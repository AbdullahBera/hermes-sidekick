#!/usr/bin/env bash
# Open an interactive Hermes chat inside the VM.
# Run this from a real terminal (it needs a TTY).
set -euo pipefail
VM="${HERMES_VM:-hermes}"
exec orb run -m "$VM" bash -lc '
  export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"
  hermes
'
