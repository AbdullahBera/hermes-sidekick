# Roadmap

hermes-sidekick aims to be a complete personal assistant people can text, running on a
Linux VM they administer at home or in their own cloud account. It should remember useful
context, complete everyday tasks, and follow up with permission. Ownership must come with a
usable product: guided setup, clear controls, reliable execution, and straightforward recovery.
This roadmap distinguishes implemented capabilities from product goals and acceptance still pending.

## Product direction

**A capable everyday assistant, hosted and controlled by its user.**

The user owns the assistant's runtime, persistent state, browser sessions and connector
configuration. External model and connector services still receive the data needed for their
requests; self-hosting is not a promise of offline inference. Actual access boundaries are
specified in [PRIVACY.md](PRIVACY.md).

Self-hosting is an architectural requirement, not a substitute for task quality or ease of use.
The product must earn daily use through successful outcomes. Keep Hermes as the execution
engine; build the missing setup, control, approval and recovery experience around it.

## Next product milestones, in order

1. **Repeatable deployment on a user-managed Linux VM.** Support one documented Linux
   baseline first, with VM-local storage and browser execution. The deployment must work
   without Mac filesystem mounts or an OrbStack dependency inside the VM. Provide guided
   configuration, health checks, backup/restore and a documented upgrade/rollback path.
   Signal remains the first supported messaging path; additional channels follow a proven
   deployment. Complete the [fresh-account second-user trial](ONBOARDING-TRIAL.md).
2. **A dependable task lifecycle.** Persist accepted work, progress, completion and failures;
   support cancellation and recovery after restart without repeating external actions.
   Approvals for consequential actions must be bound to the exact proposed action and checked
   by execution code. Agent instructions alone are not the enforcement boundary. Provide an
   immediate pause control and a user-visible action history; keep sensitive details local.
3. **Useful browser execution on that same VM.** Measure the existing browser's latency and
   failure modes before choosing a replacement engine or different host requirements. Support
   secure human handoff for login/challenges and require approval before submission. Benchmark
   complete user tasks, including failures and retries, rather than counting available tools.
4. **Demonstrate three complete daily-use workflows.** (a) Read a request, offer concrete
   calendar options, and create the selected event only after approval. (b) Prepare a meeting
   from connected email/calendar and relevant saved context. (c) Find an available appointment
   on a real website, reach the confirmation step, and complete only the approved action.
   Measure correctness, elapsed time, model cost and human intervention. The second participant
   must verify results on their own accounts; keep payments and sensitive identity workflows
   out of this first acceptance set.

The long-term audience includes non-technical people. The first acceptance participant can
provision a VM, but daily use should happen through conversation. The control interface exists
for setup, permissions, approvals, memory inspection/deletion, health and recovery.

More connectors, voice, additional messaging channels and public distribution follow these
milestones. Feature breadth does not replace proof that a small set of tasks works reliably.

## Shipped ✅
- **Channel:** Signal. **Model:** Claude Sonnet 5 via the **direct Anthropic** provider.
  **Voice:** concise, human, text-native; matches your tone (Turkish for Turkish names).
- **Connectors:** Gmail (read + draft + label-sort, never sends), Calendar (read + write,
  ask-first), Contacts (read). Web search (keyless).
- **Automations (your daily loop):** morning brief (weather → calendar → triage), **email
  triage** (ranks urgent + real people, files into your labels, auto-drafts), birthday
  reminders, **evening prep** (tomorrow + calendar-conflict alerts), **follow-up nudges**
  (catches dropped threads; silent by default).
- **Core:** profile-driven config (`profile.yaml`); two-tier living **memory** (`USER.md`
  digest + on-demand detail); persona + hard rules (`SOUL.md`).
- **Onboarding / deploy tooling:** one-command `bootstrap` · `provision` · `migrate-state` ·
  `setup-google` (OAuth-wall shrink) · `sync` (repo→VM deploy). Plus a copy-paste **plugin
  template** + [authoring guide](AUTHORING-PLUGINS.md).
- **Security:** VM execution with documented host-sharing limits, your own OAuth, ask-first policy on writes, secrets VM-only, two
  independent audits, and **automated secret scanning** (gitleaks — CI + pre-commit, keyless).

---

## Controlled execution implementation (opt-in; live migration pending)

The [control service](CONTROL.md) now provides SQLite-backed tasks/events, exact owner approvals,
restart recovery that holds uncertain submissions, pause/cancel/disconnect, approved memory,
and a bounded browser inspection/form path. Local fixture tests exercise a complete appointment
submission and restart/replay behavior. It requires a separate unprivileged agent identity for
real enforcement; the existing development VM is not automatically migrated. Owner approvals
use a private CLI or loopback web interface. Human login handoff pauses the agent, isolates
screenshots and credentials from its tools, and saves only the selected sites’ sessions.
General script-heavy automated tasks, real-provider login acceptance, verified chat approvals
and autonomous proactive notifications remain follow-up work. Live deployment is deferred
until a destination is available; no new host has been provisioned.

## Reliability implementation (acceptance still pending)
- Sync preflight validates profiles/catalog/jobs before writes; command failures return nonzero.
  Named Google MCP enablement is reconciled with gateway reload recovery.
- Bootstrap verifies each runtime stage and preserves existing credentials/profile on rerun.
- Core regression and site build/browser checks run in CI; operational health distinguishes
  configured connectors, failed jobs, and detected host shares.
- [Privacy boundaries](PRIVACY.md) are explicit. Shell capabilities still rely on agent policy.
- [Second-user fresh-account trial](ONBOARDING-TRIAL.md) remains **pending human participation**.

## 🎯 Current focus
Explore a persistent personal agent with local inference and owner-editable Obsidian
memory using the [local personal agent plan](LOCAL-AGENT-PLAN.md). Begin with grounded
conversation and durable drafts, then one explicitly enabled check-in. This remains
planned work; existing scheduled runs stay paused during development.

The ordered product milestones above set current priorities. The capability and distribution
items below are supporting work and backlog, not a parallel commitment to expand every feature.

### (2) More capable — do more for you
- **Location / Maps** ✅ **live (keyless — OSM Nominatim + OSRM, no key)** → **commute prep** in
  the morning brief: for today's located events, travel time from home + "leave by 2:38". The
  morning heads-up works today; real-time "leave now" alerts still want always-on. *(set your
  home coords in `connectors.location.home`.)*
- **Notes** ✅ **live (keyless, local markdown — Obsidian vault or a folder)** — capture ("note: …"
  → appends a dated line) + recall ("search my notes for …"). Append/create only, never edits.
- **Web actions:** the existing Hermes browser follows prompt-based approval policy. The new
  [controlled path](CONTROL.md) supports bounded form inspection and approved submission with
  code enforcement. Chromium fixture tasks run below a second on the reference Linux VM;
  earlier slow raw-tool runs do not establish a GPU requirement. Real-site completion,
  interactive login and script-heavy applications remain acceptance work.
- **Tasks / to-do** ✅ **live (keyless, local markdown checkboxes)** — "add X to my tasks",
  "what's on my list?", "mark X done". Append/tick only, never deletes. (Google Tasks/Todoist
  are possible future backends.)
- **Meeting prep** ✅ **live** — for the day's real meetings (≥ min_attendees or a video link):
  who's attending, your last thread with them, any doc/location. Silent on meeting-free days.
- **Weekly review** — Sunday: the week ahead + what slipped.

### (3) Spreadable — let others use it
- **Onboarder v2** — make the AI-agent onboarder genuinely launchable + robust (v1 is a scaffold).
- **Real end-to-end onboarding test** — prove the fresh-install path *with* the human steps
  (Google OAuth, Signal registration), not just the deterministic install.
- **Plugin ecosystem** — a publishing path + a few flagship community plugins.
- **Public quickstart / demo** — a crisp "0-to-running" guide (+ a README demo).

---

## Backlog (the full menu)

### A. Reliability
- **Always-on hosting** — move off the laptop so proactivity fires reliably (tooling ready;
  needs a spare Mac / box / cloud VM). Then health/status checks + graceful recovery.
- **Cron tidy-up** ✅ birthday reminder now defaults to 08:30, separate from the brief.

### B. More connectors (what it can access)
- Location/Maps · Notes (Notion/Obsidian) · Tasks · Flights/travel · Finance
  (spending awareness — sensitive; supports ethical-finance constraints).

### C. More automations (what it does proactively)
- Commute/meeting prep · weekly review · commitment extraction (deadlines/promises from email) ·
  goal/project nudges (tied to your `USER.md` focus) · smarter triage (learns your corrections).

### D. Intelligence — make it know you
- Auto-learning memory (build your profile + tone from usage) · cross-conversation context.

### E. Channels — how you reach it
- **iMessage** (BlueBubbles — bridge prepped) · Telegram / WhatsApp / Slack · voice
  (voice notes in, spoken replies).

### F. Bespoke personal helpers (high personal value)
- Event/trip planning, a copilot for your own projects, or a work assistant — configured per
  user. Anything sensitive or regulated (e.g. health/PHI) stays private and handled carefully.

### G. Execution + trust standard (the category frontier)
- **Web actions** — headless-browser automation in your VM (bookings, checkout, flight check-in,
  shopping); always **stop before any charge or identity step** and hand back for a "yes".
- **Tap-to-approve payments** — a tokenized/virtual card + one-tap approval for the exact amount,
  so a merchant never sees your real card.
- **Wallet passes** — deliver boarding passes / tickets as Apple Wallet passes.
- **Proactive watching** — sit on a thread or a page and alert the moment something changes (a
  reply lands, a price drops, a booking window opens). Extends follow-up nudges.
- **Trust standard** — read the live source before acting; cite claims with links; route
  sensitive data (passport, card) through a secure fill-in link, never the chat thread.
- **Human escalation** — when it genuinely doesn't know, route the question to a human and bring
  back the answer, instead of guessing.

### H. Growth (distribution mechanics)
- Invite-link virality (existing users invite others), waitlist/early-access framing, and a
  "test me cheap on something low-stakes" trust-building onboarding.

---

## Guardrails (always)
Least-privilege scopes, ask-first on any action, secrets stay in your VM, quiet hours + soft
rate limits on anything proactive, and every commit secret-scanned.
