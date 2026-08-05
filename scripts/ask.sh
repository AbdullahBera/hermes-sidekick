#!/usr/bin/env bash
# One-shot prompt to Hermes (non-interactive). Runs inside the VM.
# Usage: ./scripts/ask.sh "your task or question"
set -euo pipefail
VM="${HERMES_VM:-hermes}"
[ "$#" -gt 0 ] || { echo "usage: $0 \"prompt\"" >&2; exit 1; }
PROMPT="$*"
# Pass the prompt as a positional arg ($1) so quoting/spaces are safe.
orb run -m "$VM" bash -lc '
  export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
  hermes -z "$1"
' _ "$PROMPT"
