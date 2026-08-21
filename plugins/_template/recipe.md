# <Your connector> — self-hosted, private
#
# CONNECTORS (and channels) — the detailed, human-readable setup the onboarder follows and a
# stranger can do by hand. Runs in the VM with the user's OWN credentials — no third-party
# broker. Delete this header before shipping.

<What it connects to, and that credentials + the server run inside the VM.>

## Security posture
- **Scope:** <least-privilege scopes; what it can and cannot do>.
- **Ask-first:** <what requires an explicit "yes"; what's allowed unprompted, if anything, and why>.
- **No <destructive thing>, ever:** <how that's guaranteed — tool non-exposure and/or scope>.
- **Secrets are VM-only:** creds live in `~/.hermes/<dir>/` (chmod 600). This repo references only paths.

## One-time setup
### 1. Provider credentials (browser)
- <exact steps to create the credential; deep-link the console page if there is one>.
### 2. Install the server (in the VM)
```bash
<install command, e.g. uv tool install / apt / curl>
```
### 3. Register with Hermes + reload
```bash
hermes mcp add <name> --command <...> --args <...>
sudo systemctl restart hermes-gateway
```

## Config (documented here; real values stay in the VM)
| Var | Meaning |
|---|---|
| `<VAR>` | <what it points to — a path, not the secret itself> |

## Verify
- <the exact check that proves it works — matches the `verify` step in plugin.yaml>.
