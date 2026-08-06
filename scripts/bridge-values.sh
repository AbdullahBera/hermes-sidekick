#!/usr/bin/env bash
# Print the current OrbStack VM <-> Mac bridge addresses for the BlueBubbles setup.
# OrbStack can reassign the VM IP across rebuilds — re-run this to refresh values.
set -euo pipefail
VM="${HERMES_VM:-hermes}"

VM_IP=$(orb run -m "$VM" bash -lc 'ip -4 addr show | grep -oE "inet [0-9.]+" | awk "{print \$2}" | grep -v "^127" | head -1')
HOST_GW=$(orb run -m "$VM" bash -lc 'ip route | awk "/default/ {print \$3; exit}"')

echo "VM IP  (Mac reaches VM here; webhook bind + advertised host): $VM_IP"
echo "Host GW (VM reaches Mac / BlueBubbles here):                  $HOST_GW"
echo
echo "# --- paste into the VM's ~/.hermes/.env (secrets stay in the VM) ---"
echo "BLUEBUBBLES_SERVER_URL=http://${HOST_GW}:1234"
echo "BLUEBUBBLES_WEBHOOK_HOST=${VM_IP}"
echo "BLUEBUBBLES_WEBHOOK_PORT=8645"
echo "BLUEBUBBLES_WEBHOOK_PATH=/bluebubbles-webhook"
