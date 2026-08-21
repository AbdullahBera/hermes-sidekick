# The AI onboarder

The onboarder is how a non-technical person sets up hermes-sidekick: **a conversation, not
a manual.** It's an AI agent that does the technical work itself and pauses only for the few
things a human must do (approve an OAuth screen, solve a captcha, provide a key).

It:
- reads the plugin catalog ([`../plugins/`](../plugins/)) and each plugin's detailed recipe
  (its `recipe.md`),
- talks the user through what they want, resolves dependencies, runs each chosen plugin's
  `setup`, **verifies every step**, self-heals failures, and
- writes the user's [profile](../docs/PROFILE.md) as the source of truth.

The exact instructions the onboarding AI follows are in [`playbook.md`](playbook.md). It runs
as a Claude/Hermes agent with shell access to the user's **isolated VM** — the same shape
that set up the reference deployment, now codified so it repeats for anyone.

## Running it (today)
**One command:** [`bootstrap.sh`](bootstrap.sh) provisions the runtime (OrbStack + VM + Hermes),
stages this repo and your model key into the VM, and hands you to the onboarder. The onboarder
itself is a playbook an agent executes — either the Hermes agent in the VM, or a coding agent
(e.g. Claude Code) pointed at this repo: it loads `playbook.md`, reads the catalog, and walks
the user through setup, pausing only for human checkpoints.
