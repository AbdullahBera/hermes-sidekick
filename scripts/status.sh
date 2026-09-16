#!/usr/bin/env bash
# Read-only health checks. --require-isolation rejects detected host filesystem sharing.
# --probe-connectors connects to MCP servers for discovery, without invoking account tools.
# On a Linux host/inside the VM: HERMES_LOCAL=1 ./scripts/status.sh
set -euo pipefail
VM="${HERMES_VM:-hermes}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${HERMES_LOCAL:-0}" = 1 ]; then
  export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
  exec python3 "$ROOT/scripts/lib/health_engine.py" "$ROOT" "$@"
fi
command -v orb >/dev/null || { echo 'FAIL OrbStack: command missing' >&2; exit 1; }
[ "$(orb status)" = Running ] || { echo 'FAIL OrbStack: engine not running' >&2; exit 1; }
# Do not use orb run on a stopped VM: a health check must not start it.
orb list | awk -v vm="$VM" '$1 == vm && $2 == "running" { found=1 } END { exit !found }' \
  || { echo 'FAIL VM: not running' >&2; exit 1; }
exec orb run -m "$VM" bash -lc 'export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"; root="$1"; shift; exec python3 "$root/scripts/lib/health_engine.py" "$root" "$@"' bash "$ROOT" "$@"
