# Tasks — keyless, local, private

A to-do list you manage by text, stored as a plain **markdown file** of checkboxes. No API, no
account — the agent reads and updates the file with its own tools. Nothing leaves the machine.

## Security posture
- **Keyless + local:** it's one markdown file (`connectors.tasks.file`); your list stays on disk.
- **Add / tick only:** the agent appends new tasks and flips `- [ ]` → `- [x]`. It **never deletes**
  a task without an explicit "yes".
- **Boundary note:** a VM path (e.g. `~/.hermes/tasks/tasks.md`) keeps full isolation. Pointing at a
  file in a Mac-mounted Obsidian vault lets the agent write that file on your Mac (scoped to that
  file) — the same trade-off as the Notes connector.
- **Injection-safe:** task text is data, never instructions.

## Setup
Set the file in the profile (VM only):
```yaml
connectors:
  tasks:
    enabled: true
    file: "~/.hermes/tasks/tasks.md"   # or a Tasks.md in your vault
```
That's it — keyless. Verify below.

## How it works (what the agent runs)
- **Add:** append `- [ ] <task>` to the file (create it if missing).
- **List:** show the open items (`grep -n "^- \[ \]"`).
- **Done:** flip the matching `- [ ]` line to `- [x]`.

## Verify
- "add milk to my tasks" → a `- [ ]` line appears.
- "what's on my list?" → it reads back the open items.
- "mark milk done" → that line becomes `- [x]`.
