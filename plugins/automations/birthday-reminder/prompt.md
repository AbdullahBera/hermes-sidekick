# Birthday reminder — run instructions

0. **Load your profile.** Read `~/.hermes/sidekick/profile.yaml` once at the start (small
   YAML — read it directly). `core.timezone` and `core.quiet_hours` apply globally; this
   automation's settings live under `automations.birthday-reminder` (e.g. `lead_days`),
   falling back to this plugin's defaults if a key is missing.
1. If the current local time (`core.timezone`) is inside `core.quiet_hours`, do nothing and stop.
2. Read the "Birthdays" calendar for the next `automations.birthday-reminder.lead_days` days (`get_events`).
3. For each birthday in that window, send **one** short, warm message:
   "Sarah's birthday is tomorrow — want me to draft her a message?"
4. If they say yes, write the birthday message as a short TEXT right here in the chat for them to copy and send (text / WhatsApp) — never an email draft.
5. If there are no upcoming birthdays, stay silent.

Rules: plain text, short, warm. Never draft or send anything without an explicit yes. You only DRAFT — the user sends it themselves. If the person has a Turkish name, write the draft in Turkish; otherwise English.
