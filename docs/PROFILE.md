# Profile — the per-user config

The **profile** is the single source of truth for *what a given user enabled and how*. The
AI onboarder generates it from a conversation; Hermes and the automations read it.

- **Lives in the user's VM** at `~/.hermes/sidekick/profile.yaml` — never in this repo.
- **Contains no secrets.** Credentials stay in their own stores (`~/.hermes/.env`, the
  connector credential dirs). The profile records *choices and settings* only.
- **To change something:** toggle it here and re-run that plugin's recipe.

## Schema

```yaml
version: 1

core:
  model: claude-sonnet-5         # claude-sonnet-5 | claude-opus-4-8 | claude-haiku-4-5
  timezone: America/Los_Angeles
  quiet_hours: "22:00-07:00"     # no proactive messages inside this local window
  rate_limit_per_day: 6          # max proactive messages/day

channels:                        # exactly one is typically enabled
  signal:
    enabled: true
    allowed_users: ["+1XXXXXXXXXX"]  # your personal number(s), E.164
    home_channel: "+1XXXXXXXXXX"     # where proactive messages are delivered (you)
    reactions: false

connectors:
  gmail:
    enabled: true
    important_senders: []
    summary_style: concise
  calendar:
    enabled: true
    default_calendar: primary

automations:
  morning-brief:
    enabled: true
    time: "08:00"
    include: [calendar, email]
  birthday-reminder:
    enabled: false
    lead_days: 1
```

## How it's used
- **Onboarder** — writes it as the final step of setup, and edits it when the user toggles things.
- **Channels / connectors** — their `enabled` flags mirror what was wired into Hermes.
- **Automations** — each reads its schedule + settings, and every automation obeys
  `core.quiet_hours` and `core.rate_limit_per_day`.

A ready-to-copy example is in [`../profile.example.yaml`](../profile.example.yaml).
