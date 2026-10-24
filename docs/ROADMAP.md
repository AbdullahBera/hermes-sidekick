# Roadmap

hermes-sidekick aims to be a personal assistant people can text, running on hardware they
control. It should remember useful context, complete everyday tasks and follow up with
permission. Ownership must come with a usable product: guided setup, clear controls,
reliable execution and straightforward recovery. This roadmap separates what is implemented
from what is planned.

## Product direction

**Local-first: a private assistant whose personal data stays on the owner's devices.**

A local model coordinates the assistant and handles personal conversations, records, memory
and embeddings. Public knowledge comes from minimal web searches. Hosted models are used only
for explicit, narrow exceptions: coding work delegated to Claude Code, and general questions
the owner routes to Claude by hand. Privacy is enforced by OS accounts, network rules and
brokers, not by instructions to the model. The design, trust zones and handoffs are in the
[local-first plan](LOCAL-AGENT-PLAN.md); the tests are in [LOCAL-AGENT-TESTS.md](LOCAL-AGENT-TESTS.md).

**Today's reference deployment is not local-first.** It sends conversations and retrieved
context to a hosted model (Claude through the direct Anthropic provider), and its VM has host
filesystem shares. [PRIVACY.md](PRIVACY.md) describes the current data flows.

Keep Hermes as the execution engine. Build the missing privacy boundaries, controls, approvals
and recovery around it, and reuse the controlled task service where it fits.

## Milestones, in order

| Phase | Milestone | Status |
| --- | --- | --- |
| 0 | Decide and measure: model benchmarks (MLX first), memory budget including Sim, verified assumptions, reconciled docs | **Done** (2026-10-24): Qwen3.6-35B-A3B on mlx-lm; memory headroom is a Phase 1 constraint |
| 1 | Private local core: isolated VM, local inference, local-only Hermes, owner-only Signal | Planned |
| 2 | Research gateway: search broker, query rules, taint rule, explicit Claude questions | Planned |
| 3 | Coding bridge: Signal → Claude Code in a local Conductor workspace → handoff | Planned |
| 4 | Real personal data, one category at a time | Planned |
| 5 | Sim workflows, private tier, local models only | Planned |
| 6 | Agent-drafted workflows with approval-bound deployment | Planned |
| 7 | Sim external integrations, one at a time | Planned |

Each phase ends with a gate that includes the privacy regression suite. Existing scheduled
routines stay paused throughout; enabling any trigger is an explicit owner choice.

### Carried forward from the previous plan
These milestones remain valid but now sit behind the local-first phases:
- **Repeatable deployment on a user-managed host,** with guided configuration, health checks,
  backup/restore and upgrade/rollback, and the [fresh-account second-user trial](ONBOARDING-TRIAL.md).
- **Useful browser execution:** measure the controlled browser's latency and failure modes on
  real sites, with secure login handoff and approval before submission.
- **Three complete daily workflows:** calendar options with approved event creation, meeting
  preparation, and an approved appointment booking on a real site. Measure correctness, time,
  cost and human intervention.

## Shipped ✅
- **Channel:** Signal. **Model (current):** Claude Sonnet 5 via the direct Anthropic provider.
  **Voice:** concise, human, text-native; matches your tone (Turkish for Turkish names).
- **Connectors:** Gmail (read, draft, label-sort; never sends), Calendar (read and write,
  ask-first), Contacts (read), keyless web search and research, read-url, location and commute
  prep (OpenStreetMap Nominatim and OSRM), weather, translation, places, local Markdown notes
  (append and search) and checkbox tasks (add, list, done).
- **Automations:** morning brief, email triage, birthday reminders, evening prep, follow-up
  nudges, meeting prep. Live scheduled runs are paused during development.
- **Core:** profile-driven configuration (`profile.yaml`), two-tier memory (`USER.md` digest
  plus on-demand detail), persona and hard rules (`SOUL.md`), a plugin template and
  [authoring guide](AUTHORING-PLUGINS.md).
- **Onboarding and deployment tooling:** `bootstrap`, `provision`, `migrate-state`,
  `setup-google`, `sync` (validated, idempotent repo-to-VM deployment), read-only `status`
  health checks with host-share detection.
- **Controlled task service ([CONTROL.md](CONTROL.md), opt-in):** SQLite tasks and events,
  exact expiring owner approvals, restart recovery that holds uncertain submissions,
  duplicate prevention, pause/cancel/disconnect, approved memory, a bounded browser form path,
  an owner CLI and loopback UI, and private login handoff. It requires a separate agent OS
  identity for enforcement; the development VM has not been migrated.
- **Security:** secrets kept in the VM, own OAuth clients, ask-first write policies, two
  independent audits, automated secret scanning (gitleaks in CI and pre-commit), and
  [documented capability boundaries](PRIVACY.md).
- **Local-first Phase 0 tools:** synthetic persona pack, query-rule checker, local model
  benchmark harness, read-only Mac host baseline.

## Pending acceptance
- Second-user fresh-account trial (needs a human participant).
- Real-site browser tasks, interactive real-provider login, script-heavy applications.
- Authenticated chat approvals and autonomous proactive notifications.
- Live isolation: shell capabilities in the current deployment still rely on agent policy.

## Backlog
Ideas that follow the milestones above. Each one must fit the local-first boundaries: personal
data processed locally, and any new outbound flow documented and controlled.

- **More connectors:** flights and travel; finance and spending awareness (Phase 4 rules apply).
- **More automations:** weekly review, commitment extraction, goal and project nudges, triage
  that learns from corrections.
- **Memory:** learning preferences from corrections, cross-conversation context, an
  owner-editable Obsidian vault as memory.
- **Channels:** iMessage (BlueBubbles, bridge prepared), Telegram, WhatsApp, Slack, voice.
- **Execution and trust:** broader web actions that stop before any charge or identity step,
  tap-to-approve payments with virtual cards, Wallet passes, proactive watching of a page or
  thread, human escalation when the agent does not know.
- **Spreadable:** a working onboarder v2, a real end-to-end onboarding test, a plugin
  publishing path, a public demo, invite-based growth.
- **Bespoke helpers:** event and trip planning, a copilot for the owner's own projects, a work
  assistant, configured per user.
- **Multiple agents:** parallel coding workers in separate workspaces with controlled
  integration, after one coordinator and one worker are dependable.

## Guardrails (always)
Least-privilege access, ask-first on consequential actions, personal data and secrets on the
owner's devices, quiet hours and rate limits on anything proactive, and every commit
secret-scanned.
