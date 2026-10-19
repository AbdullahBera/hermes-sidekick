"""Ephemeral, owner-only login. No screenshots or keystrokes are written to task history."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
import uuid

from .store import ControlError, canonical


class Handoff:
    def __init__(self, allow_loopback=False, clock=time.monotonic):
        self.allow_loopback, self.clock = allow_loopback, clock
        self.process = None
        self.tempdir = None
        self.session_id = None
        self.expires = 0
        self.origins = []
        self.responses = queue.Queue(maxsize=2)
        self.command_lock = threading.Lock()

    def active(self):
        if self.process and (self.clock() >= self.expires or self.process.poll() is not None):
            self.close()
        return self.process is not None

    def begin(self, origins):
        if self.active():
            raise ControlError('cancel or finish the existing login first')
        self.session_id = uuid.uuid4().hex
        self.expires = self.clock() + 900
        self.origins = origins
        self.responses = queue.Queue(maxsize=2)
        env = {k:v for k,v in os.environ.items() if k.upper() not in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NODE_OPTIONS','NODE_PATH')}
        self.tempdir = tempfile.TemporaryDirectory(prefix='sidekick-login-')
        env['TMPDIR'] = self.tempdir.name
        try:
            self.process = subprocess.Popen(['node', str(Path(__file__).with_name('login.mjs'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, env=env, start_new_session=True)
        except OSError:
            self.close()
            raise ControlError('login browser could not start; check the Node installation') from None
        process, responses = self.process, self.responses
        def read():
            try:
                while True:
                    line = process.stdout.readline(2_000_001)
                    if not line or len(line) > 2_000_000 or not line.endswith('\n'):
                        responses.put_nowait(None)
                        return
                    responses.put_nowait(json.loads(line))
            except Exception:
                try: responses.put_nowait(None)
                except queue.Full: pass
            finally:
                process.stdout.close()
        threading.Thread(target=read, daemon=True).start()
        return self.session_id

    def command(self, session_id, op, **params):
        with self.command_lock:
            return self._command(session_id, op, **params)

    def _command(self, session_id, op, **params):
        if not self.active() or session_id != self.session_id:
            raise ControlError('login session expired or changed; start again')
        process, responses = self.process, self.responses
        try:
            process.stdin.write(canonical(dict(op=op, **params))+'\n')
            process.stdin.flush()
            response = responses.get(timeout=25)
            if response is None:
                raise ControlError('login browser stopped; start again')
            if not response.get('ok'):
                raise ControlError('login browser operation failed; refresh or cancel the handoff')
            return response['result']
        except (OSError, ValueError, AttributeError, queue.Empty):
            if self.session_id == session_id:
                self.close()
            raise ControlError('login browser interrupted; start again') from None

    def close(self):
        process, self.process = self.process, None
        temporary, self.tempdir = self.tempdir, None
        self.session_id = None
        self.origins = []
        if process:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: pass
            try: process.stdin.close()
            except (OSError, ValueError): pass
            # The reader owns stdout; closing it here can block behind its read lock.
        if temporary:
            temporary.cleanup()
