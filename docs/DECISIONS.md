# Design decisions

A running log of why this setup is the way it is.

## North star (product goal)

Build this into an **open-source project that lets a non-technical person create
their own private personal agent in minutes.** Everything in this doc that we did by
hand is, long-term, work the project should automate for the user: provisioning the
isolated environment, installing and registering the messaging bridge, standing up
services, and writing config — behind a guided, safe, few-step setup. Re-evaluate
every design choice below against: "how do we make this push-button and safe for
someone who can't use a terminal?"

## 2026-08-03/04 — Initial build

### Why Hermes Agent
Wanted a self-hostable, single-user autonomous agent I fully own (tools, memory,
skills, crons) — not a team platform (evaluated YC's `qm`, too company-scale for
one person) and not just a framework to hand-build (LangGraph / Claude Agent SDK).
Hermes is MIT, model-agnostic, ships 40+ tools + a learning/skills loop, and runs
locally. See the conversation research for the full comparison.

### Why an OrbStack **VM** (not Docker, not host install)
- Hermes ships **no official Docker image**, so a container path would mean hand-
  writing and maintaining a Dockerfile.
- Its installer is a `curl … | bash` that installs onto the host — the opposite of
  the isolation goal.
- An OrbStack **Linux VM** gives real isolation from macOS, contains the installer
  itself, starts fast, is light on battery, and is disposable (`orb delete hermes`).
- Chosen over Docker Desktop as the OrbStack runtime for speed/battery on Apple Silicon.

VM: `hermes` — Ubuntu 26.04 LTS, arm64.

### Why Claude via the **direct Anthropic provider**
- Wanted Claude-quality reasoning. Hermes's `config.yaml` supports a native
  `anthropic` provider (`ANTHROPIC_API_KEY`), so no OpenRouter middleman is needed.
- Default model set to `claude-opus-4-8` (most capable). `claude-sonnet-5` is the
  cheaper fallback for an always-on agent.
- There is no separate "Claude Code API" — Claude Code uses the same Anthropic API;
  a Pro/Max subscription is not a third-party agent credential.

### Terminal backend = `local`
Hermes runs its shell/file tools *inside the VM* (`terminal.backend: local`). Since
the VM is already the sandbox, this is the simplest safe option — no nested
container needed.

### Secrets handling
- Keys live only in the VM's `~/.hermes/.env` (chmod 600), entered via a silent
  `read -rsp` prompt so they never touch the chat transcript or host repo.
- Host-side backups redact all secret values before writing.

### Gmail integration — self-hosted, read + draft, ask-first (2026-08-09)
Chose [`google_workspace_mcp`](https://github.com/taylorwilsdon/google_workspace_mcp)
running in the VM with the user's *own* Google OAuth client (Desktop app) — no
third-party broker (evaluated Composio; rejected for privacy). Granted scope: read +
labels + drafts (`gmail.readonly`/`labels`/`compose`); `gmail.modify` intentionally
not granted. **No send** tool exists and the scope can't send. A **hard rule** in
`SOUL.md` forbids any email action (draft/label/change) without explicit
confirmation. App published "In production" so the refresh token persists. Details:
`plugins/connectors/gmail/recipe.md`.

### Calendar integration — self-hosted, read-only (2026-08-10)
Google Calendar via the same `google_workspace_mcp` + OAuth client as Gmail (same
token, re-authed to add `calendar.readonly`). Registered as a separate `calendar` MCP
server (`list_calendars`, `get_events`, `query_freebusy`). Now read+write (`calendar:full`): create/edit/delete events, gated by the ask-first hard rule. See `plugins/connectors/calendar/recipe.md`.

### Email triage — gmail.modify for label-sorting, protection by policy (2026-08-15)
Added the `gmail.modify` scope so the assistant can sort the inbox by **adding the user's own
labels to messages** (`messages.modify`; `gmail.labels` alone only edits label *definitions*).
The same scope also permits archive/trash/mark-read, so — unlike the read-first connectors —
protection here is **policy, not scope**: a hard rule in `SOUL.md` confines unprompted writes to
(a) ADDING the user's configured triage labels (mail stays in the inbox) and (b) creating DRAFTS
(shown to the user, never sent). Archive, trash, mark read/spam, unsubscribe → explicit "yes".

Deliberately did **not** grant the full-mailbox scope (`https://mail.google.com/`), so permanent
delete is impossible — worst case is recoverable Trash. Kept `send` off: no send tool is exposed
and the permission level stays at `drafts` (below `send`/`full`).

Correctness fix: earlier docs claimed "the granted scope can't send." Inaccurate — `gmail.compose`
technically can send. The real guarantee is **tool non-exposure + ask-first**, now stated that way
in the plugin manifest and recipe.

Accepted residual risk: a prompt-injection carried in a hostile email could try to make the agent
label/archive/trash maliciously. Mitigations: the SOUL.md hard rule (system labels off-limits;
destructive actions ask-first), VM isolation, no send path, and no permanent delete. Triage is
read-only otherwise, auto-drafts (never sends), and folds into the morning brief (check-in
triggered) so a sleeping laptop never misses a run. Revisit if we expose more of modify's surface.

### Calendar date-safety + SOUL.md deployment drift (2026-08-16)
A relative-date request ("today/tomorrow") led the agent to delete the **wrong** calendar event.
Two causes: (1) Hermes injects only a **date-only, potentially-stale** "Conversation started" line
(kept byte-stable for prefix-cache — it expects the model to query exact time via tools), and
(2) the live VM `~/.hermes/SOUL.md` had **drifted to an old ruleset** — none of the security-audit
hardening was actually deployed. Fixes: added a "dates & calendar safety" hard rule — resolve the
current date+time in `core.timezone` via a tool (`date`) before any date math, and **echo the exact
event (title + weekday/date + start time) for an explicit "yes" before any create/edit/delete** —
and deployed the reviewed `config/SOUL.md` to the VM so all hardened rules are finally live.
Timezone itself was already correct (`hermes_time` falls back to server localtime =
America/Los_Angeles). Lesson: the repo `config/SOUL.md` is a **template** — edits are inert until
deployed to `~/.hermes/SOUL.md` and the gateway is restarted.

### Fresh-install shakedown — prerequisites the installers silently assume (2026-08-18)
Ran the onboarder path against a clean OrbStack Ubuntu 26.04 arm64 VM (isolated from the live
one). A fresh VM lacks things the scripts + upstream Hermes installer assume are present:
- **`xz-utils` (most dangerous):** without it the Hermes installer's Node `.tar.xz` extraction
  fails — but the installer still **exits 0**, leaving a broken install with no `hermes`. Silent
  and fatal. Our live VM happened to have `xz`, so we never saw it.
- **`git`:** the bootstrap repo-clone needs it; not preinstalled.
- **Java 25:** signal-cli 0.14.7 is compiled for class-file 69 (Java 25); a JRE 21 throws
  `UnsupportedClassVersionError`. `provision.sh` now installs `openjdk-25-jre-headless`.
- `hermes` lands on the login PATH via `~/.local/bin` (Ubuntu's `.profile`) — no extra PATH
  work needed once the install actually succeeds.
- Gateway service: use `hermes gateway install --system --no-start-now` (canonical) instead of
  hand-writing the unit, so it won't drift on Hermes updates. The signal-cli unit stays ours.
Fixes landed in `onboarder/bootstrap.sh` + `scripts/provision.sh`. Verified on the throwaway VM:
Hermes v0.20.4 installs + runs, `workspace-mcp` installs, signal-cli 0.14.7 runs under Java 25.
Lesson: `curl | bash` installers that exit 0 on partial failure are why the shakedown matters.

### Reconciled model routing to direct Anthropic (2026-08-22)
The live `config.yaml` had drifted to `provider: auto` with `base_url: https://openrouter.ai/api/v1`
(an OpenRouter default), while only `ANTHROPIC_API_KEY` was present in `.env` — contradicting the
"direct Anthropic, no middleman" decision above. Set it explicitly: `model.provider: anthropic`,
`model.default: claude-sonnet-5`, and unset `base_url` (so it uses Anthropic's endpoint). The 4
automation crons carried pinned `model_snapshot`s and would fail-closed on the change, so each was
re-pinned (`hermes cron edit <id> --model claude-sonnet-5 --provider anthropic`). Verified with a
live one-shot call (returned "pong"). Also fixed `bootstrap.sh`'s onboarder-launch line — `hermes`
needs a subcommand/flag (`hermes -z "…"`), not a bare prompt.

### End-to-end onboarding test — full pipeline validated on a fresh VM (2026-08-29)
Ran the whole chain on an isolated fresh VM (deleted after): hardened deps → Hermes install →
migrated the key + Google creds → registered the calendar MCP (connected, 8 tools) → set
direct-Anthropic → `sync`-deployed SOUL + prompts → ran the morning brief through the agent. It
produced a correct brief (real weather in the configured units + the real calendar), read-only on
the accounts (email excluded, delivery `local`). This proves the deterministic install + config +
connector + run pipeline works for a fresh user. Still unproven (irreducible human signups):
creating a NEW Google OAuth client from scratch, and a NEW Signal registration.

Finding + fix: the Hermes installer does NOT set up the gateway service (the **cron scheduler** +
Signal). So a fresh `bootstrap.sh` installed everything except the thing that makes proactive
automations fire. Fixed: bootstrap now runs `hermes gateway install` (provision.sh already did).
Without it, everything installs cleanly but nothing ever fires.

## Reliability and second-user readiness (2026-09-08)

Sync now validates the full input set before mutation and returns failure for invalid profiles
or failed commands. The old invalid-profile fallback could pause every automation. Regression
fixtures cover that failure, subprocess failures, idempotent reconciliation, and reload retry.
MCP enablement is reconciled for the three separately registered Google connectors; shell-based
capabilities still use policy. Profile timezone is written to Hermes scheduler configuration.

Host filesystem inspection confirmed the reference VM exposes Mac directories. Prior statements
that VM execution alone confined access away from the Mac were too broad. The actual boundary,
residual credential access, and strict host-share detection are documented in PRIVACY.md.

Bootstrap verifies runtime stages and starts new profiles with capabilities disabled. CI and
read-only health checks are implemented. Fresh second-user Google OAuth, Signal registration,
and scheduled delivery remain pending the participant trial in ONBOARDING-TRIAL.md.

## Local-first direction (2026-10-24)

### A local model coordinates; hosted models are narrow exceptions
Personal conversations, health and financial records, notes, memory, embeddings and logs are
processed on the owner's devices. A local model is the coordinator. We considered the reverse,
a hosted model that routes sensitive questions to the local one, and rejected it: the router
must read every message to decide, so private messages would reach the cloud first, and the
router would also see the local model's answers and the whole conversation history.

Two exceptions are deliberate and narrow. Coding work goes to Claude Code with a scoped brief
and the project's files; the worker may search the web for coding or other non-personal work.
General questions go to Claude only when the owner prefixes them with `claude:`, without
history or memory. There is no silent fallback to a hosted model.

### Enforce privacy with architecture, not prompts
Separate OS accounts per zone, outbound traffic blocked by default, and brokers that build
every outbound request. An agent with private data, untrusted content and a way to send data
out (the "lethal trifecta"; Meta's "Rule of Two") is exposed to prompt injection, and
published adaptive attacks break most detection-based defenses. So outbound actions after
untrusted content enters a turn need a pre-made plan or owner approval (the taint rule), raw
web pages are read by a separate local-model context with no tools or private data, and
fixed query rules modeled on the HIPAA Safe Harbor identifiers check every query. These reduce
risk; they do not guarantee anonymity.

### Exa for search
Google's Custom Search JSON API is closed to new customers and scheduled to shut down on
2027-01-01. Exa remains. Its general privacy policy allows using query data to improve its
products, including training; API customers are governed by their agreement. Queries are
therefore minimal and general by design.

### MLX first for local inference
Inference runs natively on macOS because a Linux VM does not get Metal acceleration. MLX is
evaluated first because it is built for Apple Silicon. Model choice follows measured tool-call
reliability, query-rewriting leaks, extraction accuracy, latency and memory headroom.

### Sim for workflows, private tier first
[Sim](https://github.com/simstudioai/sim) (Apache-2.0) is self-hosted in its own VM with local
models only. Its hosted Chat/Copilot service, remote code sandboxes, telemetry and cloud
providers are disabled. Workflows that read private data cannot send anything out; public and
mixed workflows come later, one integration at a time.

### Personal notes vault stays out of cloud work
The owner's notes vault is personal data. It is excluded from the coding worker's project
registry and is handled only by the local model.

### Correction: Claude Code programmatic use
The 2026-08-03 entry said there is no separate Claude Code API. Programmatic use goes through
the Agent SDK or `claude -p`; the recommended scripted mode, `--bare`, authenticates with an
API key rather than a subscription login, and Agent SDK products are expected to use API keys.
API (commercial) terms exclude training on prompts; consumer plans may train when that
setting is on. The coding worker therefore uses its own API key with a spending limit.

### Memory: an approved source of truth, not an agent-managed memory (2026-10-24)
Personal memory is an approved-memory store with source, date and explicit/inferred labels;
search indexes are derived from it and rebuilt after deletions; research stays in a separate
untrusted cache. Letta was rejected for now: it is a full agent runtime whose agents edit their
own pinned memory, which would compete with Hermes and make a successful injection persist in
every prompt. Mem0 (an official Hermes provider with a local mode) captures and rewrites facts
after every turn without approval and sends telemetry by default, so it is only a candidate
for extraction and search with automatic capture constrained. A Phase 1 bake-off decides.

### VM isolation: OrbStack isolated machines plus one forwarded port (2026-10-24)
Phase 0 showed that an ordinary OrbStack VM can reach every service on the Mac's loopback
interface, so "listen on 127.0.0.1" does not keep a service away from VMs. `--isolated` removes
the Mac filesystem but still allowed loopback access in testing; `--isolated --isolate-network`
blocks the Mac and other VMs while keeping internet access. The Mac then opens a reverse SSH
tunnel over the `orb` command channel to forward only the inference port (OrbStack's own SSH
proxy does not allow reverse forwarding). The forwarded port still needs a token and a
per-account firewall rule inside the VM.

### Phase 0 findings
The reference VM has host filesystem mounts, and the default home and Conductor folder
permissions let other local accounts read workspaces. Both must change before private data
(Phase 1) and before a separate coding account (Phase 3). Details are in
[LOCAL-AGENT-PLAN.md](LOCAL-AGENT-PLAN.md).

### Model and runtime: Qwen3.6-35B-A3B on mlx-lm (2026-10-24)
Benchmarked on synthetic data (results in LOCAL-AGENT-PLAN.md). The mixture-of-experts model
matched the others on tool calls and extraction and was the fastest: 65 tokens/s on mlx-lm
versus 39 on Ollama's llama.cpp engine and 25 on Ollama's MLX engine for the same model, with
equal prompt-cache reuse across turns. The dense 27B was about 6 times slower. Ollama stays,
in local-only mode, for embeddings (`qwen3-embedding:0.6b` with a 2K context). Because
`mlx_lm.server` is not hardened, Phase 1 adds an authenticated proxy. Memory is the main risk:
the model peaks at 22–23 GB at long contexts on a 32 GB host.

## Open / next
- Phase 1: isolated VM, authenticated inference proxy and tunnel, local-only Hermes, memory
  bake-off, all on synthetic data.
- Complete the fresh-account second-user trial and record actual delivery evidence.
- Always-on host: an Apple Silicon Mac mini is the intended host. Nothing migrates before the
  Phase 1 gate, and old scheduled routines are not re-enabled automatically.
- Further permission enforcement must happen outside the model; prompt rules are not a sandbox.
