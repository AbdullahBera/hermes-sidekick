#!/usr/bin/env bash
# Health check: OrbStack engine, the VM, and Hermes itself.
set -euo pipefail
VM="${HERMES_VM:-hermes}"

echo "== OrbStack engine =="
orb status 2>&1 || true

echo
echo "== VM '${VM}' =="
orb list 2>&1 | grep -E "^${VM}[[:space:]]" || echo "(VM '${VM}' not found or not running)"

echo
echo "== Hermes =="
orb run -m "$VM" bash -lc '
  export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
  hermes --version 2>&1 | head -3
  echo
  grep -E "^  default:" ~/.hermes/config.yaml | sed "s/^/model /"
  if grep -q "^ANTHROPIC_API_KEY=." ~/.hermes/.env; then
    echo "ANTHROPIC_API_KEY: set"
  else
    echo "ANTHROPIC_API_KEY: MISSING"
  fi
' 2>&1 || echo "(could not reach Hermes in VM)"
