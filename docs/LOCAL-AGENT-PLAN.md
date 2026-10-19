# Local personal agent plan

Build a personal agent that runs on the user's computer with a local model and
readable, editable memory. It should remember useful context, resume unfinished
work, and offer thoughtful follow-ups within permissions the user controls.

This is an exploration plan. Local inference and the complete vault workflow still
need implementation and acceptance testing. Existing scheduled runs remain paused
during development; enabling a new trigger requires an explicit user choice.

## The first experience

Start with one Obsidian vault, a conversational interface, a few active projects,
and one optional check-in. The user can save an article, connect it to a project,
and later ask what they decided and what remains open. Answers should link to the
notes that support them. The agent can prepare a draft next step and retain its
progress across a restart.

Continuity comes from stored memory, durable tasks, and deliberate wake-ups. The
model does not need to generate continuously. Initial learning means recording
corrections and useful procedures, then retrieving them for later work; model
retraining is outside the first milestone.

## Components

- **Vault:** Markdown notes for preferences, projects, decisions, journal entries,
  and research. Obsidian provides the owner's reading and editing interface.
- **Local inference:** evaluate a local model runner, with Ollama as an initial
  candidate. Keep inference, embeddings, and retrieval local in local-only mode,
  with no silent cloud fallback. Model choice follows measured task quality and
  available memory on the intended Mac mini.
- **Agent runtime:** extend the existing Hermes integration and controlled task
  service where compatible. Persist task status and results in the task database;
  Markdown notes are not the execution queue. Verify local model tool use before
  relying on it for actions.
- **Triggers:** user messages first, followed by selected file events or an
  explicitly enabled check-in. Bound work per wake-up and avoid duplicate triggers.
- **Owner controls:** inspect and correct memory, review exact actions, disconnect
  capabilities, cancel work, and pause agent execution and proactive notifications.

## Memory and permissions

Begin with access to a selected vault, not the entire home directory. Keep agent
drafts separate from owner-authored notes. Each durable memory entry should retain
its source and date, and distinguish an explicit user statement from an inference.
Corrections and deletion must also update derived indexes so stale records do not
reappear in answers. Explain backup retention separately from active-memory deletion.

Treat imported articles and other external content as data, not permission to run
commands or change agent instructions. Enforce filesystem access and consequential
approvals in code. The agent must not grant itself permissions or rewrite the rules
that enforce them. Version history and backups support recovery; they do not prevent
data disclosure or undo an external action.

Local inference does not make connected services offline. Any later email, browser,
or messaging integration must make its external data flow and permissions explicit.
For a Mac-hosted model and VM-hosted tools, define and test a narrowly scoped model
connection and vault access boundary before enabling that deployment.

## Implementation sequence

1. **Establish a local baseline.** Choose a small representative set of notes and
   tasks. Verify local model compatibility, retrieval quality, response time, and
   peak memory on available hardware. Record the model, quantization, context
   settings, and hardware used. Choose the Mac mini configuration after measuring
   the intended workload; do not promise performance before testing.
2. **Add grounded conversation.** Search the selected vault and answer with source
   links. Handle missing or conflicting information explicitly. Support inspecting,
   correcting, and forgetting saved facts without silently rewriting owner notes.
3. **Add durable work.** Prepare drafts in the agent's folder, record progress, and
   recover after interruption. Reuse exact-action approvals for consequential writes.
   Uncertain external outcomes must remain visible and must not be retried blindly.
4. **Add one useful proactive behavior.** Offer an optional project check-in based
   on saved decisions and unfinished tasks. Include quiet hours, notification limits,
   duplicate suppression, and immediate pause. Keep existing automations paused.
5. **Prove a complete daily workflow.** Capture a research note, discuss it, retain
   an owner-approved decision, restart the service, recover the unfinished draft,
   and produce one enabled follow-up. Use the results to choose the next capability.

## Acceptance criteria

- Local-only mode completes the baseline tasks without hosted model calls; verify
  network behavior as well as configuration. Report unavailable external tools.
- Recall identifies the supporting notes and handles a correction, a deletion, and
  conflicting evidence without inventing a personal fact.
- A restart preserves accepted work and shows failures; retry tests demonstrate
  that an approved external action is not repeated after an uncertain response.
- Owner edits survive agent activity. Writes outside the selected scope and changes
  to permission rules are rejected by the enforcement layer.
- Pause stops new execution and notifications. Expired, altered, or missing approvals
  cannot authorize consequential actions.
- The owner evaluates short replies and follow-ups for usefulness. Record latency,
  memory use, task completion, and required intervention before expanding scope.

## Later exploration

Broader browser tasks, voice, additional accounts, automatic procedure refinement,
and multiple agents follow a dependable single-agent workflow. Any procedure changes
remain reviewable and cannot expand permissions. The existing deployment and
second-user acceptance work remains tracked in [the roadmap](ROADMAP.md).
