# Authoring a plugin

Everything a user can add is a **plugin** — and adding one is meant to be a copy-paste job. You
declare *what it needs, its security posture, and its setup recipe*; the AI onboarder handles
install, dependency resolution, and settings. This guide gets you from zero to a working plugin.

## The three kinds
- **Channel** — *how they reach it* (Signal, iMessage, Telegram). `hermes.kind: platform`.
- **Connector** — *what it can access* (Gmail, Calendar, Notion). `hermes.kind: mcp`. Ships a
  `recipe.md`.
- **Automation** — *what it does proactively* (morning brief, triage). `hermes.kind: cron`. Ships
  a `prompt.md` and usually `requires` a connector.

## Quickstart (~5 minutes)
1. **Copy the template** into the right category folder:
   ```bash
   cp -r plugins/_template plugins/<category>/<your-id>     # category = channels | connectors | automations
   ```
2. **Fill `plugin.yaml`** — id, name, summary, `requires`, `security`, `setup`, `settings`,
   `hermes`. Keep the lines for your category, delete the rest.
3. **Add the detail file** — `recipe.md` for a connector/channel, `prompt.md` for an automation.
   (Delete the one you don't need.)
4. That's it — the onboarder now discovers it in the catalog and can offer + install it. Add a
   one-line entry to [`../plugins/README.md`](../plugins/README.md).

## The contract (what the onboarder executes)
Each `plugin.yaml` follows the [architecture contract](ARCHITECTURE.md#the-plugin-contract). The
heart of it is the **`setup` recipe** — ordered steps, each one of:
- **`auto:`** a command the onboarder runs in the VM itself.
- **`human:`** an irreducible human step (approve OAuth, solve a captcha, provide a key) — the
  onboarder gives clear instructions and waits.
- **`verify:`** a check that *proves* the step worked — the onboarder won't proceed until it passes,
  and self-heals if it fails.

Include a `verify` for every meaningful step. That's what makes onboarding adaptive instead of a
brittle wizard.

## Security rules (non-negotiable)
Every plugin MUST:
- default to **least-privilege** scopes and **read-only** where possible;
- set **`ask_first: true`** for anything that writes or acts — and if some write is allowed
  unprompted, list it under `unprompted:` and justify it in `notes:`;
- keep all secrets in the user's VM (`secrets_location: vm`, chmod 600) — **never in this repo**
  (placeholders only: `sk-ant-…`, `+1XXXXXXXXXX`);
- state `send`/`delete` posture explicitly if the underlying tool *could* do them, and explain
  what actually prevents it (usually: no such tool is exposed).

See [`../config/SOUL.md`](../config/SOUL.md) for the hard rules the agent enforces at runtime.

## Settings + the profile
Whatever you put under `settings:` becomes this plugin's block in the user's
[`profile.yaml`](PROFILE.md) (e.g. `automations.<your-id>.*` or `connectors.<your-id>.*`). Your
`prompt.md`/`recipe.md` reads those keys at runtime — spell them identically everywhere.

## Test it
- **Deploy** your changes into a running VM: `./scripts/sync.sh --apply` (deploys prompts + SOUL,
  reports drift). See [`../scripts/sync.sh`](../scripts/sync.sh).
- **Automations:** dry-run with `hermes cron run <your-id>` in the VM, then read the output in
  `~/.hermes/cron/output/<job-id>/` and check tool errors in `~/.hermes/logs/errors.log`.
- **Connectors:** run your `verify` step (e.g. list something read-only).

## How the onboarder uses it
Discover (reads the catalog) → resolve dependencies (`requires.connectors`) → execute your
`setup` recipe (auto/human/verify) → write the user's profile → done. The full flow is in
[`../onboarder/playbook.md`](../onboarder/playbook.md).
