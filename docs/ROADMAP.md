# Roadmap

hermes-sidekick is a private, self-hosted personal assistant you text — set up by an AI
onboarder, composed from opt-in plugins. It stays private and secure by construction (your VM,
your OAuth, no broker). This roadmap tracks what's shipped and where we're headed.

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
- **Location / Maps (OpenRouteService, free)** → **commute prep** — "your 3pm is ~25 min away,
  leave by 2:40." The flagship. The morning-heads-up version works without always-on. *[next up]*
- **Notes — Notion + Obsidian** — surface/search your notes, capture new ones. (You live in both.)
- **Tasks / to-do** — Google Tasks / Todoist / Things — pull your to-dos into the day.
- **Meeting prep** — before a meeting: who's attending, last thread with them, relevant doc.
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
- Location/Maps · Notes (Notion/Obsidian) · Tasks · Flights/travel (you build a flight app) ·
  Finance (spending awareness — sensitive; halal/riba-aware).

### C. More automations (what it does proactively)
- Commute/meeting prep · weekly review · commitment extraction (deadlines/promises from email) ·
  goal/project nudges (tied to your `USER.md` focus) · smarter triage (learns your corrections).

### D. Intelligence — make it know you
- Auto-learning memory (build your profile + tone from usage) · cross-conversation context.

### E. Channels — how you reach it
- **iMessage** (BlueBubbles — bridge prepped) · Telegram / WhatsApp / Slack · voice
  (voice notes in, spoken replies).

### F. Bespoke to you (high personal value)
- Wedding-planning assistant (Istanbul venue, timeline, vendor follow-ups) · flight-app
  copilot · work helper (Aware Health — ⚠️ HIPAA/PHI, keep bespoke + careful).

---

## Guardrails (always)
Least-privilege scopes, ask-first on any action, secrets stay in your VM, quiet hours + soft
rate limits on anything proactive, and every commit secret-scanned.
