# Roadmap

hermes-sidekick is a private, self-hosted personal assistant you text — set up by an AI
onboarder, composed from opt-in plugins. This roadmap is oriented around one goal:
**make it genuinely proactive in your day-to-day**, while staying private and secure.

## Shipped
- **Channel:** Signal. **Model:** Claude Sonnet 5. **Voice:** concise, human, text-native,
  matches your tone (and writes Turkish for Turkish names).
- **Connectors:** Gmail (read + draft + label-sort, never send), Calendar (read + write,
  ask-first), Contacts (read).
- **Web search** (keyless).
- **Automations:** morning brief; birthday reminders (draft-only, you send).
- **Memory:** a living, two-tier "about you" — a small always-on digest (`USER.md`) plus
  on-demand detail (`USER_DETAIL.md`); learns durable facts, ask-first on anything private
  (see [MEMORY.md](MEMORY.md)).
- **Security:** isolated VM, your own OAuth clients, ask-first on any write, secrets VM-only,
  public repo scanned clean.

## Now / Next — proactivity for day-to-day
The theme: it tells you the right thing at the right time, and handles the follow-up (ask-first).
- **Location & Maps** (OpenRouteService — free, no card): addresses, distances, ETAs,
  and "leave by X to make your 3pm." → `plugins/connectors/location`
- **Meeting & commute prep:** before an event, a heads-up with location, travel time, and
  what you need to bring.
- **Calendar-conflict alerts:** ✅ live (in evening prep) — flags double-bookings + tight back-to-backs for tomorrow.
- **Email triage:** ✅ **live** — files your inbox into your own Gmail labels, surfaces only what
  needs you, and auto-drafts replies (never sends). Folds into the morning brief (check-in
  triggered). Deployed via `scripts/sync.sh` and verified end-to-end.
- **Evening prep:** ✅ live — an evening look at tomorrow (first event, conflicts, early starts,
  prep) + "anything to sort tonight?". A second daily touchpoint alongside the morning brief.
- **Follow-ups & nudges:** ✅ live — catches real-people emails you received days ago and haven't
  answered; offers a draft. Silent unless something's genuinely dropped.
- **Profile-driven config:** automations read `profile.yaml` (quiet hours, what to include)
  so proactivity is tuned to you.

## The moat — one-command onboarding
- **AI onboarder bootstrap:** a single command installs the runtime and launches the
  onboarder, which sets all this up for anyone — non-technical.

## Dependability
- **Always-on hosting:** run the VM on an always-on box or optional cloud deploy so it
  doesn't stop when your laptop sleeps.
- Health/status checks and graceful recovery.

## More connectors
- **Tasks / to-do** and **Notes** — pull your to-dos and notes into the day.
- **iMessage** (BlueBubbles) — when a spare Apple ID + always-on Mac are available (the
  network bridge is already prepped).

## Later
- **Memory that learns you** — auto-build your profile + tone from how you use it.
- **Plugin publishing** — a clean path for others to contribute plugins.

## Guardrails (always)
Least-privilege scopes, ask-first on any action, secrets stay in your VM, and quiet hours +
rate limits on anything proactive.
