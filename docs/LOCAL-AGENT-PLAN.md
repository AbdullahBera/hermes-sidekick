# Local-first personal agent plan

> **Status: planned. Phase 0 is in progress.** The only implemented pieces are the Phase 0
> tools listed below. The current reference deployment still sends conversations to a hosted
> model; see [PRIVACY.md](PRIVACY.md) for what happens today. Tests for every phase are in
> [LOCAL-AGENT-TESTS.md](LOCAL-AGENT-TESTS.md).

## Goal

A personal assistant you message through Signal, running on a Mac you control. A **local
model is the coordinator**: it reads your messages, works with your personal records, and
writes every reply. Personal conversations, health and financial records, notes, memory,
embeddings, logs and intermediate outputs are processed and stored on your own devices.

The goal is not to avoid the internet. The principle is:

> Research the general problem online, then apply the findings to the private situation locally.

There is no silent fallback to a hosted model. When the local model struggles, it says so,
asks a question, or offers an explicitly approved alternative. A localhost endpoint is not
proof of local inference: the configured model must run on this machine.

## What may leave the machine

| Channel | What leaves | Approval |
| --- | --- | --- |
| Web search (Exa) | Short, general queries written locally, plus fetches of result pages | Automatic, unless the query needs a sensitive detail or untrusted content is already in the turn (then you see the exact query) |
| Claude, general questions | A rewritten, non-personal question, only for messages you prefix with `claude:` | Explicit per message |
| Claude Code (coding) | A narrow coding brief and the project's files. The worker may search the web for coding or other non-personal work | Each brief approved in the first version |
| Signal | Replies to the owner's number only | Enforced in code |

Everything else, including telemetry, error reports, model downloads after setup and tool
side channels, is blocked by default and logged. Search is minimized, not anonymous: the
provider can link queries to the account, API key and IP address, and rare combinations of
facts can identify a person. Exa's general privacy policy allows using query data to improve
its products, including model training; API customers are governed by their own agreement.

## Architecture

```
 INTERNET        Signal servers        Exa search API       Anthropic API
                       ▲                     ▲                    ▲         ▲
                       │ E2E, owner only     │ minimal query      │ general │ brief + repo,
                       │                     │ + page fetch       │ Q only  │ worker web search
═══════════════════════╪═════════════════════╪════════════════════╪═════════╪═══ allowlist per zone
 MAC (Apple Silicon)   │                     │                    │         │
┌─ VM "hermes" ────────┼─────────────────────┼────────────────────┼────┐    │
│  ┌────────────┐      │  ┌──────────────────┴─────┐ ┌────────────┴──┐ │    │
│  │ signal-cli ├──────┘  │ SEARCH BROKER          │ │ CLOUD-Q BROKER│ │    │
│  └─────┬──────┘         │ policy · audit log     │ │ explicit only │ │    │
│        │                │ quarantined reader     │ │ stateless     │ │    │
│        │                └──────────▲─────────────┘ └──────▲────────┘ │    │
│        ▼                           │ query                │ question │    │
│  ┌─────────────────────────────────┴─────────────────────┴───────┐   │    │
│  │ PRIVATE ZONE · no internet · taint-aware outbound rules        │   │    │
│  │ Hermes coordinator · private records · personal memory         │   │    │
│  │ research cache (untrusted, cited) · sidekick_control           │   │    │
│  └─────┬────────────────────┬────────────────────────┬────────────┘   │    │
└────────┼────────────────────┼────────────────────────┼────────────────┘    │
         │ prompts            │ MCP: run workflow      │ approved brief      │
         ▼                    ▼                        ▼                     │
┌──────────────────┐ ┌─────────────────────────┐ ┌───────────────────────────┴┐
│ LOCAL INFERENCE  │◀┤ SIM  (VM "sim")         │ │ CODING BROKER              │
│ native · Metal   │ │ agent blocks → local LLM│ │ macOS user hermes-coder    │
│ chat + embeddings│ │ KB: local embeddings    │ │ Claude Code --bare         │
│ VM-only + token  │ │ no Copilot · no E2B     │ │ web search: non-personal   │
│ outbound blocked │ │ no internet (Phase 5)   │ │ allowlisted workspaces     │
└──────────────────┘ │ broker tools via MCP    │ │ lock · handoff note        │
                     └─────────────────────────┘ └─────────────┬──────────────┘
                                                               │ same files
                                                  ┌────────────▼────────────┐
                                                  │ Conductor workspace     │
                                                  └─────────────────────────┘
```

**Why this placement:**
- **Inference runs natively on macOS.** A Linux VM on macOS does not get Metal GPU
  acceleration. MLX is the engine: it is built for Apple Silicon and measured fastest here.
  `mlx_lm.server` describes itself as not for production and parses tool calls per model
  family, so daily use puts a small authenticated proxy in front of it. Embeddings come from
  Ollama (local-only mode), which both Sim and Mem0 support.
- **The VM reaches inference through one forwarded port.** OrbStack VMs can normally reach
  every service on the Mac's loopback. An isolated, network-isolated machine cannot; the Mac
  opens an SSH tunnel into it over OrbStack's command channel and forwards only the model
  port, which the VM's firewall further limits to the `hermes` account (verified in Phase 0).
- **Hermes, Signal, the brokers and private data run in a VM.** Linux makes per-user
  outbound blocking simple to configure and audit.
- **The coding worker runs natively** under its own macOS account, because it must work
  on the same files Conductor uses.
- **Sim runs in a second VM**, because it holds private data (knowledge bases, run logs)
  and needs its own outbound policy and memory accounting.

## Trust zones

| Zone | Can read | Can reach | Must never receive |
| --- | --- | --- | --- |
| Private zone (Linux user `hermes`) | Private records, memory, embeddings, logs | Local inference and the brokers. No internet | n/a |
| Local inference (macOS) | Prompts from the VMs | Nothing outbound after the model download | n/a |
| Search broker (Linux user `search`) | Its config, the Exa key, its audit log, a hashed sensitive-terms list | Exa and fetched result pages | Private records; it only accepts a query string and a result count |
| Cloud-Q broker (Linux user `cloudq`) | Its Anthropic key and audit log | Anthropic API | Conversation history, memory, records |
| Signal (Linux user `signal`) | Its message store (private) | Signal servers | Any recipient other than the owner |
| Sim (VM `sim`) | Its workflows, knowledge bases and run logs | Local inference and the brokers. No internet until Phase 7 | Cloud model providers, Sim's hosted Copilot, remote code sandboxes |
| Coding worker (macOS user `hermes-coder`) | Allowlisted workspaces and the git metadata they need | Anthropic, allowlisted package registries and documentation, web search | Conversation history, personal memory, records, the personal notes vault, other repositories, `~/.ssh` |

## Rules across zones

- **Enforcement lives outside the model.** OS accounts, firewall rules and brokers decide what
  can leave. Prompts and model classifiers are hints, not boundaries. Published adaptive
  attacks have broken most prompt-injection defenses that rely on detection.
- **Taint rule.** The coordinator holds private data and can send queries out, so web content
  in its context would complete the "lethal trifecta". Once untrusted content enters a turn,
  further outbound actions must come from a plan made before that content arrived, or get
  owner approval. A separate local-model reader with no tools and no private data turns raw
  pages into cited facts.
- **Fixed query rules.** Outbound queries are checked against rules modeled on the HIPAA Safe
  Harbor identifiers (see `scripts/lib/query_policy.py`). Checks are imperfect: paraphrases,
  rounding and rare combinations can still identify someone.
- **Untrusted content stays untrusted.** Research saved for later keeps its source and date,
  is labeled untrusted when retrieved, and never becomes personal memory or instructions
  without owner approval.
- **Approvals are rare and exact.** Each approval shows the exact outgoing text. Frequent
  prompts get approved without reading, so the design keeps them for unusual cases.

## Memory

Memory is built in layers so that what the assistant "knows" stays inspectable, approved and
deletable:

```
 coordinator ─▶ PROPOSALS (local model extracts candidate facts)
                    │  turns that contain untrusted content cannot write memory
                    ▼
 approval: an explicit "remember X" from the owner is saved and labeled explicit;
 inferred facts go to a short daily digest for approval
                    ▼
 SOURCE OF TRUTH: approved-memory store (sidekick_control, extended with source, date,
 explicit/inferred, category); exportable to Markdown
                    │ rebuilt from the source of truth
                    ▼
 SEARCH INDEX (derived, disposable): local embeddings
 RESEARCH CACHE (separate store; public, untrusted, cited)
```

Deleting a fact removes it from the source of truth, rebuilds the index, and verifies it is
gone. Hermes's built-in `MEMORY.md`/`USER.md` hold only a digest generated from approved
memory.

**Evaluated options.** Letta is a full agent runtime whose agents edit their own pinned memory.
That would compete with Hermes as the orchestrator, conflicts with approval-gated memory, and
turns a successful injection into text present in every future prompt. It is not used unless
Hermes is ever replaced. Mem0 is an official Hermes memory provider with a fully local mode
(Ollama or an OpenAI-compatible model, Qdrant or pgvector). By default it extracts and updates
facts after every turn without approval, costs an extra model call per turn, truncates captured
messages, and sends PostHog telemetry unless `MEM0_TELEMETRY=false` is set before import. It
is a candidate for the extraction and search layers with automatic capture constrained, not
for the source of truth. Hermes's local-only Holographic provider is a third candidate. Phase 1
chooses among them with the M1–M8 bake-off in [LOCAL-AGENT-TESTS.md](LOCAL-AGENT-TESTS.md).

## Sim workflows

[Sim](https://github.com/simstudioai/sim) (Apache-2.0) is a self-hostable builder for AI
agent workflows. It supports local models (`OLLAMA_URL`, or an OpenAI-compatible
`VLLM_BASE_URL`) and has APIs to create, import, export and deploy workflows. Deployed
workflows can be exposed as MCP tools. In this plan:

- **Turned off:** Sim's hosted Chat/Copilot service (`COPILOT_API_KEY` unset,
  `NEXT_PUBLIC_CHAT_DISABLED=true`); remote code sandboxes (E2B, Daytona); telemetry
  (`NEXT_TELEMETRY_DISABLED=1`, verify `TELEMETRY_ENDPOINT`); cloud providers
  (`BLACKLISTED_PROVIDERS`); public API and registration.
- **Local:** agent blocks use the local model, and knowledge-base embeddings use a local
  model (Sim's default is OpenAI).
- **Tiers:** Tier A (private inputs, nothing leaves) runs first. Tier B (public inputs that
  reach out) needs a separately firewalled instance. Tier C (both) is allowed only through
  the Hermes brokers, with an approval pause showing the exact outgoing data.
- **Authoring:** Hermes drafts workflows through Sim's API and never deploys them itself.
  Deployment, and especially schedules, needs owner approval bound to the workflow's
  content. Generic templates with no personal content may be written by the coding worker.
- **Memory:** Sim's setup guidance lists 12 GB+ RAM. Whether it fits next to the model and
  the Hermes VM is a Phase 0 measurement.

## Phases

| Phase | Scope | Data | Gate |
| --- | --- | --- | --- |
| 0. Decide and measure | Benchmarks, memory budget, verify assumptions, docs | None, then synthetic | G0 |
| 1. Private local core | VM hardening, local inference, local-only Hermes, owner-only Signal | Synthetic | G1 |
| 2. Research gateway | Search broker, query rules, taint rule, quarantined reader, cloud-Q broker | Synthetic | G2 |
| 3. Coding bridge | `hermes-coder`, Claude Code worker, lock, Signal relay, handoff | Synthetic | G3 |
| 4. Real data | One category at a time (notes, finances, health), canaries mixed in | Real | G4 |
| 5. Sim private tier | Sim VM, local models only, owner-built Tier A workflows | Synthetic, then real | G5 |
| 6. Agent-drafted workflows | Drafts via API, validator, approval-bound deployment | Synthetic, then real | G6 |
| 7. Sim integrations | Tier B in a separate instance, Tier C through brokers, one integration at a time | Real | G7 |

Phases 3 and 4 can run in parallel after Phase 2. Every gate re-runs the privacy regression
suite. A failure stops the rollout and rolls back that phase.

### Phase 1 build list
- A new VM created with `orb create --isolated --isolate-network`: no Mac filesystem, no access
  to the Mac or other VMs. Separate Linux users per zone. All outbound traffic blocked by
  default, with exceptions per user. DNS only through a logging resolver.
- Local inference on the Mac, bound to loopback behind an authenticated proxy. The Mac opens a
  reverse SSH tunnel into the VM over the `orb` channel, forwarding only the proxy port; the
  VM firewall allows only the `hermes` account to use it. The runtime is blocked from the
  internet after downloads, model snapshots are pinned by revision, and servers run offline
  (`HF_HUB_OFFLINE=1`).
- Fresh Hermes install with `provider: custom` pointing at the forwarded port, a context
  window of at least 64K tokens (Hermes's minimum), no `fallback_providers` or
  `fallback_model`, auxiliary tasks (vision, compression, titles, skills hub) pinned to the
  local endpoint or disabled, and an explicit toolset allowlist (web, browser, media,
  skills-hub and remote-sandbox tools off; search goes through the broker). No model-provider
  keys. Only the profile and `SOUL.md` are imported; old scheduled routines are not migrated
  or enabled.
- The memory bake-off (M1–M8) on synthetic data.
- signal-cli restricted in code to the owner's number. Link previews off.
- Private store on the VM's own disk (mode 0700), approved memory from `sidekick_control`,
  log retention, encrypted backups.

### Phase 2 build list
- Search broker holding the Exa key: query-string API, fixed rules, rate limits, GET-only page
  fetches without cookies, size limits.
- Quarantined reader, taint tracking, Signal approval with the exact query, research cache.
- Cloud-Q broker for `claude:` messages: stateless, same rules, approval when the coordinator
  rewrote the question.

### Phase 3 build list
- `hermes-coder` macOS account with access only to allowlisted workspaces and their repo's
  `.git` metadata. Default home and Conductor folder permissions must be tightened first (see
  Phase 0 findings).
- Claude Code with `--bare` (so repository hooks and `.mcp.json` servers do not run), its own
  settings file, sandbox on with `failIfUnavailable`, `.env*` reads denied, web search and
  fetch allowed, a network allowlist for package registries and docs,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `DISABLE_FEEDBACK_COMMAND=1`,
  `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, an API key from the worker's keychain, and a per-job
  spending cap. `--bare` uses API-key authentication, not a subscription login.
- Coding broker: project registry (`config/coding-projects.example.yaml`), workspace lock,
  job events, question relay with `--resume`, SIGINT cancellation, local commits only, new
  dependencies flagged, handoff note in `.context/hermes-handoff.md`.

### Signal → coding → Conductor handoff
1. You ask for a change in a named project.
2. The coordinator finds the workspace in the registry, or asks you to create one in
   Conductor (local workspaces have no automation API).
3. It drafts a brief without conversation history or personal memory. The brief passes the
   query rules, and you approve it on Signal.
4. The broker takes the workspace lock and refuses to start over uncommitted changes it did
   not make. It cannot detect an active Conductor chat, so you agree not to type in a locked
   workspace.
5. Claude Code runs as `hermes-coder`. Progress, questions, completion and failures are relayed
   to Signal with rate limits. Questions resume the same session with your answer.
6. "Stop" sends SIGINT and records the job as interrupted.
7. On completion: local commit, no push, handoff note with summary, files changed, tests run,
   open questions, session ID and the resume command. The lock is released when the process
   exits.
8. You review the diff in Conductor and continue there. You can resume the saved session
   from a Conductor terminal as `hermes-coder`. Importing it into Conductor's native chat is
   not supported.

## Phase 0 results (2026-10-24)

**Status: complete, with one condition.** Model and runtime are chosen from measurements, and
every Phase 0 question has an answer. Memory headroom (B5) is marginal at long contexts and
becomes an operating constraint for Phase 1.

| Item | Result |
| --- | --- |
| Tools: synthetic pack, query rules, benchmark (B1–B4, B7), host baseline, registry example | Done, unit-tested |
| MLX installed (`mlx-lm` 0.32.2 in a private Python 3.12 environment) and models benchmarked | Done; models pinned by revision and served offline |
| Runtime comparison: mlx-lm vs Ollama (MLX engine) vs Ollama (llama.cpp engine), same model | Done; mlx-lm chosen for chat, Ollama (local-only) for embeddings |
| Sim memory in a disposable stack with no data | Done for idle and warm pages (about 1.06 GB); memory while a workflow runs is test S13 |
| Hermes custom endpoint, fallbacks and outbound tools | Verified in Hermes documentation; live test happens with the Phase 1 install |
| OrbStack isolation | Verified with throwaway machines (see findings) |
| Accounts: Exa API key, Anthropic Console key with spending limit | Owner, before Phases 2 and 3 |

### Benchmarks (synthetic data, Apple M6 Mac mini, 32 GB)

Qwen3.6-35B-A3B is the same model in all three runtime rows. "Tok/s" is measured generation
speed for a 300-token reply. Times are to the first token.

| Model / runtime | B1 tools | B2 leaks | B3 | Tok/s | 8K prompt | 32K prompt | Follow-up turn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Qwen3.6-35B-A3B 4-bit, mlx-lm** | 8/8 | 1 | 100% | **65** | 5.9 s | 31 s | 0.2 s |
| Qwen3.6-35B-A3B nvfp4, Ollama (MLX engine) | 8/8 | 1 | 100% | 25 | 6.4 s | 32 s | 0.2 s |
| Qwen3.6-35B-A3B Q4_K_M, Ollama (llama.cpp) | 8/8 | 1 | 100% | 39 | 8.6 s | 49 s | 0.2 s |
| Qwen3.6-27B dense 4-bit, mlx-lm | 8/8 | 0 | 100% | about 7 | 32 s | 146 s | n/a |
| Qwen3.5-9B 4-bit, mlx-lm | 8/8 | 2 | 100% | about 23 | 8.3 s | 41 s | n/a |
| gpt-oss-20b, mlx-lm | 2/8 | 0 | 100% | about 43 | 4.2 s | 22 s | n/a |

- **Chosen: Qwen3.6-35B-A3B 4-bit on mlx-lm.** It ties for quality and is fastest. Every
  model resisted both injection cases; the remaining leaks were a rare condition (H3) and an
  employer name (F3), which the fixed query rules catch and route to owner approval. The
  slower dense 27B asked for approval correctly in both cases.
- gpt-oss-20b chose tools correctly, but `mlx_lm.server` does not parse its output format into
  tool calls. Ollama's llama.cpp run had flash attention off by default, so raw llama.cpp may
  narrow the gap on long prompts.
- Embeddings: `qwen3-embedding:0.6b` on Ollama, pinned to a 2K context, uses 0.99 GB (4.8 GB
  at its default 32K context) and embeds about 73 texts per second.

### Findings
- **Memory (B5):** the chat model peaks at 22–23 GB on a 32K prompt. With embeddings, the
  Hermes VM and desktop apps running, free memory dropped to 8% and the first token slowed
  from 31 s to 41 s. An 8-bit context cache changed little (11%); the 19 GB of weights
  dominate. In Phase 1 the host runs headless (no desktop apps), Sim starts on demand, the
  embedding model keeps a small context, and the working context per turn has a budget. If
  that is not enough, the next candidate to measure is a pruned variant of the same model.
- **GPU memory limit:** exceeding macOS's default GPU memory limit aborts requests with a Metal
  out-of-memory error rather than slowing down. One global large-context setting applied to
  the embedding model was enough to trigger it.
- **Loopback is not a boundary:** ordinary OrbStack VMs, and in testing even `--isolated`
  ones, reached services bound to the Mac's `127.0.0.1`. `--isolated --isolate-network`
  blocked the Mac and other VMs while keeping internet access. A Mac-initiated reverse SSH
  tunnel over the `orb` command channel then exposed exactly one port inside the VM.
- **Host shares:** the existing reference VM mounts six Mac paths (`/Users`, `/mnt/mac`,
  `/Applications`, `/Library`, `/Volumes`, `/private`). It is not used for private data; Phase
  1 creates a new isolated VM.
- **Folder permissions:** the home folder is group-readable (`staff`) and the Conductor folders
  are world-readable (`755`), so a separate coding account could read every workspace,
  including a personal notes vault. Tightening this is a Phase 3 prerequisite (test C2).
- **Ollama:** runs local-only (`OLLAMA_NO_CLOUD=1`, logged as "cloud disabled"), listens on
  loopback, and uses its MLX engine on this 32 GB Mac. Model pulls run inside the server
  process, so downloads must finish before outbound traffic is blocked.
- **Hermes:** needs a 64K context window, supports `provider: custom`, has no fallback unless
  `fallback_providers`/`fallback_model` are set, and resolves auxiliary tasks with `auto`,
  which follows the main provider. Its web, browser, media, skills-hub and remote-sandbox
  tools are outbound paths to disable.

## Open decisions
1. Phase 1 context budget per turn and whether Sim stays running or starts on demand.
2. Memory design candidates for the bake-off (approved store baseline, Mem0 local, Holographic).
3. Workflow authoring by the local model only, or also coding-worker templates.
4. Order of real data categories.

## Limitations
- A local model of the size that fits will be weaker than hosted frontier models. With no
  cloud fallback, some tasks will be worse.
- Hermes with a local model and a minimal tool set is not yet verified live.
- Memory headroom on 32 GB is tight at long contexts (Phase 0, B5).
- Query rules, the taint rule and the quarantined reader reduce risk; they do not prove that
  nothing personal can leave.
- The coding worker can still be steered by web content; diff review, no push and flagged
  dependencies are the defense.
- Sim is large and changes quickly. Pinned versions and a full re-test on upgrade are required.

## References
- Simon Willison, [The lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
- Meta, [Agents Rule of Two](https://ai.meta.com/blog/practical-ai-agent-security/)
- [Design Patterns for Securing LLM Agents against Prompt Injections](https://arxiv.org/abs/2506.08837)
- [The Attacker Moves Second](https://arxiv.org/abs/2510.09023)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026)
- [HHS de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification)
- Claude Code: [headless and `--bare`](https://code.claude.com/docs/en/headless),
  [sandboxing](https://code.claude.com/docs/en/sandboxing),
  [data usage](https://code.claude.com/docs/en/data-usage)
- Sim: [repository](https://github.com/simstudioai/sim),
  [self-hosting environment variables](https://docs.sim.ai/self-hosting/environment-variables)
- [Exa privacy policy](https://exa.ai/privacy-policy)
