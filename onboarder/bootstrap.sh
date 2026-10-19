#!/usr/bin/env bash
# Provision and verify the Mac/OrbStack runtime. Re-running resumes from verified state.
# Human OAuth and Signal registration remain in onboarder/playbook.md.
# --launch opens an interactive Hermes chat after verification (uses your model API).
set -euo pipefail
VM="${HERMES_VM:-hermes}"
REPO="${HERMES_REPO:-https://github.com/AbdullahBera/hermes-sidekick}"
MODEL="${HERMES_MODEL:-claude-sonnet-5}"
LAUNCH=0
case "${1:-}" in
  '') ;;
  --launch) LAUNCH=1 ;;
  -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
  *) echo 'Usage: bootstrap.sh [--launch]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo 'Too many arguments' >&2; exit 2; }
say() { printf '\n== %s ==\n' "$*"; }
trap 'echo "Bootstrap stopped at a failed step. Repair it and rerun; existing credentials and profile are preserved." >&2' ERR

say '1/7 OrbStack'
command -v orb >/dev/null || { echo 'Install OrbStack first: brew install --cask orbstack' >&2; exit 1; }
if [ "$(orb status 2>/dev/null)" != Running ]; then
  open -ga OrbStack
  for _ in {1..30}; do
    [ "$(orb status 2>/dev/null)" = Running ] && break
    sleep 1
  done
fi
[ "$(orb status)" = Running ] || { echo 'OrbStack did not become ready within 30 seconds' >&2; exit 1; }

say "2/7 VM $VM"
VM_LIST="$(orb list)"
if ! awk -v vm="$VM" '$1 == vm { found=1 } END { exit !found }' <<< "$VM_LIST"; then
  orb create ubuntu "$VM"
elif ! awk -v vm="$VM" '$1 == vm && $2 == "running" { found=1 } END { exit !found }' <<< "$VM_LIST"; then
  orb start "$VM"
fi
orb run -m "$VM" bash -lc 'test "$(uname -s)" = Linux'

say '3/7 Base dependencies'
orb run -m "$VM" bash -lc '
  set -euo pipefail
  if ! command -v git >/dev/null || ! command -v xz >/dev/null || ! command -v curl >/dev/null || ! test -s /etc/ssl/certs/ca-certificates.crt; then
    sudo apt-get update -y
    sudo apt-get install -y git xz-utils ca-certificates curl
  fi
  git --version >/dev/null; xz --version >/dev/null; curl --version >/dev/null
  test -s /etc/ssl/certs/ca-certificates.crt
'

say '4/7 Hermes and gateway service (installed, not started)'
orb run -m "$VM" bash -lc '
  set -euo pipefail
  export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"
  if ! command -v hermes >/dev/null; then
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
  fi
  hermes --version >/dev/null
  python3 -c "import yaml" # sync requires the runtime YAML dependency
  system_loaded() { [ "$(systemctl show hermes-gateway --property=LoadState --value)" = loaded ]; }
  user_loaded() { [ "$(systemctl --user show hermes-gateway --property=LoadState --value)" = loaded ]; }
  if ! system_loaded && ! user_loaded; then
    if ! hermes gateway install --system --no-start-now --start-on-login; then
      echo "System service install failed; trying the supported user service."
      hermes gateway install --start-on-login --no-start-now
    fi
  fi
  if ! system_loaded && ! user_loaded; then
    echo "Gateway installation returned without a loaded service" >&2; exit 1
  fi
'

say '5/7 Catalog and onboarding playbook in VM'
# Pass user-supplied URL as an argument, never interpolate it into shell program text.
orb run -m "$VM" bash -lc '
  set -euo pipefail
  if [ ! -d "$HOME/hermes-sidekick/.git" ]; then
    git clone --depth 1 -- "$1" "$HOME/hermes-sidekick"
  else
    git -C "$HOME/hermes-sidekick" pull --ff-only
  fi
  cd "$HOME/hermes-sidekick"
  test -s onboarder/playbook.md; test -s profile.example.yaml
  test -s scripts/lib/sync_engine.py
' bash "$REPO"

say '6/7 Model key (silent input; saved only in VM)'
# Distinguish transport failure from missing credentials. Never print their contents.
KEY_STATE="$(orb run -m "$VM" bash -lc '
  set -euo pipefail
  cd "$HOME/hermes-sidekick"
  # key-state check: only present/missing; read/transport failures must propagate.
  python3 - <<'"'"'PY'"'"'
import sys
from pathlib import Path
sys.path.insert(0,"scripts/lib")
from sync_engine import env_values
key=env_values(Path.home()/".hermes/.env").get("ANTHROPIC_API_KEY", "")
print("present" if key and not any(c.isspace() for c in key) else "missing")
PY
')"
if [ "$KEY_STATE" = missing ]; then
  read -rsp 'Anthropic API key: ' K; echo
  [ -n "$K" ] && [[ "$K" != *[[:space:]]* ]] || { echo 'Key must be nonempty with no whitespace' >&2; exit 1; }
  printf '%s\n' "$K" | orb run -m "$VM" bash -lc '
    set -euo pipefail
    umask 077
    mkdir -p "$HOME/.hermes"
    python3 -c '\''import os,sys,tempfile
from pathlib import Path
p=Path.home()/".hermes/.env"
key=sys.stdin.read().strip()
if not key: raise SystemExit("Empty key")
lines=p.read_text().splitlines() if p.exists() else []
lines=[line for line in lines if not line.startswith("ANTHROPIC_API_KEY=")]
fd,name=tempfile.mkstemp(dir=p.parent)
with os.fdopen(fd,"w") as f: f.write("\n".join(lines+["ANTHROPIC_API_KEY="+key])+"\n")
os.replace(name,p)
'\''
  '
  unset K
elif [ "$KEY_STATE" != present ]; then
  echo 'Could not determine VM key state' >&2; exit 1
fi
orb run -m "$VM" bash -lc 'chmod 600 "$HOME/.hermes/.env"'

say '7/7 Safe initial profile and runtime verification'
orb run -m "$VM" bash -lc '
  set -euo pipefail
  export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"
  cd "$HOME/hermes-sidekick"
  python3 - "$1" <<'"'"'PY'"'"'
import sys
from pathlib import Path
import yaml
sys.path.insert(0,"scripts/lib")
from sync_engine import atomic_write, load_catalog, read_yaml, validate_profile
h=Path.home()/".hermes"
p=h/"sidekick/profile.yaml"
if not p.exists():
    profile=read_yaml(Path("profile.example.yaml"))
    # Enforce opt-in even when a checkout has an older example with enabled defaults.
    for section in ("channels","connectors","automations"):
        for block in profile[section].values(): block["enabled"]=False
    profile["core"]["model"]=sys.argv[1]
    config=read_yaml(h/"config.yaml")
    config.setdefault("model",{}).update(provider="anthropic", default=sys.argv[1])
    config["model"].pop("base_url",None)
    atomic_write(h/"config.yaml",yaml.safe_dump(config,sort_keys=False))
    atomic_write(p,yaml.safe_dump(profile,sort_keys=False))
validate_profile(read_yaml(p),load_catalog(Path(".")))
print("Profile verified; enable only the capabilities you choose during onboarding.")
PY
  hermes --version >/dev/null
' bash "$MODEL"

cat <<'DONE'

Runtime prerequisites verified. Account connections and message delivery are NOT verified yet.
The Mac filesystem may be shared into this VM; see docs/PRIVACY.md before enabling tools.
Continue with onboarder/playbook.md and record the trial in docs/ONBOARDING-TRIAL.md.

For interactive setup, rerun this command with --launch. In that chat, enter:
  Read onboarder/playbook.md. Resume my setup from the existing profile and verify each step.

Inside the VM use HERMES_LOCAL=1 for scripts/sync.sh and scripts/status.sh.
DONE
if [ "$LAUNCH" = 1 ]; then
  exec orb run -m "$VM" bash -lc 'export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"; cd "$HOME/hermes-sidekick"; exec hermes chat'
fi
