"""Single-request local IPC client. Owner authority comes from socket permissions."""
import json
import socket
from .store import ControlError, canonical


def call(path, method, **params):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(10)
            connection.connect(str(path))
            connection.sendall((canonical({'method': method, 'params': params}) + '\n').encode())
            with connection.makefile('rb') as stream:
                data = stream.readline(2_000_001)
            if len(data) > 2_000_000 or not data.endswith(b'\n'):
                raise ControlError('invalid or oversized control response')
            response = json.loads(data)
    except (OSError, ValueError):
        raise ControlError('control service unavailable or access denied') from None
    if not response.get('ok'):
        raise ControlError(response.get('error', 'control request failed'))
    return response['result']
