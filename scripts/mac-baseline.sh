#!/usr/bin/env bash
# Read-only Phase 0 baseline for the Mac host: hardware, memory headroom, OrbStack VMs and
# their host shares, home-folder permissions seen by other local users, and installed model
# runtimes. It changes nothing and never starts a stopped VM. Run it at idle, then again with a
# model loaded (and later with Sim running) to measure headroom (test B5).
# Output can include local paths and VM addresses: keep saved copies out of the repository.
#   ./scripts/mac-baseline.sh                 # report
#   CONDUCTOR_DIR=~/elsewhere ./scripts/mac-baseline.sh
set -uo pipefail
[ "$(uname -s)" = Darwin ] || { echo 'FAIL: run this on the Mac host' >&2; exit 1; }
VM="${HERMES_VM:-hermes}"
CONDUCTOR_DIR="${CONDUCTOR_DIR:-$HOME/conductor}"
section() { printf '\n== %s ==\n' "$1"; }

section 'Hardware'
echo "model=$(sysctl -n hw.model) chip=$(sysctl -n machdep.cpu.brand_string)"
echo "memory_gib=$(( $(sysctl -n hw.memsize) / 1073741824 )) macos=$(sw_vers -productVersion)"
limit="$(sysctl -n iogpu.wired_limit_mb 2>/dev/null || echo unavailable)"
echo "iogpu.wired_limit_mb=$limit (0 means the macOS default GPU memory limit)"

section 'Memory'
memory_pressure 2>/dev/null | tail -n 1
echo "swap: $(sysctl -n vm.swapusage)"
page="$(sysctl -n hw.pagesize)"
vm_stat | awk -v page="$page" '
  /Pages free/ {free=$3} /Pages inactive/ {inactive=$3} /Pages wired/ {wired=$4}
  /occupied by compressor/ {compressed=$5}
  END { gsub(/\./, "", free); gsub(/\./, "", inactive); gsub(/\./, "", wired); gsub(/\./, "", compressed)
        printf "free+inactive_gib=%.1f wired_gib=%.1f compressed_gib=%.1f\n",
          (free + inactive) * page / 2^30, wired * page / 2^30, compressed * page / 2^30 }'

section 'Largest processes (resident MiB)'
ps -axo rss=,comm= | sort -rn | head -n 12 |
  awk '{ n = split($2, parts, "/"); printf "%8.0f  %s\n", $1 / 1024, parts[n] }'

section 'Model runtimes on PATH'
for tool in mlx_lm.server mlx_lm.generate ollama llama-server; do
  if command -v "$tool" >/dev/null 2>&1; then echo "present: $tool"; else echo "absent:  $tool"; fi
done

section 'OrbStack'
if ! command -v orb >/dev/null 2>&1; then
  echo 'orb: not installed'
elif [ "$(orb status 2>/dev/null)" != Running ]; then
  echo 'orb: engine not running (not started by this script)'
else
  orb version 2>/dev/null | head -n 1
  orb list 2>/dev/null | awk '{ print $1, $2, $3, $4, $5, $6, $7 }'   # name state distro release arch size
  if orb list | awk -v vm="$VM" '$1 == vm && $2 == "running" { found=1 } END { exit !found }'; then
    shares="$(orb run -m "$VM" sh -c "awk '\$0 ~ / - (virtiofs|fuse[.][a-z-]+|9p|nfs4?|vboxsf) / { n++ } END { print n+0 }' /proc/self/mountinfo" 2>/dev/null)"
    echo "vm=$VM host_share_mounts=${shares:-unknown} (0 is required before private data, test P9)"
  else
    echo "vm=$VM not running; host-share check skipped"
  fi
fi

section 'Home-folder permissions other local users would see'
echo 'Other users are normally in group "staff". Group/other read or execute here would let a'
echo 'separate coding-worker account traverse into these folders (test C2).'
for path in "$HOME" "$CONDUCTOR_DIR" "$CONDUCTOR_DIR/workspaces" "$CONDUCTOR_DIR/repos"; do
  [ -e "$path" ] && stat -f '%Sp %Su:%Sg %N' "$path"
done
if [ -d "$CONDUCTOR_DIR/workspaces" ]; then
  for path in "$CONDUCTOR_DIR"/workspaces/*; do
    [ -d "$path" ] && stat -f '%Sp %Su:%Sg %N' "$path"
  done
fi
exit 0
