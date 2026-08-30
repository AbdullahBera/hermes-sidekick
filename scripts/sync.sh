#!/usr/bin/env bash
# sync.sh — deploy repo config into the VM and make plugins plug-and-play.
#
# The repo is the source of truth; the running agent uses DEPLOYED copies in the VM. This keeps
# them in step AND reconciles automations straight from your profile:
#   • set `enabled: true` in profile.yaml  -> the cron is created
#   • set `enabled: false`                 -> the cron is paused
#   • change a prompt or a `time`          -> synced
#   • drop a new plugin folder             -> validated + (if enabled) wired up
#
#   ./scripts/sync.sh            # --check: validate + show a status table, change NOTHING
#   ./scripts/sync.sh --apply    # deploy SOUL + prompts, reconcile crons, create/pause as needed
#
# The heavy lifting is in scripts/lib/sync_engine.py, which runs INSIDE the VM (it has PyYAML,
# the profile, cron/jobs.json and the `hermes` CLI) and reads this repo via the OrbStack mount.
set -euo pipefail

VM="${HERMES_VM:-hermes}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="check"
case "${1:-}" in
  --apply)     MODE="apply" ;;
  ""|--check)  MODE="check" ;;
  -h|--help)   sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *)           echo "unknown arg: $1 (use --check or --apply)" >&2; exit 2 ;;
esac

echo "sync ($MODE) — repo: $ROOT  vm: $VM"
echo "----------------------------------------------------------------"
# Run the engine in the VM; it reads the repo at $ROOT via the mount. Exits non-zero on a plugin
# ERROR (handy for CI); WARN/actions are just reported.
cat "$ROOT/scripts/lib/sync_engine.py" \
  | orb run -m "$VM" bash -lc 'export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"; exec python3 - "$0" "$1"' "$MODE" "$ROOT"
