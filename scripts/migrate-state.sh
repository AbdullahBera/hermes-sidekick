#!/usr/bin/env bash
# migrate-state.sh — move a Hermes instance's STATE to another host (for always-on).
#
# It copies only the small, non-reproducible state — config, persona, memories, crons,
# OAuth creds, secrets, and the Signal registration — and deliberately SKIPS the ~2 GB of
# reinstallable code (hermes-agent/, node/, bin/, caches). The target host must already have
# Hermes installed (see docs/DEPLOY.md). Works for a spare-Mac OrbStack VM today and a
# home/cloud Linux box later — same state set.
#
#   ./scripts/migrate-state.sh                      # --dry-run: list state + sizes, copy nothing
#   ./scripts/migrate-state.sh --to user@host       # stream state VM -> target over SSH
#
# SAFETY — Signal: a phone number lives on ONE registration. This is a CLEAN CUTOVER — stop
# signal-cli on BOTH hosts around the copy and never run two instances at once, or Signal will
# deregister one. The copy itself is non-destructive (source is untouched), so OrbStack stays a
# hot rollback until you verify the new host. See docs/DEPLOY.md.
set -euo pipefail

VM="${HERMES_VM:-hermes}"
MODE="dry-run"; TARGET=""
case "${1:-}" in
  ""|--dry-run) MODE="dry-run" ;;
  --to) MODE="copy"; TARGET="${2:-}"; [ -n "$TARGET" ] || { echo "--to needs user@host" >&2; exit 2; } ;;
  -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

vm() { orb run -m "$VM" bash -lc "$1"; }

# The portable state. Everything under ~/.hermes EXCEPT the reinstallable code/caches, plus the
# Signal registration under ~/.local/share/signal-cli.
EXCLUDES='--exclude=hermes-agent --exclude=node --exclude=bin --exclude=cache --exclude=logs --exclude=models_dev_cache.json --exclude=*.log --exclude=*.bak --exclude=*.pre-sync.bak'
# tar targets (paths relative to $HOME so they restore to the same layout on the new host)
PATHS='.hermes .local/share/signal-cli'

echo "migrate-state ($MODE) — source VM: $VM"
echo "------------------------------------------------------------"
echo "State to migrate (reinstallable code is excluded):"
vm "cd ~ && du -sh --exclude=hermes-agent --exclude=node --exclude=bin --exclude=cache --exclude=logs .hermes .local/share/signal-cli 2>/dev/null" | sed 's/^/  /'
echo "  (skipping ~/.hermes/{hermes-agent,node,bin,cache,logs} — reinstalled by provision)"
echo "------------------------------------------------------------"

if [ "$MODE" = dry-run ]; then
  echo "Key files present?"
  for f in .hermes/config.yaml .hermes/SOUL.md .hermes/.env .hermes/sidekick/profile.yaml \
           .hermes/google-workspace .hermes/memories .hermes/cron/jobs.json .local/share/signal-cli; do
    vm "test -e ~/$f" && echo "  ✓ $f" || echo "  ✗ MISSING: $f"
  done
  echo "------------------------------------------------------------"
  echo "Dry run only — nothing copied. When the target host has Hermes installed:"
  echo "  ./scripts/migrate-state.sh --to user@your-host"
  exit 0
fi

# --- copy path: stream tar from the source VM straight to the target over SSH ---
# Secrets never land on the Mac disk in between; they go VM -> (host pipe) -> target.
echo "Streaming state to $TARGET …"
echo "Reminder: stop signal-cli on BOTH hosts first (clean Signal cutover)."
# shellcheck disable=SC2086
vm "cd ~ && tar -czpf - $EXCLUDES $PATHS" \
  | ssh "$TARGET" 'tar -xzpf - -C "$HOME" && chmod 600 ~/.hermes/.env 2>/dev/null; chmod -R go-rwx ~/.hermes/google-workspace ~/.hermes/memories ~/.hermes/sidekick 2>/dev/null; echo "restored on target"'
echo "------------------------------------------------------------"
echo "Done. Next on the target: start signal-cli + hermes-gateway, then verify (docs/DEPLOY.md)."
echo "Keep the OrbStack instance as rollback until the new host runs a full day clean."
