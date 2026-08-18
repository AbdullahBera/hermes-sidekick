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
#   ./scripts/sync.sh --apply    # deploy the safe pieces (SOUL.md; create profile if missing)
#
# What it does on --apply:
#   • SOUL.md  -> ~/.hermes/SOUL.md   (backup first; reload gateway after)
#   • profile.yaml: create from the example ONLY if missing; NEVER overwrites (it's your
#     VM-only config and may hold personal settings).
#   • Cron prompts: REPORTED, not deployed. They live inline in ~/.hermes/cron/jobs.json and
#     carry hand-tuning (channel voice, timezone). Rendering them from templates is a later
#     step (needs the prompt-reconciliation decision) — this tool won't clobber them.
set -euo pipefail

VM="${HERMES_VM:-hermes}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="check"
case "${1:-}" in
  --apply) MODE="apply" ;;
  ""|--check) MODE="check" ;;
  -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1 (use --check or --apply)" >&2; exit 2 ;;
esac

vm() { orb run -m "$VM" bash -lc "$1"; }
hr() { printf '%s\n' "----------------------------------------------------------------"; }
changed=0

echo "sync ($MODE) — repo: $ROOT  vm: $VM"
hr

# 1) SOUL.md — the persona + all hard rules. Clean, high-value deploy.
LOCAL_SOUL="$ROOT/config/SOUL.md"
if vm 'cat ~/.hermes/SOUL.md' 2>/dev/null | diff -q - "$LOCAL_SOUL" >/dev/null 2>&1; then
  echo "SOUL.md            : in sync ✓"
else
  echo "SOUL.md            : DRIFT — repo differs from VM"
  changed=1
  if [ "$MODE" = apply ]; then
    vm 'cp ~/.hermes/SOUL.md ~/.hermes/SOUL.md.pre-sync.bak'
    cat "$LOCAL_SOUL" | vm 'cat > ~/.hermes/SOUL.md'
    echo "                     -> deployed (backup: ~/.hermes/SOUL.md.pre-sync.bak)"
    SOUL_APPLIED=1
  else
    echo "                     (run --apply to deploy; diff below)"
    vm 'cat ~/.hermes/SOUL.md' 2>/dev/null | diff - "$LOCAL_SOUL" | sed 's/^/                     /' || true
  fi
fi

# 2) profile.yaml — VM-only user config. Validate; create if missing; NEVER overwrite.
if vm 'test -f ~/.hermes/sidekick/profile.yaml'; then
  if cat "$ROOT/profile.example.yaml" >/dev/null && \
     vm 'python3 -c "import yaml,sys; yaml.safe_load(open(\"$HOME/.hermes/sidekick/profile.yaml\"))"' >/dev/null 2>&1; then
    echo "profile.yaml       : present + valid ✓ (left untouched)"
  else
    echo "profile.yaml       : present but INVALID YAML — fix it"; changed=1
  fi
else
  echo "profile.yaml       : MISSING"
  changed=1
  if [ "$MODE" = apply ]; then
    cat "$ROOT/profile.example.yaml" | vm 'mkdir -p ~/.hermes/sidekick && cat > ~/.hermes/sidekick/profile.yaml && chmod 600 ~/.hermes/sidekick/profile.yaml'
    echo "                     -> created from profile.example.yaml — EDIT IT before relying on it"
  fi
fi

# 3) Cron coverage — which enabled automations have a live cron. Report only.
hr
echo "Automations (repo plugin  ->  live cron):"
LIVE_CRONS="$(vm 'hermes cron list 2>/dev/null' | grep -iE "Name:" | sed -E "s/.*Name:[[:space:]]*//" | tr -d "\r" || true)"
for d in "$ROOT"/plugins/automations/*/; do
  id="$(basename "$d")"
  if printf '%s\n' "$LIVE_CRONS" | grep -qx "$id"; then
    echo "  $id  ->  live ✓"
  else
    echo "  $id  ->  NO cron (folds into another automation, or not wired)"
  fi
done
echo "Note: cron prompts are hand-tuned inline in jobs.json — this tool reports coverage but"
echo "does not overwrite prompt text. Reconcile tuning into the repo templates, then render."

# 4) reload the gateway if we changed SOUL.md
if [ "${SOUL_APPLIED:-0}" = 1 ]; then
  hr
  echo "Reloading gateway so the new SOUL.md loads at next session…"
  vm 'sudo systemctl restart hermes-gateway' >/dev/null 2>&1 && echo "gateway: active ✓" || echo "gateway: restart it manually (sudo systemctl restart hermes-gateway)"
fi

hr
if [ "$MODE" = check ] && [ "$changed" = 1 ]; then
  echo "Drift found. Re-run with --apply to deploy the safe pieces."
elif [ "$MODE" = check ]; then
  echo "Everything in sync."
else
  echo "Apply complete."
fi
