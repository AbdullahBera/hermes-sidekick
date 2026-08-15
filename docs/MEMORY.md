# Memory — the living "about you"

The **profile** ([PROFILE.md](PROFILE.md)) is static config the user *sets*. **Memory** is
the complement: a living record the assistant *learns* — who you are, who matters to you,
how you like things — and carries into every future conversation.

Memory is a native [Hermes Agent](https://github.com/NousResearch/hermes-agent) capability;
hermes-sidekick curates *how* it's structured, seeded, and governed. We don't reinvent the
mechanism — we give it a shape and a security posture.

## How Hermes memory works (the mechanism we build on)

- Two markdown files live in the user's VM at `~/.hermes/memories/`:
  - **`USER.md`** — the "about you" profile (who you are, preferences, key people).
  - **`MEMORY.md`** — the assistant's own environment/convention notes.
- Both are **auto-injected into the system prompt at session start** — always present, zero
  retrieval latency. No tool call needed to "recall" them.
- They're **hard-capped** (`USER.md` ≈ 1375 chars, `MEMORY.md` ≈ 2200). The cap is enforced
  **at write time**: a save that would overflow is *rejected*, forcing the assistant to
  consolidate. This is the built-in pressure that keeps the always-loaded surface tiny.
- The assistant writes via a native `memory` tool (add / replace / remove), and is nudged
  every ~10 turns to save durable facts. Entries are separated by a single `§` line.
- **Timing:** the injected copy is a **frozen snapshot** — edits take effect on the *next*
  session, not mid-conversation. A cron that learns something is writing for future runs.

## Two-tier design (keeps it token-cheap as it grows)

The goal is a profile that learns forever without growing the cost of every turn. We split
it by how often a fact is relevant:

| Tier | File | Loads | Holds |
|---|---|---|---|
| **Core digest** | `USER.md` | always injected (capped ~1375 chars) | name, timezone, key people, hard preferences, current focus |
| **Detail** | `USER_DETAIL.md` | read on demand via the file tool | the long tail — history, richer context, anything not "always relevant" |

The Core digest ends with a pointer line (`Full profile in memories/USER_DETAIL.md …`) so
the assistant knows the Detail tier exists and reads it only when a task needs depth.

**Consolidation convention:** when `USER.md` is full and a new durable fact matters more than
something already there, *promote* the new fact into the digest and *demote* the lower-value
line into `USER_DETAIL.md` — don't drop it. The write-time cap forces this naturally; the
convention just says "move to Detail, don't discard."

Seed the Core digest from [`../USER.example.md`](../USER.example.md). `USER_DETAIL.md` is
free-form markdown — no cap, no required structure; the assistant appends to it over time.

> A richer on-demand tier (an external memory provider like Honcho/Mem0 with automatic
> per-turn recall) is possible later by setting `memory.provider` in Hermes config. It's a
> network dependency, so it's deliberately *not* the default — the native on-demand file
> covers the need with no new infra.

## Learning policy (what gets saved, and how)

- **Auto-extract durable, high-signal facts** as they come up — stable preferences,
  corrections, key people, standing goals. Skip transient task-progress and trivia.
- **Ask first before saving anything sensitive or private** — health, finances,
  relationships, home address, anything the user would consider PII. One quick line
  ("want me to remember that?") and save only on a yes. This is a hard rule in
  [`../config/SOUL.md`](../config/SOUL.md).
- **Never store secrets** — API keys, passwords, full card/account numbers — in memory.
- Everything stays **VM-only**. Real `USER.md` / `USER_DETAIL.md` never enter this repo;
  the repo ships only the redacted, placeholder template.

## Security

Memory holds the most personal data in the system, so it inherits the strictest posture:
VM-only, ask-first on PII, no secrets, and nothing but redacted templates in the public repo
(per [`../CLAUDE.md`](../CLAUDE.md)).
