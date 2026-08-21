#!/usr/bin/env bash
# provision.sh — turn a FRESH Ubuntu (arm64) host into a Hermes host.
#
# Run this ON THE NEW HOST (a spare-Mac OrbStack VM, a home box, or a cloud VM), NOT via orb.
# It installs the reproducible pieces — Hermes Agent, workspace-mcp, signal-cli, and the systemd
# units — so that scripts/migrate-state.sh can then drop in your ~20 MB of state. Services are
# installed but NOT started; you start them after migrating state and cutting Signal over
# (see docs/DEPLOY.md).
#
#   SIGNAL_NUMBER=+1XXXXXXXXXX ./provision.sh
#
# The phone number is a required env var and is only written into a local systemd unit on this
# host — never committed. This is a first-run scaffold: verify each step against
# https://github.com/NousResearch/hermes-agent and plugins/channels/signal/recipe.md.
set -euo pipefail

: "${SIGNAL_NUMBER:?set SIGNAL_NUMBER=+1XXXXXXXXXX (the Signal account this host will run)}"
USER_NAME="$(id -un)"; HOME_DIR="$HOME"
SIGNALCLI_VERSION="${SIGNALCLI_VERSION:-0.14.7}"
say() { printf '\n== %s ==\n' "$*"; }

say "1/6  Base deps (Java 25 for signal-cli; xz-utils so the Hermes installer can extract node)"
if command -v apt-get >/dev/null; then
  sudo apt-get update -y
  # signal-cli 0.14.7 needs Java 25 (class file 69) — JRE 21 fails. xz-utils is required or the
  # Hermes installer's node .tar.xz extraction dies silently (exit 0, broken install).
  sudo apt-get install -y openjdk-25-jre-headless xz-utils curl git unzip ca-certificates
else
  echo "Non-apt host — install a JRE 25+, xz-utils, curl, git, unzip yourself, then re-run." >&2; exit 1
fi

say "2/6  Hermes Agent (bundles Python 3.11, node, ripgrep, ffmpeg)"
if ! command -v hermes >/dev/null; then
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
else
  echo "hermes already present: $(hermes --version 2>/dev/null || true)"
fi

say "3/6  uv + workspace-mcp (Gmail/Calendar/Contacts connector)"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install workspace-mcp || uv tool upgrade workspace-mcp || true

say "4/6  signal-cli $SIGNALCLI_VERSION"
if ! command -v signal-cli >/dev/null; then
  mkdir -p "$HOME/.local/opt" "$HOME/.local/bin"
  url="https://github.com/AsamK/signal-cli/releases/download/v${SIGNALCLI_VERSION}/signal-cli-${SIGNALCLI_VERSION}.tar.gz"
  curl -fsSL "$url" | tar -xz -C "$HOME/.local/opt"
  ln -sf "$HOME/.local/opt/signal-cli-${SIGNALCLI_VERSION}/bin/signal-cli" "$HOME/.local/bin/signal-cli"
  echo "NOTE: on arm64, signal-cli may need the native libsignal-client patch — see"
  echo "      plugins/channels/signal/recipe.md if 'signal-cli --version' fails with a lib error."
fi
signal-cli --version || echo "(resolve the arm64 libsignal patch, then re-run)"

say "5/6  systemd units (installed, NOT started)"
sudo tee /etc/systemd/system/signal-cli.service >/dev/null <<UNIT
[Unit]
Description=signal-cli JSON-RPC HTTP daemon (Hermes agent Signal account)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${USER_NAME}
Environment=PATH=${HOME_DIR}/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${HOME_DIR}/.local/bin/signal-cli -a ${SIGNAL_NUMBER} daemon --http 127.0.0.1:8080
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT

# Gateway: use Hermes's OWN installer (canonical — won't drift when Hermes updates its unit).
export PATH="$HOME/.local/bin:$PATH"
hermes gateway install --system --run-as-user "${USER_NAME}" --no-start-now --start-on-login

sudo systemctl daemon-reload
sudo systemctl enable signal-cli.service

say "6/6  Done — host provisioned"
cat <<DONE
Next (see docs/DEPLOY.md):
  1. On your current machine:  ./scripts/migrate-state.sh --to ${USER_NAME}@<this-host>
     (stop signal-cli + hermes-gateway on the OLD host first — clean Signal cutover)
  2. On this host:  sudo systemctl start signal-cli && sudo systemctl start hermes-gateway
  3. Verify:  hermes cron run morning-brief   (delivers to Signal; triage labels; Google reads work)
Services are enabled but NOT started yet — start them only after state is migrated.
DONE
