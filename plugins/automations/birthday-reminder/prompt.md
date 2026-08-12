# Birthday reminder — run instructions

1. If the current local time is inside `core.quiet_hours`, do nothing and stop.
2. Read the "Birthdays" calendar for the next `settings.lead_days` days (`get_events`).
3. For each birthday in that window, send **one** short, warm message:
   "Sarah's birthday is tomorrow — want me to draft her a message?"
4. If they say yes **and** the gmail connector is enabled, draft it (never send). Otherwise
   just remind.
5. If there are no upcoming birthdays, stay silent.

Rules: plain text, short, warm. Never draft or send anything without an explicit yes.
