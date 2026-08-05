#!/usr/bin/env bash
# Ensure the OrbStack engine and the `hermes` VM are running.
set -euo pipefail
VM="${HERMES_VM:-hermes}"

if ! command -v orb >/dev/null 2>&1; then
  echo "orb not found — install OrbStack: brew install --cask orbstack" >&2
  exit 1
fi

# Start the OrbStack engine if stopped.
if ! orb status >/dev/null 2>&1 || [ "$(orb status 2>/dev/null)" != "Running" ]; then
  echo "Starting OrbStack engine…"
  open -ga OrbStack || true
  for _ in $(seq 1 15); do
    [ "$(orb status 2>/dev/null)" = "Running" ] && break
    sleep 1
  done
fi

# Start the VM if it exists but isn't running.
if orb list 2>/dev/null | grep -qE "^${VM}[[:space:]]"; then
  if ! orb list 2>/dev/null | grep -qE "^${VM}[[:space:]]+running"; then
    echo "Starting VM '${VM}'…"
    orb start "$VM" || true
  fi
else
  echo "VM '${VM}' not found. Create it with: orb create ubuntu ${VM}" >&2
  exit 1
fi

orb list | (head -1; grep -E "^${VM}[[:space:]]")
