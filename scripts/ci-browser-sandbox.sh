#!/usr/bin/env bash
# Hosted Ubuntu runner only: allow the downloaded Chromium binaries to create their
# sandbox namespaces. Does not disable Chromium sandboxing or the global AppArmor gate.
set -euo pipefail
[ "${GITHUB_ACTIONS:-}" = true ] && [ "$(uname -s)" = Linux ] \
  || { echo 'This helper is only for disposable GitHub Actions Linux runners' >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
browser_check() {
  node --input-type=module <<'JS'
import { chromium } from './sidekick_control/node_modules/playwright/index.mjs';
const browser = await chromium.launch({headless:true, chromiumSandbox:true});
await browser.close();
console.log('Sandboxed Chromium startup passed. No sites or accounts opened.');
JS
}
if browser_check; then exit 0; fi
[ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null)" = 1 ] \
  || { echo 'Browser startup failed without an AppArmor namespace restriction; inspect the error above' >&2; exit 1; }
POLICY="$(mktemp)"
trap 'rm -f "$POLICY"' EXIT
python3 - > "$POLICY" <<'PY'
import os, re
from pathlib import Path
cache=Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH', str(Path.home()/'.cache/ms-playwright')))
paths=sorted(p.resolve() for p in cache.rglob('*') if p.is_file() and p.name in ('chrome','chrome-headless-shell','headless_shell'))
if not paths: raise SystemExit('No downloaded Chromium executables found')
print('abi <abi/4.0>,\ninclude <tunables/global>')
for i,path in enumerate(paths):
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)):
        raise SystemExit('Unsupported browser path in CI profile')
    print(f'profile sidekick-ci-chromium-{i} "{path}" flags=(unconfined) {{\n  userns,\n}}')
PY
sudo apparmor_parser -r "$POLICY"
browser_check
