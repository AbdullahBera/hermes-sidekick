"""Local control broker. Separate Unix sockets keep owner authority out of agent tools."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import stat
import subprocess
import threading
import time

from .store import ControlError, Store, canonical
from .validation import origins, prepare, allowed_url
from .handoff import Handoff


AGENT_METHODS = {'status','tasks','task','propose','cancel','retry_read','memories','events'}
LOGIN_METHODS = {'start_login','login_status','login_view','login_input','finish_login','cancel_login'}
OWNER_METHODS = AGENT_METHODS | LOGIN_METHODS | {'approve','pause','resume','connect_browser','disconnect_browser','forget','resolve'}


class Runtime:
    def __init__(self, store, allow_loopback=False, executor=None):
        self.store = store
        self.allow_loopback = allow_loopback
        self.executor = executor or self.browser
        self.guard = threading.RLock()
        self.stop = threading.Event()
        self.process = None
        self.active_task = None
        self.worker = None
        self.failed = threading.Event()
        self.handoff = Handoff(allow_loopback)

    def dispatch(self, role, request):
        if not isinstance(request, dict) or set(request) - {'method','params'}:
            raise ControlError('request requires method and params only')
        method = request.get('method')
        params = request.get('params', {})
        if method not in (OWNER_METHODS if role == 'owner' else AGENT_METHODS):
            raise ControlError('owner authority required or unknown method')
        if not isinstance(params, dict):
            raise ControlError('params must be an object')
        if method in LOGIN_METHODS:
            return self.login(method, params)
        # Serialized with dispatch/termination so pause cannot race a new browser spawn.
        with self.guard:
            if method == 'status':
                return dict(self.store.status(), worker_failed=self.failed.is_set(),
                            worker_running=bool(self.worker and self.worker.is_alive()))
            if method == 'tasks':
                return self.store.list_tasks()
            if method == 'task':
                return self.store.get(params['id'])
            if method == 'propose':
                action = prepare(self.store, params['kind'], params['action'])
                return self.store.propose(params['request_key'], params['kind'], params['title'], action)
            if method == 'approve':
                return self.store.approve(params['id'], params['digest'])
            if method in ('pause','resume'):
                if method == 'resume' and self.handoff.active():
                    raise ControlError('finish or cancel the private login before resuming tasks')
                result = self.store.set_paused(method == 'pause')
                if method == 'pause':
                    self.kill_browser()
                    self.handoff.close()
                return result
            if method == 'cancel':
                result = self.store.cancel(params['id'])
                if params['id'] == self.active_task:
                    self.kill_browser()
                return result
            if method == 'retry_read':
                return self.store.retry_read(params['id'])
            if method in ('connect_browser','disconnect_browser'):
                enabled = method == 'connect_browser'
                allowed = origins(params['origins'], self.allow_loopback) if enabled else None
                storage = params.get('storage') if enabled else None
                if storage is not None and (not isinstance(storage, dict) or set(storage) - {'cookies','origins'} or not isinstance(storage.get('cookies', []), list) or not isinstance(storage.get('origins', []), list)):
                    raise ControlError('invalid Playwright browser storage state')
                result = self.store.configure_browser(enabled, allowed, storage)
                self.kill_browser()
                self.handoff.close()
                return result
            if method == 'memories':
                return self.store.memories()
            if method == 'forget':
                return self.store.forget(params['id'])
            if method == 'events':
                return self.store.events(params.get('after', 0))
            if method == 'resolve':
                if type(params['completed']) is not bool:
                    raise ControlError('completed must be boolean')
                return self.store.resolve(params['id'], params['completed'], params['note'])
        raise ControlError('unknown method')

    def login(self, method, params):
        with self.guard:
            if method == 'login_status':
                active = self.handoff.active()
                return {'active': active, 'session_id': self.handoff.session_id,
                        'origins': self.handoff.origins if active else []}
            if method == 'start_login':
                connected = origins(params['origins'], self.allow_loopback)
                additional = origins(params['login_origins'], self.allow_loopback) if params.get('login_origins') else []
                url = allowed_url(params['url'], connected)
                if self.handoff.active():
                    raise ControlError('finish or cancel the current login first')
                self.store.set_paused(True)
                self.kill_browser()
                session_id = self.handoff.begin(connected)
                op, values = 'start', dict(origins=connected, login_origins=additional, url=url,
                                          allowLoopback=self.allow_loopback)
            else:
                session_id = params['session_id']
                if not self.handoff.active() or session_id != self.handoff.session_id:
                    raise ControlError('login session expired or changed; start again')
                if method == 'cancel_login':
                    self.handoff.close()
                    return {'cancelled': True, 'paused': True}
                if method == 'finish_login':
                    if params.get('confirmed') is not True:
                        raise ControlError('confirm the signed-in account before connecting it')
                    op, values = 'finish', {}
                elif method == 'login_input':
                    op, values = 'input', {'event': params['event']}
                else:
                    op, values = 'view', {}
        # Owner pause/cancel can kill the handoff while navigation is waiting.
        try:
            result = self.handoff.command(session_id, op, **values)
        except Exception:
            if method == 'start_login':
                with self.guard:
                    if self.handoff.session_id == session_id:
                        self.handoff.close()
            raise
        with self.guard:
            if not self.handoff.active() or session_id != self.handoff.session_id:
                raise ControlError('login was cancelled or expired')
            if method == 'finish_login':
                self.store.configure_browser(True, self.handoff.origins, result['storage'])
                self.handoff.close()
                return {'connected': True, 'paused': True}
            return dict(result, session_id=session_id)

    def kill_browser(self):
        if self.process is not None and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def browser(self, task):
        with self.guard:
            if self.stop.is_set() or self.store.get(task['id'])['state'] != 'running' or self.store.status()['paused']:
                return {'outcome': 'uncertain' if task['kind'] == 'browser.submit' else 'failed', 'error': 'execution_stopped'}
            c = self.store.connector()
            if not c['enabled'] or c['generation'] != task['connector_generation']:
                return {'outcome': 'failed', 'error': 'connector_changed'}
            args = ['node', str(Path(__file__).with_name('browser.mjs'))]
            env = {k: v for k, v in os.environ.items() if k.upper() not in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NODE_OPTIONS','NODE_PATH')}
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, env=env, start_new_session=True)
            self.process = process
            payload = canonical({'kind': task['kind'], 'action': task['action'], 'origins': c['hosts'],
                                 'storage': c['storage'], 'allowLoopback': self.allow_loopback})
        try:
            output, _ = process.communicate(payload, timeout=45)
            if process.returncode or len(output) > 200000:
                raise ControlError('browser process ended without a verifiable result')
            result = json.loads(output)
            if result.get('outcome') not in ('succeeded','failed','uncertain'):
                raise ControlError('invalid browser outcome')
            return result
        except (subprocess.TimeoutExpired, ValueError, ControlError):
            with self.guard:
                self.kill_browser()
            process.communicate()
            return {'outcome': 'uncertain' if task['kind'] == 'browser.submit' else 'failed',
                    'error': 'browser_timeout_or_interruption'}
        finally:
            with self.guard:
                if self.process is process:
                    self.process = None

    def run_once(self):
        with self.guard:
            if self.stop.is_set():
                return False
            self.handoff.active()  # expire human sessions even while execution is paused
            task = self.store.claim()
            if task is None:
                return False
            self.active_task = task['id']
        try:
            if task['kind'] == 'memory.save':
                with self.guard:
                    if self.store.get(task['id'])['state'] == 'running':
                        self.store.save_memory_task(task['id'])
            else:
                result = self.executor(task)
                # Store bounded results only. No arbitrary exception text goes into history.
                evidence = result.get('result')
                if evidence is not None:
                    evidence = dict(evidence, elapsed_ms=result.get('elapsed_ms'))
                self.store.finish(task['id'], result['outcome'], evidence, result.get('error'))
        except Exception:
            self.store.finish(task['id'], 'uncertain' if task['kind'] == 'browser.submit' else 'failed', error='worker_error')
        finally:
            with self.guard:
                self.active_task = None
        return True

    def start(self):
        self.store.recover()
        def loop():
            try:
                while not self.stop.is_set():
                    if not self.run_once():
                        self.stop.wait(0.25)
            except Exception:
                # Database/queue failures must stop the service so systemd can restart it.
                # Never leave a healthy-looking API with a silently dead worker.
                self.failed.set()
                self.stop.set()
        self.worker = threading.Thread(target=loop, name='sidekick-worker', daemon=True)
        self.worker.start()

    def shutdown(self):
        with self.guard:
            self.stop.set()
            self.kill_browser()
            self.handoff.close()
        if self.worker:
            self.worker.join(timeout=5)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        try:
            limit = 2_000_000 if self.server.role == 'owner' else 100000
            line = self.rfile.readline(limit + 1)
            if not line.endswith(b'\n') or len(line) > limit:
                raise ControlError('request exceeds limit or is incomplete')
            request = json.loads(line)
            result = self.server.runtime.dispatch(self.server.role, request)
            response = {'ok': True, 'result': result}
        except ControlError as exc:
            response = {'ok': False, 'error': str(exc)}
        except (ValueError, KeyError, TypeError):
            response = {'ok': False, 'error': 'invalid request parameters'}
        except Exception:
            response = {'ok': False, 'error': 'control operation failed; inspect service health locally'}
        try:
            self.wfile.write((canonical(response) + '\n').encode())
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, path, runtime, role):
        self.runtime, self.role = runtime, role
        path = Path(path)
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not stat.S_ISSOCK(path.stat().st_mode):
                raise ControlError('refusing to replace a non-socket control path')
            with socket.socket(socket.AF_UNIX) as probe:
                try:
                    probe.connect(str(path))
                except (ConnectionRefusedError, FileNotFoundError):
                    path.unlink(missing_ok=True)
                else:
                    raise ControlError('control socket is already in use')
        super().__init__(str(path), Handler)
        os.chmod(path, 0o600 if role == 'owner' else 0o660)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('/var/lib/sidekick-control'))
    parser.add_argument('--sockets', type=Path, default=Path('/run/sidekick-control'))
    parser.add_argument('--dev', action='store_true', help='allow same-user local testing and loopback fixture origins; not an isolation boundary')
    args = parser.parse_args()
    os.umask(0o077)
    # Production unit creates the two socket permissions under the restricted agent group.
    if not args.dev and (os.geteuid() == 0 or os.environ.get('SIDEKICK_ISOLATED_SERVICE') != '1'):
        raise SystemExit('Run the isolated systemd service, or explicitly use --dev for fixtures')
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = os.open(args.state / '.service-lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('another control worker owns this state') from None
    store = Store(args.state)
    args.sockets.mkdir(parents=True, exist_ok=True, mode=0o750)
    if args.sockets.is_symlink() or args.sockets.stat().st_mode & 0o022:
        raise SystemExit('socket directory must not be writable by other users')
    runtime = Runtime(store, allow_loopback=args.dev)
    servers = [Server(args.sockets / 'owner.sock', runtime, 'owner'), Server(args.sockets / 'agent.sock', runtime, 'agent')]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    runtime.start()
    finished = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: finished.set())
    print('Sidekick control ready. Inspect status before resuming work.', flush=True)
    try:
        while not finished.wait(0.25):
            if runtime.failed.is_set():
                raise SystemExit('Control worker failed; review service health before resuming')
    finally:
        runtime.shutdown()
        for server in servers:
            server.shutdown()
            server.server_close()
            Path(server.server_address).unlink(missing_ok=True)
        os.close(lock)


if __name__ == '__main__':
    main()
