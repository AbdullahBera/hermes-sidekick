# Roadmap

hermes-sidekick is a private, self-hosted personal assistant you text — set up by an AI
onboarder, composed from opt-in plugins. It stays private and secure by construction (your VM,
your OAuth, no broker). This roadmap tracks what's shipped and where we're headed.

## Positioning (the wedge)
The category is converging on "act + remember + connected accounts" — that's now table stakes.
The frontier is **real execution** (driving a browser to do live web tasks) and a **trust
standard** (read the live source before acting, ask-first on money/identity, cite sources with
links, sensitive data through a secure link — never the chat). Our distinct wedge: deliver that
execution **privately, on infrastructure the user owns** — open, transparent, self-hosted — the
opposite of a hosted service that won't disclose where your data lives. Convenience is
commoditizing; **private, owned execution** is the defensible position.

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
- **Security:** isolated VM, your own OAuth, ask-first on writes, secrets VM-only, two
  independent audits, and **automated secret scanning** (gitleaks — CI + pre-commit, keyless).

---

## 🎯 Current focus
Two tracks, chosen deliberately: **(2) make it more capable** and **(3) make it spreadable**.

### (2) More capable — do more for you
- **Location / Maps** ✅ **live (keyless — OSM Nominatim + OSRM, no key)** → **commute prep** in
  the morning brief: for today's located events, travel time from home + "leave by 2:38". The
  morning heads-up works today; real-time "leave now" alerts still want always-on. *(set your
  home coords in `connectors.location.home`.)*
- **Notes** ✅ **live (keyless, local markdown — Obsidian vault or a folder)** — capture ("note: …"
  → appends a dated line) + recall ("search my notes for …"). Append/create only, never edits.
- **Web actions (private browser automation)** 🔨 **built** ⭐ — the agent drives a real browser
  **inside your VM** (Playwright/Chromium via `agent-browser`) to do live web tasks, **stopping
  before any charge or your-name step** (trust standard enforced in `SOUL.md`). Runs on infra *you
  own*; sensitive data never enters the thread. *Browser launches + drives Chromium (verified), but
  it's impractically slow on the GPU-less VM (software rendering) — needs a faster host or the
  Lightpanda engine to be usable. Guardrails + capability shipped; performance is the open item.*
- **Tasks / to-do** — Google Tasks / Todoist / Things — pull your to-dos into the day.
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
- **Cron tidy-up** — birthday-reminder shares 08:00 with the brief; shift to 08:30.

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
