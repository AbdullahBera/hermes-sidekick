# Working guidelines for hermes-sidekick

This repository is currently **private** but is intended to be **open-sourced**.
**Treat everything here as if it were already public** — write and review every
file and commit to that standard, starting now.

## Public-ready rules (always)
- **No secrets, ever.** API keys, tokens, passwords, and account credentials live
  only in the VM's `~/.hermes/.env` (chmod 600) — never in this repo. Use
  placeholders in docs and examples (`sk-ant-...`, `+1XXXXXXXXXX`).
- **No personal data / PII.** No real phone numbers, emails, private IPs that
  locate a person, or message content. Redact backups before they land here.
- **Every commit is world-readable and permanent.** Don't write anything in code,
  comments, docs, or commit messages you wouldn't publish publicly under your name.
- **Scan before every push** — working tree *and* full git history — for keys,
  numbers, and credentials. New files start placeholder-only.

## Quality (public-project standard)
- README and docs should make sense to a stranger; explain the "why," not just the
  "how" (see `docs/DECISIONS.md`).
- Small, focused commits with clear messages.
- Scripts are self-contained, documented, and safe to run; prefer variables/env
  over hardcoded personal paths.
- Keep the layout clean and conventional: `docs/`, `scripts/`, `README`, `LICENSE`,
  `.env.example`.

## Security is the top priority
When in doubt, choose the more private/secure option, and confirm before anything
leaves the machine. All real infrastructure and secrets stay in the VM, not here.
