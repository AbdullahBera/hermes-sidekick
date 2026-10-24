# Verification

Core tests use temporary Hermes homes and fake subprocess/OrbStack responses. They never
contact accounts, start services, or edit the live VM's configuration.

```bash
python3 -m pip install -r requirements-dev.txt -r requirements-control.txt
python3 -m unittest discover -s tests -v
for script in scripts/*.sh onboarder/*.sh; do bash -n "$script" || break; done
```

Use Python 3.11+ in CI (the Hermes runtime also provides PyYAML). Coverage includes malformed
profiles/catalogs/jobs, dependency and schedule validation, check-mode immutability, cron
failures, idempotent reconciliation, MCP toggles, pending reload recovery, secret-safe errors,
bootstrap failure propagation, and health failures. Secret scanning runs separately.

The site job installs its locked dependencies, builds before checking packaging, then runs
Playwright desktop/mobile checks:

```bash
cd site
npm ci
npm run build
npm run test:sites
npx playwright install chromium
npm run test:e2e
```

For operational checks, `./scripts/status.sh` is read-only and returns nonzero for unhealthy
services/configuration, missing or mismatched enabled MCP registrations, failed job/delivery
records, or next-run times overdue by more than 15 minutes. It distinguishes a configured
connector from verified access. `--probe-connectors` additionally launches MCP connections for
tool discovery, without invoking account tools. It may use the MCP server's normal auth/cache
behavior; it is opt-in. For actual account reads and delivery, use [the human trial](ONBOARDING-TRIAL.md).

`./scripts/sync.sh --check` never writes or starts a stopped VM. Exit 0 means valid state;
it can still report drift. Invalid state and failed applies return 2 from the engine. Apply
validates all inputs before writes, uses private atomic file replacements, and stops at the
first command failure. It re-reads state before reporting success, so a command that exits zero
without persisting its change still fails verification. Earlier operations may already have succeeded: fix the cause and rerun.
Backups are VM-local `*.pre-sync.bak`; they can contain secrets and must never be copied to the
repo. Concurrent Sidekick applies are locked; external Hermes edits are not transactional with
sync, so avoid simultaneous administration. A failed reload leaves a marker so retries reload
even if the files already match.


## Local-first Phase 0

The query-rule checker, synthetic persona pack and benchmark harness have unit tests that need
no model (`tests/test_query_policy.py`, `tests/test_local_bench.py`). Against a model server on
loopback, and on the Mac host:

```bash
./scripts/mac-baseline.sh      # read-only: hardware, memory, VM host shares, folder permissions
python3 scripts/lib/local_bench.py --base-url http://127.0.0.1:8080/v1 --model <model-id>
```

The benchmark sends only synthetic data, refuses non-loopback endpoints by default, and writes
results to the ignored `.bench/` folder. Add `--suites b1,b2,b3,b4,b7 --embedding-model <id>` for
embeddings, and `--extra-body '{"reasoning_effort": "none"}'` for servers that think by default. Suites, thresholds and later-phase tests are in
[LOCAL-AGENT-TESTS.md](LOCAL-AGENT-TESTS.md).

The new controlled execution path has additional SQLite/socket tests in `test_control.py` and
real Chromium fixture tests. See [CONTROL.md](CONTROL.md) for commands, supported browser forms,
restart/duplicate-action cases, and the OS identity requirements for owner-only approvals.
The MCP test exercises real stdio tool discovery and requests through the agent socket. It
requires `requirements-control.txt`; without that optional dependency it is explicitly skipped.

Owner-control checks include the actual web UI and a fictional sign-in site: exact approval,
private password entry, session transfer, an authenticated read, and disconnect. HTTP tests
reject invalid tokens, cross-origin requests, untrusted hosts, and credential-import methods.
Login cancellation/expiry tests verify that interrupted handoffs cannot save a session later.
Run these with the same `npm --prefix sidekick_control test` and Python discovery commands.
