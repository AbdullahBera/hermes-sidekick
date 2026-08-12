# Architecture

## What this is

**hermes-sidekick is a thin, security-first *product layer* — plus AI-driven onboarding —
on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.**

Hermes is the engine: the agent runtime, tool-calling, MCP integrations, messaging
gateway, cron scheduler, skills, and memory. hermes-sidekick doesn't reinvent any of
that — it **curates** it into a finished personal-assistant product that a
non-technical person can actually set up and use, with security as a visible,
first-class property.

We **curate; Hermes executes.**

### Built on Hermes (attribution)
This project is built on and depends on **Hermes Agent** (Nous Research), MIT-licensed.
All the heavy lifting — the agent loop, tools, MCP, gateway, crons — is Hermes. Please
support the upstream project. hermes-sidekick is likewise MIT (see `LICENSE`).

## What hermes-sidekick adds

On top of everything Hermes already does, this layer contributes:

- **AI-driven onboarding** — setup is a conversation; the onboarder does the work and
  only pauses for the few steps a human must do (approve an OAuth screen, solve a
  captcha, provide a key).
- **A curated, opt-in plugin catalog** — capabilities with dependencies resolved and
  sensible, safe defaults.
- **Security-first defaults, made visible** — least-privilege scopes, ask-first on any
  write, and every secret kept in the user's own VM.
- **A text-first personal-assistant experience** — a concise voice and proactive,
  opt-in life-management (morning brief, reminders).

The goal is simple: make a self-hosted Hermes assistant usable by someone who can't
(and shouldn't have to) open a terminal.

## Design principles

1. **Thin layer.** Curate and orchestrate Hermes; never fork or reimplement it.
2. **Everything is an opt-in plugin.** Nothing is forced on the user.
3. **Security is first-class and visible.** Least-privilege scopes, ask-first on any
   write/action, and every secret stays in the user's own VM — never in this repo,
   never brokered by a third party unless the user knowingly chooses it.
4. **AI does the onboarding.** The installer is a conversation, not a manual — and it's
   adaptive and self-healing (it can diagnose and fix failures a static wizard can't).
5. **The user owns everything.** Runtime and secrets live in an isolated VM on their
   machine.

## The layers

```
        You (texting)
            │
   ┌────────▼─────────┐   Channel plugin  (Signal / iMessage / Telegram …)
   │  hermes-sidekick │ ─ Connector plugins (Gmail / Calendar / …  → MCP)
   │   PRODUCT LAYER  │ ─ Automation plugins (morning brief / birthdays → cron)
   │                  │ ─ Catalog · Profile · AI Onboarder · plugin contracts
   └────────┬─────────┘
            │  configures / drives
   ┌────────▼─────────┐
   │   HERMES ENGINE  │   agent loop · tools · MCP · gateway · cron · skills · memory
   └────────┬─────────┘
            │
     Claude (model) · the user's isolated VM (all secrets, chmod 600)
```

## Plugin model

Everything a user might want is a plugin in one of three categories, plus base config:

- **Channels** — *how they reach it.* Signal, iMessage, Telegram, WhatsApp, Web. Pick ≥1.
- **Connectors** — *what it can access.* Gmail, Calendar, Contacts, Tasks, Notion… Each
  opt-in, each with its own security scope.
- **Automations** — *what it does proactively.* Morning brief, birthday reminders, email
  triage, calendar prep. Opt-in, scheduled, quiet-hours aware. Automations **depend on**
  connectors (birthday reminder → calendar).
- **Core config** — model, personality/voice, quiet hours, rate limits.

### Two files make it customizable
- **Catalog** (in this repo, public): every available plugin and its contract. The
  onboarder reads it to know what to offer and how to install each.
- **Profile** (per-user, in their VM): which plugins they enabled + their settings. This
  *is* the customization; the onboarder generates it from a conversation and can toggle
  it later.

### How it maps to Hermes (real, not vapor)
- **Channel** → a Hermes gateway platform (already modular)
- **Connector** → a Hermes MCP server (`hermes mcp add/remove/configure`) + an OAuth recipe
- **Automation** → a Hermes cron job + a skill/prompt (+ memory)

A hermes-sidekick plugin is a *thin bundle*: a manifest + a setup recipe + the config it
writes into Hermes.

## The plugin contract

Every plugin is a self-contained folder under `plugins/<category>/<id>/` with a
`plugin.yaml` manifest. This contract is the spec **plugin authors build against** and
**the AI onboarder executes**.

```yaml
id, name, summary, category            # identity
requires:
  connectors: []                       # deps on other plugins (resolved automatically)
  human: []                            # irreducible human steps (OAuth approve, captcha, API key…)
security:
  scopes: []                           # least-privilege by default
  writes: []                           # what it can change (empty = read-only)
  ask_first: true                      # never act without explicit confirmation
  secrets_location: vm                 # secrets live only in the user's VM
setup: []                              # ordered steps: {auto|human|verify}
settings: {}                           # user-tunable options
hermes: {}                             # which Hermes primitive it wires (mcp | platform | cron)
```

### Example — a Connector (`plugins/connectors/gmail/plugin.yaml`)
```yaml
id: gmail
name: Gmail
category: connector
summary: Read and draft email. Never sends.
requires:
  human: [google_oauth_client, oauth_consent]
security:
  scopes: [gmail.readonly, gmail.labels, gmail.compose]
  writes: [draft, label]
  ask_first: true            # confirm before any draft/label change
  send: false                # no send tool exists, ever
  secrets_location: vm       # ~/.hermes/google-workspace (chmod 600)
setup:
  - human:  "Enable Gmail API + create a Desktop OAuth client (guided), download JSON"
  - auto:   "uv tool install workspace-mcp (in the VM)"
  - human:  "Approve the OAuth consent screen in your browser"
  - auto:   "hermes mcp add gmail --permissions gmail:drafts"
  - verify: "list_gmail_labels returns your labels"
settings:
  important_senders: []
  summary_style: concise
hermes: { kind: mcp, server: workspace-mcp }
```

### Example — an Automation (`plugins/automations/birthday-reminder/plugin.yaml`)
```yaml
id: birthday-reminder
name: Birthday reminders
category: automation
summary: Texts you before a contact's birthday and offers to draft a message.
requires:
  connectors: [calendar]     # needs calendar read; onboarder enables it first
security:
  ask_first: true            # offers to draft; never sends
settings:
  lead_days: 1
  quiet_hours: "22:00-07:00"
hermes: { kind: cron, schedule: "daily 08:00" }
```

## The AI onboarder

The onboarder is the "installer," and it's a conversation:

1. **Discover** — reads the catalog, asks the user what they want (channel, connectors,
   automations) in plain language.
2. **Resolve** — pulls in dependencies automatically (enable birthday reminders → it also
   sets up Calendar).
3. **Execute** — runs each chosen plugin's `setup` recipe: does the `auto` steps itself,
   pauses at `human` checkpoints with clear instructions, and runs `verify` after each.
4. **Self-heal** — if a step fails, it diagnoses and fixes (e.g. the arm64 libsignal
   patch) instead of dead-ending.
5. **Persist** — writes the user's Profile (enabled plugins + settings) into the VM.

**Irreducible human checkpoints** (the onboarder guides, but a person must do these):
approve an OAuth consent screen, solve a messaging captcha / provide a number, supply
an API key or payment, grant OS permissions, install system software needing admin.
Everything else is automated.

## Building a plugin (for contributors)

Add `plugins/<category>/<id>/plugin.yaml` conforming to the contract above. The onboarder
handles install, dependency resolution, and settings — you just declare **what it needs,
its security posture, and the setup recipe.** Every plugin MUST:
- default to **least-privilege** scopes and **read-only** where possible,
- set **`ask_first: true`** for anything that writes or acts,
- keep all secrets in the user's VM (`secrets_location: vm`) — never in the repo,
- include a **`verify`** step so the onboarder can confirm it worked.

## Security model (summary)
- All runtime + secrets live in the user's **isolated VM** (chmod 600); nothing sensitive
  in this public repo (enforced — see `CLAUDE.md` and the pre-push scans).
- Connectors default to **least-privilege, read-first**; writes require **ask-first**.
- No third party brokers user data unless the user knowingly picks a plugin that does.
- The catalog surfaces each plugin's posture so users choose their exposure with eyes open.

---
*Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research, MIT). Thank you to that project.*
