# Profile — the per-user config

The **profile** is the single source of truth for *what a given user enabled and how*. The
AI onboarder generates it from a conversation; Hermes and the automations read it.

- **Lives in the user's VM** at `~/.hermes/sidekick/profile.yaml` — never in this repo.
- **Contains no secrets.** Credentials stay in their own stores (`~/.hermes/.env`, the
  connector credential dirs). The profile records *choices and settings* only.
- **To change something:** toggle it here and re-run that plugin's recipe.

The **canonical schema is [`../profile.example.yaml`](../profile.example.yaml)** — copy it
and fill it in. This doc explains what each section *means*; the example is the shape.

> The profile is config only. The separate, *living* "about you" memory the assistant
> learns over time lives in `USER.md` (a Hermes memory) — see [MEMORY.md](MEMORY.md).

## Field reference

- **`core`** — global settings every automation honors.
  - `model` — which Claude model runs (`claude-sonnet-5` | `claude-opus-4-8` | `claude-haiku-4-5`).
  - `timezone` — IANA tz; all "today"/"local time" logic uses it.
  - `quiet_hours` — `"HH:MM-HH:MM"` local window in which **no** proactive message is sent.
  - `rate_limit_per_day` — a **soft** daily ceiling on proactive messages. It's a judgment
    guide, not a hard counter (there's no enforced tally) — the assistant errs toward
    silence when nothing matters rather than counting.

- **`channels`** — how the user reaches the assistant (typically exactly one enabled).
  Each has `enabled`, `allowed_users` (E.164 numbers that may talk to it), and
  `home_channel` (where proactive messages are delivered). `signal` is live; `imessage`
  is planned (needs an always-on Mac + a secondary Apple ID).

- **`connectors`** — what the assistant can access. Each has `enabled` mirroring what was
  wired into Hermes, plus its own settings:
  - `gmail` — `important_senders` (who to prioritize), `summary_style`, and `triage`: how the
    email-triage automation sorts your inbox — `file_into` (Gmail label names it may ADD to
    messages; mail stays in the inbox), `create_missing` (create a mapped label if absent),
    and `hints` (a one-liner mapping label → what belongs in it). Requires the connector's
    `gmail.modify` scope; label writes are confined to these labels by a hard rule.
  - `calendar` — `default_calendar`. Create/edit is granted but always ask-first.
  - `contacts` — read-only; also populates Google's "Birthdays" calendar.
  - `location` — planned (free OpenRouteService key); `units`, `home_address` for
    "how far" / "leave by" calculations.

- **`automations`** — what the assistant does proactively. Each has `enabled` and its own
  settings (e.g. morning-brief `time` + `include` + a `weather` block with
  `latitude`/`longitude`/`units` (keyless open-meteo); birthday-reminder `time` + `lead_days`;
  email-triage `run` + `lookback` + `max_items` + `auto_draft`). Put `weather` in
  morning-brief's `include` to get a forecast line.
  These are the user's *actual* values — they override the defaults declared in each
  plugin's `plugin.yaml`.

## How it's used at runtime

- **Onboarder** — writes the profile as the final step of setup, and edits it when the user
  toggles things.
- **Automations** — each run **loads `~/.hermes/sidekick/profile.yaml` first** (step 0 of
  its `prompt.md`), then honors `core.*` (timezone, quiet_hours) plus its own
  `automations.<id>` block and any `connectors.*` settings it needs. Missing keys fall back
  to the plugin's declared defaults.
- **Channels / connectors** — their `enabled` flags mirror what was wired into Hermes.
