# Notes — keyless, local, private

Capture and recall notes as plain **markdown files** — no API, no token, nothing leaves the
machine. Works with an **Obsidian vault** or any folder of `.md` files. The agent captures by
**appending** to a note and recalls by searching the folder.

## Security posture
- **Keyless + local:** the agent uses its own file/terminal tools; your notes stay on disk.
- **Append/create only:** it appends to your capture file or creates a new note — it **never
  edits or deletes** existing notes.
- **The VM-boundary tradeoff (read this):** if `path` points at a **Mac-mounted** folder (an
  Obsidian vault under `/Users/...`, visible in the VM via OrbStack), the agent can **read and
  write that folder on your Mac** — a deliberate crossing of the VM sandbox, *scoped to the
  vault*. If you'd rather keep full isolation, use a **VM-local** folder (`backend: local`,
  e.g. `~/.hermes/notes`) — the agent never touches the Mac then.
- **Injection-safe:** note contents are treated as data, never instructions.

## Setup
1. Choose your notes folder and set it in the profile (VM only):
   ```yaml
   connectors:
     notes:
       enabled: true
       backend: obsidian          # or: local
       path: "/Users/<you>/…/YourVault"   # Obsidian vault via the mount, OR a VM folder
       capture: daily             # daily | inbox | <filename.md>
   ```
2. That's it — it's keyless. Verify below.

## How it works (what the agent runs)
- **Recall / search:** `grep -rIni "<query>" "<path>" --include=*.md` → summarize the hits, cite
  the note name.
- **Capture:** append a dated line to the capture target (create it if missing):
  - `capture: daily` → `"<path>/YYYY-MM-DD.md"`
  - `capture: inbox` → `"<path>/Inbox.md"`
  - otherwise the given filename.

## Verify
- Say "note: pick up dry cleaning" → a dated line appears in your capture file.
- Say "what did I note today?" → it finds and reads it back.

## Notes
- Keep captures short + dated so recall stays clean.
- Obsidian picks up the appended lines automatically (they're just files).
- A remote backend (Notion, etc.) is a future optional upgrade — it would add a token.
