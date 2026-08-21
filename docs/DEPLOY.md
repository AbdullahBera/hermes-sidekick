# Always-on deploy — moving Hermes off your laptop

Proactivity (morning brief, triage, future time-precise nudges) only fires when the host is
awake. This runbook moves a working Hermes instance onto an **always-on** host. The workload is
arm64 Linux, **outbound-only** (no inbound ports to open), and the non-reproducible **state is
tiny (~20 MB)** — config, persona, memories, crons, OAuth creds, and the Signal registration.
The ~2 GB of `hermes-agent/` code is reinstalled, not copied.

Two moving parts:
- **[`../scripts/provision.sh`](../scripts/provision.sh)** — run ON the new host to install
  Hermes Agent + workspace-mcp + signal-cli + the systemd units (`SIGNAL_NUMBER=+1… ./provision.sh`).
  Services are installed but not started.
- **[`../scripts/migrate-state.sh`](../scripts/migrate-state.sh)** — copy the small state over
  (dry-run by default; `--to user@host` streams it, secrets never landing on the Mac disk).

## Host options
- **A. Spare Mac + OrbStack, always-on** (recommended first — lowest risk): another Mac running
  OrbStack 24/7 (clamshell, plugged in). Same environment; nothing about the app changes.
- **B. Home arm64 box** (Raspberry Pi 5 8 GB / mini PC): strongest privacy, ~$80, on your LAN.
- **C. User-owned cloud VM** (arm64, ~$4/mo): fastest, but data lives on a rented box.

All three use the **same `migrate-state.sh`**; only provisioning differs.

## The two things that need care
### Signal — clean cutover
A phone number lives on **one** registration. Never run two signal-cli instances at once, or
Signal deregisters one.
1. `orb run -m hermes bash -lc 'sudo systemctl stop signal-cli hermes-gateway'` (source).
2. Run `migrate-state.sh --to …` (copies the `signal-cli` data dir with the account keys).
3. Start signal-cli + gateway on the **target** only. Same keys → no re-verify.
The copy is non-destructive, so the source stays a hot rollback until you cut over for good.

### Google OAuth — headless re-auth
The creds (`~/.hermes/google-workspace/`: client JSON + token) are portable files — copied as-is,
the refresh token keeps working. Only a *future* re-auth needs a browser; on a headless box, use
an SSH tunnel instead of OrbStack's auto-forward:
```bash
ssh -L 8000:localhost:8000 user@host   # then run the workspace-mcp HTTP auth flow on the host
```
and approve in the browser on your laptop (the loopback callback rides the tunnel).

## Runbook
1. **Provision** the target host: `SIGNAL_NUMBER=+1XXXXXXXXXX ./scripts/provision.sh` (run on the
   host). Installs Hermes + connectors + signal-cli + systemd units; leaves services stopped.
2. **Dry-run** to see exactly what will move: `./scripts/migrate-state.sh`
3. **Stop** signal-cli + gateway on the source (Signal cutover, above).
4. **Migrate**: `./scripts/migrate-state.sh --to user@host`
5. **Start** `signal-cli` then `hermes-gateway` on the target.
6. **Verify**: `hermes cron run morning-brief` on the target delivers to Signal; triage labels;
   Google reads work. Let a real 08:00 run fire once.
7. **Cut over**: once a full day runs clean, retire the OrbStack instance — but keep its image a
   week as rollback.

## Rollback
The migration never touches the source. To fall back, start signal-cli + gateway on OrbStack
again (and stop them on the target first — one Signal instance at a time).
