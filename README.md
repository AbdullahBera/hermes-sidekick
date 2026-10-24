# hermes-sidekick

Product and operations layer for a self-hosted [Hermes Agent](https://github.com/NousResearch/hermes-agent), with an OrbStack reference setup and an opt-in controlled task service for dedicated Linux VMs.

The agent engine runs in the VM. This repo holds the control service, configuration, helper scripts, tests and deployment docs. Host sharing and OS permissions determine the actual isolation boundary.

> **New here? → [docs/QUICKSTART.md](docs/QUICKSTART.md)** — from zero to a private assistant you text, in ~20 minutes.

## Vision

The product goal is a **capable everyday assistant you text, hosted on a Linux VM you
control**—at home or in your own cloud account. It should complete tasks, remember useful
context and follow up with permission, with guided setup and dependable recovery. The current
OrbStack setup is the reference deployment; portable deployment and the complete user
experience are the next milestones in [the roadmap](docs/ROADMAP.md).

The goal is to grow this into an open-source project that lets **anyone — including
non-technical people — stand up their own private, self-hosted personal AI assistant
in minutes.** You bring a chat app (Signal today, iMessage soon) and a model API key;
the project handles the rest — provisioning the sandboxed environment, wiring the
messaging bridge, registering the number, and configuring the agent — through a
guided, few-step setup.

Today it's a working single-user alpha with scripted setup and a guided agent playbook (see [`docs/`](docs/)). The
roadmap is to package that same flow into a **push-button installer + setup wizard**,
so the manual steps (VM provisioning, `signal-cli` registration, services, `.env`)
happen automatically, safely, and with sensible defaults.

**Direction: local-first.** The next architecture keeps personal data on your own devices: a
local model coordinates, web searches stay minimal, and hosted models are used only for
explicit exceptions such as delegated coding. It is planned, not built; see the
[local-first plan](docs/LOCAL-AGENT-PLAN.md).

## Built on Hermes Agent

hermes-sidekick is a thin, security-first product layer on top of
[Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research (MIT) —
the engine that does the real work (agent loop, tools, MCP, gateway, crons, memory).
We curate and orchestrate it; we don't fork it. Please support the upstream project.

The design and plugin model live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the plan is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Architecture

```
macOS host (local checkout)                     OrbStack VM "hermes" (reference setup)
├── scripts/    thin `orb run` wrappers   ──▶   ~/.hermes/
├── docs/       decisions + redacted backups     ├── config.yaml   (model = claude-sonnet-5)
└── .env.example  documents VM keys              ├── .env          (secrets, chmod 600, gitignored)
                                                 ├── hermes-agent/ (code)
                                                 ├── skills/       (71 bundled skills)
                                                 └── sessions/ logs/ cron/ memories/
```

- **Isolation:** tools execute in Linux, but OrbStack host mounts can expose writable Mac files. VM-local paths alone do not remove that access. Choose and verify your boundary in [docs/PRIVACY.md](docs/PRIVACY.md).
- **Model:** direct Anthropic API (`ANTHROPIC_API_KEY`), bootstrap default `claude-sonnet-5`; choose a different supported model during setup.

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
./scripts/sync.sh              # check for repo→VM config drift (SOUL.md, profile, crons)
./scripts/sync.sh --apply      # deploy the safe pieces into the VM (repo is source of truth)
./scripts/migrate-state.sh     # list the ~20MB of state to move to an always-on host (dry-run)
./scripts/migrate-state.sh --to user@host   # stream state to the new host (see docs/DEPLOY.md)
# On a fresh always-on host: SIGNAL_NUMBER=+1XXXXXXXXXX ./scripts/provision.sh  (installs Hermes)
./scripts/setup-google.sh      # shrink the Google OAuth wall (scripts project+APIs, guides the rest)
```

## Security

- Secrets stay in private VM storage, never in this repo. The reference Hermes setup uses `~/.hermes/.env` (chmod 600); the optional control service isolates browser session storage under its own OS identity.
- **Automated secret scanning:** [gitleaks](https://github.com/gitleaks/gitleaks) runs as a
  pre-commit hook (`.pre-commit-config.yaml`) and in CI on every push (`.github/workflows/secret-scan.yml`),
  tuned via `.gitleaks.toml`. Enable the local hook once with `pip install pre-commit && pre-commit install`.
- `backup-config.sh` redacts all secret values before writing to the host.
- Host mounts and credentials determine the actual access boundary; prompt instructions are not an OS sandbox. See [privacy and disabling guarantees](docs/PRIVACY.md).

## Status

The reference alpha has Hermes, Signal, Claude, web search, Gmail, Calendar and Contacts configured. Its ask-first and no-send instructions are behavioral policies; see [actual capability boundaries](docs/PRIVACY.md).
Also implemented: morning brief, email triage, birthday reminders, evening prep, follow-up
nudges, meeting prep, profile-driven configuration, and two-tier memory instructions. The
catalog has 20 plugins, including keyless notes, tasks, research, read-url, places, weather,
and translation. The site is a static landing page, not a setup wizard.

Current focus: the [local-first plan](docs/LOCAL-AGENT-PLAN.md). Phase 0 is complete: it chose a
local model and runtime from measurements and verified the isolation approach. Phase 1 is next. The second-user trial remains pending. Bootstrap verifies runtime
prerequisites; a fresh profile starts with every capability **off**. Sync validates before
changing state, reconciles automation crons and the named Google MCP servers, and reports
failures. [Verification commands](docs/TESTING.md) · [second-user trial (pending)](docs/ONBOARDING-TRIAL.md).

The [controlled task service](docs/CONTROL.md) adds durable tasks and failures, exact owner
approvals, bounded browser form submissions, pause/disconnect, and approved-memory controls.
It is opt-in and requires separate agent/service OS identities for enforcement. Local appointment
fixtures verify restart recovery, lost responses and duplicate prevention; general websites and
a second user's real accounts still need acceptance testing. Live scheduled runs remain paused
during development. The private owner interface supports action review and human login handoff over an SSH tunnel.
Authenticated chat approvals and real-provider login acceptance are still pending.
