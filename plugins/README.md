# Plugins

Each plugin is a self-contained unit the **AI onboarder installs** and a **contributor
authors**. Structure:

```
plugins/<category>/<id>/
  plugin.yaml     # manifest (structured)
  recipe.md       # detailed setup steps the onboarder runs
  prompt.md       # automations only: scheduled-run instructions
```

Categories:
- **channels/** — how you reach the agent (Signal, iMessage, Telegram…)
- **connectors/** — what it can access (Gmail, Calendar, …)
- **automations/** — what it does proactively (morning brief, birthday reminders…)

**Want to add one?** Copy [`_template/`](_template/) and follow
[../docs/AUTHORING-PLUGINS.md](../docs/AUTHORING-PLUGINS.md) (~5 min). The full plugin contract
and design are in [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md). The manifests here — **Signal, Gmail,
Calendar, Contacts** — are the reference examples: real, working setups distilled into the
contract. Copy one to author a new plugin. (**iMessage** and **Location** carry
`status: planned` — they describe intended setups, not verified ones.)

**Every plugin must:** default to least-privilege scopes, be read-only where possible, set
`ask_first: true` for anything that writes or acts, keep all secrets in the user's VM
(`secrets_location: vm`, never in this repo), and include a `setup:` block ending in a
`verify` step so the onboarder can confirm it worked. Automations are not exempt — their
verify step is a single by-hand run of `prompt.md`.
