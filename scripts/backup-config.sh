#!/usr/bin/env bash
# Snapshot the VM's config.yaml and a REDACTED .env (secret values stripped)
# into docs/backups/ on the host. Never copies real secrets.
set -euo pipefail
VM="${HERMES_VM:-hermes}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/backups"
mkdir -p "$DIR"

orb run -m "$VM" bash -lc 'cat ~/.hermes/config.yaml' > "$DIR/config.yaml"

# Keep variable names, blank out every value: NAME=... -> NAME=<redacted>
orb run -m "$VM" bash -lc 'sed -E "s/^([A-Za-z_][A-Za-z0-9_]*)=.+/\1=<redacted>/" ~/.hermes/.env' \
  > "$DIR/env.redacted"

echo "Backed up to: $DIR"
echo "  - config.yaml"
echo "  - env.redacted   (all secret values redacted)"
