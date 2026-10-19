"""Private owner controls. Loopback only; reach remote deployments through SSH forwarding."""
import argparse
import fcntl
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import stat
from urllib.parse import urlsplit

from .client import call
from .service import OWNER_METHODS
from .store import ControlError, canonical

STATIC = Path(__file__).with_name('static')
# Proposals remain on the agent API; no raw session import/export in the web UI.
WEB_METHODS = OWNER_METHODS - {'propose','connect_browser'}


def access_token(path, rotate=False):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077 or path.is_symlink():
        raise ControlError('owner access token must be in a private directory')
    if path.exists() and (not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077):
        raise ControlError('owner access token must be a private regular file')
    if rotate or not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(secrets.token_urlsafe(32))
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
        raise ControlError('owner access token must be a private regular file')
    token = path.read_text().strip()
    if len(token) != 43 or not all(c.isalnum() or c in '-_' for c in token):
        raise ControlError('invalid owner access token')
    return token


class OwnerServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port, endpoint, token):
        self.endpoint, self.token = endpoint, token
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    server_version = 'SidekickOwner'
    def log_message(self, *_):
        pass  # URL, form input and credentials must never enter access logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(35)

    def respond(self, status, value, content_type='application/json'):
        body = canonical(value).encode() if content_type == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass

    def valid_host(self):
        return self.headers.get('Host') == urlsplit(self.server.origin).netloc

    def authorized(self, mutation=False):
        if not self.valid_host() or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        origin = self.headers.get('Origin')
        if (mutation and origin != self.server.origin) or (origin and origin != self.server.origin):
            return False
        received = self.headers.get('Authorization', '')
        return hmac.compare_digest(received.encode(), ('Bearer '+self.server.token).encode())

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {'error':'Use the private loopback address.'})
        assets = {'/':('owner.html','text/html; charset=utf-8'), '/owner.js':('owner.js','text/javascript; charset=utf-8'), '/owner.css':('owner.css','text/css; charset=utf-8')}
        if self.path in assets:
            filename, kind = assets[self.path]
            return self.respond(200, (STATIC/filename).read_bytes(), kind)
        self.respond(404, {'error':'Not found'})

    def do_POST(self):
        if not self.authorized(mutation=True):
            return self.respond(403, {'error':'Owner access required. Open your private access link.'})
        if self.path != '/api' or self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
            return self.respond(400, {'error':'Unsupported request'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 100000:
                raise ControlError('request exceeds limit')
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict) or set(value) - {'method','params'}:
                raise ControlError('invalid request')
            method, params = value.get('method'), value.get('params',{})
            if method not in WEB_METHODS or not isinstance(params, dict):
                raise ControlError('unsupported owner operation')
            self.respond(200, {'result':call(self.server.endpoint, method, **params)})
        except ControlError as error:
            self.respond(400, {'error':str(error)})
        except (ValueError, TypeError, KeyError):
            self.respond(400, {'error':'Invalid request'})
        except Exception:
            self.respond(503, {'error':'Owner operation unavailable. Check the local service.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, default=Path('/run/sidekick-control/owner.sock'))
    parser.add_argument('--token-file', type=Path, default=Path('/var/lib/sidekick-owner/access-token'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    os.umask(0o077)
    call(args.socket, 'status')  # fail clearly if not running under the owner identity
    # Bind before rotating: a second launch must not invalidate the running UI's link.
    server = OwnerServer(args.port, args.socket, '')
    access_token(args.token_file)
    lock = os.open(args.token_file.parent / '.owner-lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        server.server_close()
        raise SystemExit('another owner web service owns this access token') from None
    server.token = access_token(args.token_file, rotate=True)
    print(f'Owner controls: {server.origin}. Read the access link with the owner CLI; it is not logged here.', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        os.close(lock)


if __name__ == '__main__':
    main()
