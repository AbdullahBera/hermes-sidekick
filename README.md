# hermes-sidekick

Host-side **control folder** ("cockpit") for a self-hosted [Hermes Agent](https://github.com/NousResearch/hermes-agent) running inside an isolated OrbStack Linux VM, using **Claude** as its model.

The agent itself is **not** in this folder — it runs sandboxed in the VM. This repo holds the helper scripts, decisions, and docs used to manage it.

## Vision

The goal is to grow this into an open-source project that lets **anyone — including
non-technical people — stand up their own private, self-hosted personal AI assistant
in minutes.** You bring a chat app (Signal today, iMessage soon) and a model API key;
the project handles the rest — provisioning the sandboxed environment, wiring the
messaging bridge, registering the number, and configuring the agent — through a
guided, few-step setup.

Today it's a working single-user build assembled by hand (see [`docs/`](docs/)). The
roadmap is to package that same flow into a **push-button installer + setup wizard**,
so the manual steps (VM provisioning, `signal-cli` registration, services, `.env`)
happen automatically, safely, and with sensible defaults.

## Built on Hermes Agent

hermes-sidekick is a thin, security-first product layer on top of
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT) —
the engine that does the real work (agent loop, tools, MCP, gateway, crons, memory).
We curate and orchestrate it; we don't fork it. Please support the upstream project.

The design and plugin model live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

✅ VM + Hermes v0.20.0 · ✅ **Signal** transport live · ✅ model `claude-sonnet-5` · ✅ web search (keyless) · ✅ **Gmail** ([read + draft, never send](plugins/connectors/gmail/recipe.md)) · ✅ **Calendar** ([read-only](plugins/connectors/calendar/recipe.md)) — both private, and ask-first on any action.
Next: proactivity (morning brief: calendar + flagged email), and persistent memory.
