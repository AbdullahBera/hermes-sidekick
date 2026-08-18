#!/usr/bin/env bash
# sync.sh — deploy this repo's config into the VM. The repo is the source of truth.
#
# Why this exists: the repo holds canonical templates (SOUL.md, plugin prompts), but the
# running agent uses DEPLOYED copies in the VM. Without a deploy step they silently drift —
# e.g. a stale ~/.hermes/SOUL.md once ran the agent on an old, un-hardened ruleset. This is
# the deterministic deploy primitive the AI onboarder will eventually wrap.
#
# Safe by default:
#   ./scripts/sync.sh            # --check: report drift, change NOTHING
#   ./scripts/sync.sh --apply    # deploy into the VM (backs up what it overwrites)
#
# What --apply does:
#   • SOUL.md      -> ~/.hermes/SOUL.md              (backup; reload gateway after)
#   • profile.yaml : create from example ONLY if missing; NEVER overwrites your VM config
#   • prompts      -> each automation's prompt.md is deployed to ~/.hermes/sidekick/<id>.prompt.txt
#                     and, if the automation has a live cron, into that cron's prompt
#                     (hermes cron edit). jobs.json is backed up first.
# Crons run once/day, so prompts keep the runtime "load profile.yaml" model — no template
# engine needed. Delivery channel + timezone come from the cron's deliver field + profile.
set -euo pipefail

VM="${HERMES_VM:-hermes}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="check"
case "${1:-}" in
  --apply) MODE="apply" ;;
  ""|--check) MODE="check" ;;
  -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1 (use --check or --apply)" >&2; exit 2 ;;
esac

vm()   { orb run -m "$VM" bash -lc "$1"; }
hr()   { printf '%s\n' "----------------------------------------------------------------"; }
# id of a cron job by name (empty if none). Reads jobs.json; robust to list/dict shapes.
cron_id() {
  printf '%s' '
import json,os,sys
p=os.path.expanduser("~/.hermes/cron/jobs.json")
d=json.load(open(p)) if os.path.exists(p) else {}
jobs=d if isinstance(d,list) else d.get("jobs",d)
for j in (jobs.values() if isinstance(jobs,dict) else jobs):
    if isinstance(j,dict) and j.get("name")==sys.argv[1]:
        print(j.get("id","")); break
' | orb run -m "$VM" bash -lc "python3 - '$1'"
}
# current inline prompt of a cron job by id
cron_prompt() {
  printf '%s' '
import json,os,sys
d=json.load(open(os.path.expanduser("~/.hermes/cron/jobs.json")))
jobs=d if isinstance(d,list) else d.get("jobs",d)
for j in (jobs.values() if isinstance(jobs,dict) else jobs):
    if isinstance(j,dict) and j.get("id")==sys.argv[1]:
        sys.stdout.write(j.get("prompt","")); break
' | orb run -m "$VM" bash -lc "python3 - '$1'"
}

changed=0; jobs_backed_up=0
echo "sync ($MODE) — repo: $ROOT  vm: $VM"
hr

# 1) SOUL.md — persona + all hard rules.
LOCAL_SOUL="$ROOT/config/SOUL.md"
if vm 'cat ~/.hermes/SOUL.md' 2>/dev/null | diff -q - "$LOCAL_SOUL" >/dev/null 2>&1; then
  echo "SOUL.md            : in sync ✓"
else
  echo "SOUL.md            : DRIFT"; changed=1
  if [ "$MODE" = apply ]; then
    vm 'cp ~/.hermes/SOUL.md ~/.hermes/SOUL.md.pre-sync.bak'
    cat "$LOCAL_SOUL" | vm 'cat > ~/.hermes/SOUL.md'
    echo "                     -> deployed (backup: SOUL.md.pre-sync.bak)"; SOUL_APPLIED=1
  fi
fi

# 2) profile.yaml — VM-only user config. Validate; create if missing; NEVER overwrite.
if vm 'test -f ~/.hermes/sidekick/profile.yaml'; then
  if vm 'python3 -c "import yaml; yaml.safe_load(open(\"$HOME/.hermes/sidekick/profile.yaml\"))"' >/dev/null 2>&1; then
    echo "profile.yaml       : present + valid ✓ (left untouched)"
  else
    echo "profile.yaml       : present but INVALID YAML — fix it"; changed=1
  fi
else
  echo "profile.yaml       : MISSING"; changed=1
  if [ "$MODE" = apply ]; then
    cat "$ROOT/profile.example.yaml" | vm 'mkdir -p ~/.hermes/sidekick && cat > ~/.hermes/sidekick/profile.yaml && chmod 600 ~/.hermes/sidekick/profile.yaml'
    echo "                     -> created from example — EDIT IT before relying on it"
  fi
fi

# 3) Automation prompts — deploy to sidekick/<id>.prompt.txt and into the matching cron.
hr
echo "Automation prompts (repo prompt.md -> VM):"
for d in "$ROOT"/plugins/automations/*/; do
  id="$(basename "$d")"; pm="$d/prompt.md"
  [ -f "$pm" ] || continue

  # always mirror the template to sidekick/<id>.prompt.txt (referenced by other prompts)
  if [ "$MODE" = apply ]; then
    cat "$pm" | vm "mkdir -p ~/.hermes/sidekick && cat > ~/.hermes/sidekick/$id.prompt.txt"
  fi

  cid="$(cron_id "$id" | tr -d '[:space:]')"
  if [ -z "$cid" ]; then
    echo "  $id : no cron (file mirrored to sidekick/$id.prompt.txt)"
    continue
  fi
  if [ "$(cron_prompt "$cid")" = "$(cat "$pm")" ]; then
    echo "  $id : cron in sync ✓"
  else
    echo "  $id : cron DRIFT"; changed=1
    if [ "$MODE" = apply ]; then
      if [ "$jobs_backed_up" = 0 ]; then
        vm 'cp ~/.hermes/cron/jobs.json ~/.hermes/cron/jobs.json.pre-sync.bak'; jobs_backed_up=1
      fi
      cat "$pm" | vm "hermes cron edit '$cid' --prompt \"\$(cat)\"" >/dev/null
      echo "         -> deployed prompt into cron $cid"
    fi
  fi
done

# 4) reload gateway if SOUL changed
if [ "${SOUL_APPLIED:-0}" = 1 ]; then
  hr; echo "Reloading gateway…"
  vm 'sudo systemctl restart hermes-gateway' >/dev/null 2>&1 && echo "gateway: active ✓" || echo "gateway: restart manually"
fi

hr
if [ "$MODE" = check ] && [ "$changed" = 1 ]; then
  echo "Drift found. Re-run with --apply to deploy."
elif [ "$MODE" = check ]; then
  echo "Everything in sync."
else
  echo "Apply complete."
fi
