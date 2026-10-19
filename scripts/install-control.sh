#!/usr/bin/env bash
# Install the control broker on a dedicated Linux VM. Checks by default; never starts services.
# sudo ./scripts/install-control.sh --check --agent-user sidekick-agent
# sudo ./scripts/install-control.sh --apply --agent-user sidekick-agent
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE=check
AGENT_USER=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --check) MODE=check; shift ;;
    --apply) MODE=apply; shift ;;
    --agent-user) [ "$#" -ge 2 ] || exit 2; AGENT_USER="$2"; shift 2 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo 'Use --check or --apply and --agent-user <dedicated Linux user>' >&2; exit 2 ;;
  esac
done
[[ "$AGENT_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo 'Specify a dedicated, unprivileged --agent-user' >&2; exit 2; }
[ "$(uname -s)" = Linux ] && [ "$(id -u)" = 0 ] || { echo 'Run this installer as the VM administrator on Linux' >&2; exit 1; }
id "$AGENT_USER" >/dev/null 2>&1 || { echo 'Create the dedicated agent OS account first (without sudo access)' >&2; exit 1; }
[ "$(id -u "$AGENT_USER")" -ne 0 ] && [ "$AGENT_USER" != sidekick-control ] || { echo 'Agent and control identities must be separate' >&2; exit 1; }
for tool in python3 node npm systemctl runuser install; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' \
  || { echo 'Python 3.11+ is required' >&2; exit 1; }
python3 -c 'import ensurepip, venv' >/dev/null 2>&1 \
  || { echo 'Install the Python venv/ensurepip package before running the installer' >&2; exit 1; }
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) process.exit(1)' \
  || { echo 'Node 20+ is required' >&2; exit 1; }
if id -nG "$AGENT_USER" | tr ' ' '\n' | grep -Eq '^(sudo|wheel|admin|docker|lxd|incus|disk)$'; then
  echo 'Agent belongs to a privileged group; use an unprivileged account' >&2; exit 1
fi
if command -v sudo >/dev/null && sudo -n -l -U "$AGENT_USER" >/dev/null 2>&1; then
  echo 'Agent has sudo privileges; owner approvals would be bypassable' >&2; exit 1
fi
if awk ' / - (virtiofs|9p|vboxsf|fuse.vmhgfs-fuse|fuse.orbstack) / {found=1} END {exit !found}' /proc/self/mountinfo; then
  echo 'Host filesystem sharing detected; use a VM without host shares for the isolated deployment' >&2; exit 1
fi
for location in /etc/systemd/system /opt /opt/hermes-sidekick-control /etc/systemd/system/sidekick-control.service /etc/systemd/system/sidekick-owner.service /var/lib/sidekick-control /var/lib/sidekick-owner /var/cache/sidekick-control; do
  if [ -L "$location" ]; then
    echo 'Refusing a symlink at a control installation path' >&2; exit 1
  fi
  if runuser -u "$AGENT_USER" -- test -w "$location"; then
    echo 'Agent can modify privileged installation paths' >&2; exit 1
  fi
done
if [ -d /opt/hermes-sidekick-control ]; then
  # Previously installed code and interpreters must not be replaceable through a
  # writable nested file/directory or a link, even if their parent is root-owned.
  python3 - "$AGENT_USER" <<'PY'
import os, pwd, stat, sys
user = pwd.getpwnam(sys.argv[1])
groups = set(os.getgrouplist(user.pw_name, user.pw_gid))
for directory, dirs, files in os.walk('/opt/hermes-sidekick-control', followlinks=False):
    for path in [directory, *(os.path.join(directory, n) for n in dirs + files)]:
        info = os.stat(path)  # Follow packaged interpreter/node links to check the target.
        if info.st_uid == user.pw_uid or info.st_mode & stat.S_IWOTH or (info.st_gid in groups and info.st_mode & stat.S_IWGRP):
            sys.exit('Agent can change existing control code or an interpreter; repair ownership first')
PY
fi
if systemctl is-active --quiet sidekick-control || systemctl is-active --quiet sidekick-owner; then
  echo 'Stop the existing control and owner services before upgrading their code' >&2; exit 1
fi
AGENT_GROUP="$(id -gn "$AGENT_USER")"
[[ "$AGENT_GROUP" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo 'Unsupported agent group name' >&2; exit 1; }
echo 'Preflight passed: separate unprivileged agent and no detected host shares.'
[ "$MODE" = apply ] || exit 0

if ! id sidekick-control >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /var/lib/sidekick-control --shell /usr/sbin/nologin sidekick-control
fi
[ "$(id -u sidekick-control)" -ne "$(id -u "$AGENT_USER")" ] || exit 1
PREFIX=/opt/hermes-sidekick-control
install -d -m 0755 -o root -g root "$PREFIX" "$PREFIX/sidekick_control"
install -m 0644 -o root -g root "$ROOT"/sidekick_control/*.py "$ROOT"/sidekick_control/*.mjs \
  "$ROOT"/sidekick_control/package*.json "$PREFIX/sidekick_control/"
install -m 0644 -o root -g root "$ROOT/requirements-control.txt" "$PREFIX/requirements-control.txt"
install -d -m 0755 -o root -g root "$PREFIX/sidekick_control/static"
install -m 0644 -o root -g root "$ROOT"/sidekick_control/static/* "$PREFIX/sidekick_control/static/"
npm --prefix "$PREFIX/sidekick_control" ci --ignore-scripts
python3 -m venv "$PREFIX/adapter-venv"
"$PREFIX/adapter-venv/bin/python" -m pip install -r "$PREFIX/requirements-control.txt"
install -d -m 0700 -o sidekick-control -g "$AGENT_GROUP" /var/lib/sidekick-control /var/cache/sidekick-control
# Download only the browser into the service's private cache. Native dependencies must be
# installed by the administrator using Playwright's documented Linux dependency command.
runuser -u sidekick-control -- env PLAYWRIGHT_BROWSERS_PATH=/var/cache/sidekick-control \
  node "$PREFIX/sidekick_control/node_modules/playwright/cli.js" install chromium
NODE_BIN="$(command -v node)"
PYTHON_BIN="$(command -v python3)"
cat > /etc/systemd/system/sidekick-control.service <<UNIT
[Unit]
Description=Sidekick owner-controlled task execution
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=sidekick-control
Group=$AGENT_GROUP
WorkingDirectory=$PREFIX
ExecStart=$PYTHON_BIN -m sidekick_control.service
Environment=SIDEKICK_ISOLATED_SERVICE=1
Environment=PLAYWRIGHT_BROWSERS_PATH=/var/cache/sidekick-control
Environment=PATH=$(dirname "$NODE_BIN"):/usr/local/bin:/usr/bin:/bin
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
RuntimeDirectory=sidekick-control
RuntimeDirectoryMode=0750
StateDirectory=sidekick-control
StateDirectoryMode=0700
CacheDirectory=sidekick-control
CacheDirectoryMode=0700
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
KillMode=control-group
TimeoutStopSec=10
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/sidekick-control.service
cat > /etc/systemd/system/sidekick-owner.service <<UNIT
[Unit]
Description=Sidekick private owner controls
Requires=sidekick-control.service
After=sidekick-control.service
[Service]
Type=simple
User=sidekick-control
Group=$AGENT_GROUP
WorkingDirectory=$PREFIX
ExecStart=$PYTHON_BIN -m sidekick_control.owner_web
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
StateDirectory=sidekick-owner
StateDirectoryMode=0700
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
KillMode=control-group
TimeoutStopSec=10
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/sidekick-owner.service
systemctl daemon-reload
systemctl enable sidekick-control.service sidekick-owner.service
cat <<'DONE'
Installed, not started. Follow docs/CONTROL.md to:
  1. Start the service and confirm it is paused.
  2. Start private owner controls, tunnel through SSH, and connect exact browser origins.
  3. Register only the restricted Sidekick MCP adapter with the dedicated Hermes account.
  4. Run the fixture acceptance checks before approving any real account action.
Keep the previous development schedules paused; this installer never resumes them.
DONE
