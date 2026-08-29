# Quickstart — 0 to a private assistant you text

By the end you'll have a **personal assistant you text on Signal**, running in an **isolated VM
on your own machine** — your data, your OAuth, no third-party broker. Budget **~20–30 minutes**.
This is written for someone **comfortable in a terminal** (the truly non-technical, one-command
flow is a work in progress — see [ROADMAP](ROADMAP.md)).

## What you need
- A **Mac** with **[OrbStack](https://orbstack.dev)** (`brew install --cask orbstack`) — the VM
  runtime. *(A Linux host also works; see [DEPLOY.md](DEPLOY.md).)*
- An **Anthropic API key** (console.anthropic.com → API Keys).
- A **phone number for Signal** you can receive a code on (a spare/Google Voice number is fine).

## The flow
Two layers do the work: **`bootstrap.sh`** stands up the runtime, then the **AI onboarder**
walks you through the rest (it does the technical steps and pauses only for the few a human must
do — OAuth approval, a Signal captcha, your key).

### 1. Stand up the runtime (one command)
```bash
git clone https://github.com/AbdullahBera/hermes-sidekick && cd hermes-sidekick
./onboarder/bootstrap.sh
```
This installs OrbStack's VM → Hermes → clones this repo into the VM → asks for your Anthropic key
(stored **only** in the VM, chmod 600). Idempotent — safe to re-run.

### 2. Connect Signal (how you'll text it)
Register a Signal number for the assistant (the one human step here — it may need a captcha).
Follow [`plugins/channels/signal/recipe.md`](../plugins/channels/signal/recipe.md). Once done,
you text that number and it replies.

### 3. Connect Google (Gmail / Calendar / Contacts)
This is the one real friction wall (creating your *own* OAuth client — the price of no broker).
It's guided:
```bash
./scripts/setup-google.sh    # scripts the project + APIs via gcloud, deep-links the console clicks
```
It stages your `client_secret.json` into the VM; then mint the token (browser approve, one time)
per [`plugins/connectors/gmail/recipe.md`](../plugins/connectors/gmail/recipe.md).

### 4. Make it yours (the profile)
Your settings live in `~/.hermes/sidekick/profile.yaml` **in the VM** (never the repo). Copy
[`profile.example.yaml`](../profile.example.yaml) and set your timezone, quiet hours, important
senders, home coords, notes path, and which automations you want. See [PROFILE.md](PROFILE.md).
*(The onboarder can write this for you from a conversation.)*

### 5. Deploy + verify
```bash
./scripts/sync.sh --apply    # deploys SOUL.md + automation prompts into the VM, reloads the gateway
```
Text your assistant "what can you do?" — or wait for the **8am morning brief** (weather + calendar
+ triaged inbox).

## Customize + extend
- **Tune it:** edit `profile.yaml` (VM), then `./scripts/sync.sh --apply`.
- **Add a plugin** (channel / connector / automation): copy `plugins/_template/` and follow
  [AUTHORING-PLUGINS.md](AUTHORING-PLUGINS.md) (~5 min).
- **What's built + what's next:** [ROADMAP.md](ROADMAP.md). **How it works:** [ARCHITECTURE.md](ARCHITECTURE.md).

## Honest notes
- **Human checkpoints** (unavoidable, guided): approving Google's OAuth screen, the Signal
  captcha/number, your API key. Everything else the tooling/onboarder does.
- **Always-on:** proactive messages (morning brief, etc.) only fire **while your Mac is awake**.
  To make them reliable, move the VM to an always-on host — [DEPLOY.md](DEPLOY.md) (tooling ready).
- **Web actions** (browser automation) work but are slow on a GPU-less VM — see the
  [web-actions recipe](../plugins/connectors/web-actions/recipe.md).

## Privacy (by construction)
Secrets and personal data live **only in the VM** (`~/.hermes/`, chmod 600); the repo carries
placeholders only. Your own OAuth clients, no third-party broker, and every commit is
secret-scanned (gitleaks). See [Security](../README.md#security).
