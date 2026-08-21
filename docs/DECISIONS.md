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

## Open / next
- Optional messaging gateway (Telegram/Slack) via `hermes gateway install`.
- Crons for background automation.
- Decide cost ceiling → maybe default to `claude-sonnet-5`.
- Always-on: currently tied to the Mac being awake + OrbStack running; revisit a
  dedicated always-on host later if needed.
