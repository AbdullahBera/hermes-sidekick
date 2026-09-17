"""Owner CLI. Invoke through the owner socket under its OS identity, never as an agent tool."""
import argparse
import json
from pathlib import Path
from .client import call
from .store import ControlError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, default=Path('/run/sidekick-control/owner.sock'))
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('status','tasks','pause','resume','memories','disconnect-browser'):
        sub.add_parser(name)
    for name in ('task','cancel','retry-read','forget'):
        sub.add_parser(name).add_argument('id')
    approve = sub.add_parser('approve')
    approve.add_argument('id')
    approve.add_argument('--digest', required=True, help='copy the exact digest after reviewing task details')
    connect = sub.add_parser('connect-browser')
    connect.add_argument('--origin', action='append', required=True)
    connect.add_argument('--storage-file', type=Path, help='private Playwright storage-state JSON; never pass through model/chat')
    propose = sub.add_parser('propose')
    propose.add_argument('--file', type=Path, required=True, help='JSON with request_key, kind, title, action')
    resolve = sub.add_parser('resolve')
    resolve.add_argument('id')
    resolve.add_argument('--outcome', choices=['completed','not-completed'], required=True)
    resolve.add_argument('--note', required=True, help='evidence checked at the destination before resolving ambiguity')
    events = sub.add_parser('events')
    events.add_argument('--after', type=int, default=0)
    link = sub.add_parser('owner-link', help='print the private owner link in your trusted terminal, never in chat')
    link.add_argument('--token-file', type=Path, default=Path('/var/lib/sidekick-owner/access-token'))
    link.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    method = args.command.replace('-', '_')
    params = {k: getattr(args,k) for k in ('id','digest','after') if hasattr(args,k)}
    try:
        if method == 'owner_link':
            from .owner_web import access_token
            if not args.token_file.exists():
                raise ControlError('start the owner web service first')
            print(f'http://127.0.0.1:{args.port}/#{access_token(args.token_file)}')
            return 0
        if method == 'connect_browser':
            params = {'origins': args.origin}
            if args.storage_file:
                if args.storage_file.stat().st_mode & 0o077:
                    raise ControlError('storage state file must be private (0600)')
                params['storage'] = json.loads(args.storage_file.read_text())
        elif method == 'propose':
            params = json.loads(args.file.read_text())
        elif method == 'resolve':
            params.update(completed=args.outcome == 'completed', note=args.note)
        result = call(args.socket, method, **params)
        # Escaping control characters also prevents untrusted page text from issuing
        # terminal escape sequences in the owner's review surface.
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except (ControlError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc) if isinstance(exc, ControlError) else 'invalid local input file'}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
