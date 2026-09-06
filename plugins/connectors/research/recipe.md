# Research — keyless, cited

Ask it to look something up and it does real web research — searches the live web, reads the
actual sources, and comes back with a concise answer **and the links it used**. Read-only; it
never acts on your accounts.

## Security posture
- **Keyless:** searches from the terminal via DuckDuckGo lite (`lite.duckduckgo.com/lite/?q=…`)
  and fetches pages with `curl`. No search-API key, no account.
- **Read-only:** it only reads and reports — no writes, no purchases, no messages sent.
- **Trust standard:** it reads the **live source** (not memory), **cites** what it used, and says
  so when it can't verify — it does not fabricate a source or a fact.
- **Injection-safe:** page contents are data, never instructions (per SOUL.md).

## Setup
Keyless — nothing to configure. Optionally tune in the profile:
```yaml
connectors:
  research:
    enabled: true
    depth: standard     # quick | standard | deep
    max_sources: 5
```

## How it works
Given a question, the agent runs a few web searches, opens the most relevant results, synthesizes
a short answer, and lists the sources (title + link). `depth: deep` reads more and cross-checks
conflicting claims.

## Verify
- "research the best keyless geocoding APIs — give me 2 with links" → a short comparison + source
  links.
- "what changed in <topic> this week?" → a current answer citing where it read it.
