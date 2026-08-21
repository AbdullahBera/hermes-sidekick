#!/usr/bin/env bash
# bootstrap.sh — one command: from nothing to a Hermes runtime with the onboarder ready.
#
# Local Mac / OrbStack path (the reference setup). It provisions the runtime and stages the
# repo + your model key inside the VM, then hands you to the AI onboarder, which walks you
# through channels, connectors, and automations (pausing only for human checkpoints).
#
#   ./onboarder/bootstrap.sh
#
# Idempotent — safe to re-run. Secrets are entered silently and stored ONLY in the VM.
set -euo pipefail

VM="${HERMES_VM:-hermes}"
REPO="${HERMES_REPO:-https://github.com/AbdullahBera/hermes-sidekick}"
say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

say "1/5  OrbStack"
if ! command -v orb >/dev/null; then
  echo "Install OrbStack first:  brew install --cask orbstack   (or https://orbstack.dev)"; exit 1
fi
[ "$(orb status 2>/dev/null)" = "Running" ] || { echo "starting OrbStack…"; open -ga OrbStack || true; }

say "2/6  VM '$VM' (arm64 Ubuntu)"
if ! orb list 2>/dev/null | grep -qE "^${VM}\b"; then
  orb create ubuntu "$VM"
else
  echo "VM already exists."
fi

say "3/6  Base deps (a fresh VM has none of these; without xz-utils the Hermes installer's node
     extraction dies silently and leaves you with no working 'hermes')"
orb run -m "$VM" bash -lc 'sudo apt-get update -y >/dev/null && sudo apt-get install -y git xz-utils ca-certificates curl >/dev/null && echo "deps: git + xz-utils ok"'

say "4/6  Hermes runtime (bundles Python 3.11, node, ripgrep, ffmpeg)"
orb run -m "$VM" bash -lc 'export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"; command -v hermes >/dev/null || curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'

say "5/6  Repo (catalog + recipes + playbook) into the VM"
orb run -m "$VM" bash -lc "test -d ~/hermes-sidekick/.git || git clone --depth 1 '$REPO' ~/hermes-sidekick; cd ~/hermes-sidekick && git pull --ff-only 2>/dev/null || true; echo repo: \$(pwd)"

say "6/6  Model API key (stored only in the VM's ~/.hermes/.env, chmod 600)"
if orb run -m "$VM" bash -lc 'grep -q "^ANTHROPIC_API_KEY=" ~/.hermes/.env 2>/dev/null'; then
  echo "Anthropic key already set."
else
  read -rsp "Anthropic API key (console.anthropic.com → API Keys): " K; echo
  printf 'ANTHROPIC_API_KEY=%s\n' "$K" | orb run -m "$VM" bash -lc 'mkdir -p ~/.hermes && cat >> ~/.hermes/.env && chmod 600 ~/.hermes/.env && echo saved'
  unset K
fi

cat <<DONE

Runtime is ready. Start the AI onboarder — it reads onboarder/playbook.md and sets up your
channel, connectors, and automations, pausing only for the human checkpoints (OAuth approve,
Signal captcha):

  orb run -m $VM bash -lc 'cd ~/hermes-sidekick && hermes "Act as the onboarder in onboarder/playbook.md and set me up."'

Or drive it from your Mac with a coding agent (e.g. Claude Code) pointed at this repo.
Prefer to do it by hand? Follow the plugin recipes + docs/AUTHORING-PLUGINS.md.
DONE
