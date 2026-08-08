# hermes-sidekick

Host-side **control folder** ("cockpit") for a self-hosted [Hermes Agent](https://github.com/NousResearch/hermes-agent) running inside an isolated OrbStack Linux VM, using **Claude (Opus 4.8)** as its model.

The agent itself is **not** in this folder — it runs sandboxed in the VM. This repo holds the helper scripts, decisions, and docs used to manage it.

## Architecture

```
macOS host (~/Desktop/projects/hermes-sidekick)   OrbStack VM "hermes" (Ubuntu 26.04, isolated)
├── scripts/    thin `orb run` wrappers   ──▶   ~/.hermes/
├── docs/       decisions + redacted backups     ├── config.yaml   (model = claude-opus-4-8)
└── .env.example  documents VM keys              ├── .env          (secrets, chmod 600, gitignored)
                                                 ├── hermes-agent/ (code)
                                                 ├── skills/       (71 bundled skills)
                                                 └── sessions/ logs/ cron/ memories/
```

- **Isolation:** all of Hermes's shell/file tools run *inside the VM* (`terminal.backend: local`), never on the Mac. Delete everything with `orb delete hermes`.
- **Model:** direct Anthropic API (`ANTHROPIC_API_KEY`), default `claude-opus-4-8`. Switch to `claude-sonnet-5` for lower cost.

## Prerequisites

- [OrbStack](https://orbstack.dev/) (`brew install --cask orbstack`)
- A running VM named `hermes` with Hermes installed (see [docs/DECISIONS.md](docs/DECISIONS.md) for how it was built).

## Setup

1. Ensure the VM is up:
   ```bash
   ./scripts/ensure-vm.sh
   ```
2. Add your Anthropic API key **into the VM** (never stored on the host):
   ```bash
   orb run -m hermes bash -lc 'read -rsp "Anthropic API key: " K; echo; printf "\nANTHROPIC_API_KEY=%s\n" "$K" >> ~/.hermes/.env; echo saved'
   ```
   Get one at console.anthropic.com → API Keys. See `.env.example` for other supported keys.

## Usage

```bash
./scripts/status.sh            # OrbStack + VM + Hermes health
./scripts/ask.sh "your task"   # one-shot prompt (non-interactive)
./scripts/chat.sh              # interactive chat (run in a real terminal)
./scripts/backup-config.sh     # snapshot config.yaml + REDACTED .env into docs/backups/
```

## Security

- Secrets live only in the VM's `~/.hermes/.env` (chmod 600), never in this repo.
- `backup-config.sh` redacts all secret values before writing to the host.
- The VM is the trust boundary: prompt-injection or a misbehaving tool is confined to the VM, not your Mac. Keep untrusted web browsing and secret-holding sessions separate.

## Status

✅ VM built · ✅ Hermes v0.20.0 installed · ✅ Claude Opus 4.8 reachable (smoke test passed).
Next: optional messaging gateway (Telegram/Slack), crons, and skill customization.
