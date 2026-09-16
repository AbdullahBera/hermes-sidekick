# Controlled tasks, browser work and owner controls

The new `sidekick_control` service is an executable, opt-in path alongside the existing
Hermes setup. It does not replace the agent engine or silently migrate the live account.
It provides durable work, exact owner approvals, bounded browser form execution, approved
memory, and cancellation/pause/disconnect controls. Existing scheduled automations stay off.

## What works in this version

- Tasks and events survive service restart in private SQLite. Reusing a request key returns
  the existing task; changing that key's action is rejected. Identical consequential actions
  with a different key also return the existing accepted/completed/uncertain task.
- Reads can resume after interruption, with a three-attempt ceiling. Failed reads can be
  retried explicitly. An interrupted submission becomes **uncertain**, never automatically
  resent. The owner checks the destination and records completed/not-completed evidence before
  another attempt is possible. A new attempt still needs a new exact approval.
- Browser inspection reads page text, links and form descriptions. Form preparation stores
  the exact target, chosen fields/button and page/form fingerprint; it does not submit or
  fill a remote form. Owner approval expires after 15 minutes and is tied to the exact digest
  and connector generation. Immediately before submission, the browser rechecks the page and
  form. Changes invalidate the attempt. Only one matching POST navigation is permitted; the
  final request uses a separate HTTP transport without automatic retries, because Chromium
  can otherwise resend a POST internally after a lost connection. An allowed-origin GET redirect
  may show the confirmation; redirects requiring another POST are blocked.
- The owner can inspect tasks, failures and event history; cancel work; pause all work managed
  by this service; disconnect the browser session; inspect approved memories; and forget one.
  Pausing prevents new execution and kills the active controlled browser process group.
  A request already sent may still complete at the destination, so its outcome is held for review.
- New memory is proposed and explicitly approved. Forget removes it from the memory store and
  redacts the source task payload. Prior model sessions, Hermes-native memory and backups are
  separate stores; this command does not erase those. No existing personal memory is imported
  automatically.

These are execution guarantees for **this service's path**. Raw Hermes shell/browser tools,
other MCPs, old cron jobs and other sessions are outside it. Do not market this as a universal
approval firewall for the existing same-user development VM.

## Browser support and limits

The initial adapter supports server-rendered pages and ordinary POST forms with text, email,
telephone, URL, date/time, numeric, textarea and single-select fields. It deliberately disables
page JavaScript and blocks scripts, images, fonts and media; a website script cannot secretly
submit while the agent is inspecting or entering fields. Login/password forms, file uploads,
duplicate field names, pages exceeding the bounded review, script-driven applications and
unsupported controls require human handoff.
Payment/identity workflows are outside this initial supported set. Field-name checks are not
semantic detection of every sensitive field; the owner must review the proposal.

This is an appointment/form workflow, not a universal autonomous browser. An HTTP success means
the approved submission received a response, not that a business confirmed a booking. Inspect
the returned confirmation. The service does not retry uncertain outcomes.

Only exact owner-configured HTTPS origins are accessible. Public IPv4 DNS is checked and pinned
for the browser process; private/link-local addresses and unlisted origins/redirects are blocked.
IPv6-only origins are currently unsupported. `--dev` additionally permits explicit loopback
fixture origins. Browser sandboxing stays enabled; a sandbox startup failure is reported, not
silently worked around. GETs can have side effects on badly designed websites: navigation is
not a universal proof of read-only server behavior. Use trusted origins and minimal account access.

## The trust boundary

The owner and agent use **different Unix sockets**. Owner methods are absent from the agent
API even if the request includes a forged role. The owner socket is mode 0600; the agent socket
is 0660 under the agent group, in a directory the agent cannot modify. The database and browser
storage belong to the control service account, with directory mode 0700. Owner-supplied
Playwright storage state never appears in agent responses. Disconnect clears the broker's copy,
invalidates pending actions and stops the active browser; it is not provider-side revocation.
Revoke sessions at the provider too when necessary. Keep export files/backups private.

**Production needs a separate OS identity for the agent, with no sudo, privileged groups,
readable control credentials, writable service code or host filesystem shares.** The installer
checks this baseline and refuses the current permissive shared-host style of deployment.
Owner authority cannot be protected from an agent that can become root. Browser sandboxing
reduces renderer risk; this is not a claim of immunity to OS/browser vulnerabilities.

## Local fixture development (no real accounts)

```bash
npm --prefix sidekick_control ci --ignore-scripts
node sidekick_control/node_modules/playwright/cli.js install chromium
python3 -m unittest discover -s tests -p 'test_control.py' -v
npm --prefix sidekick_control test
```

The browser tests use a local fictional appointment server, measure timings, check changed-form
rejection, and exercise owner approval across a service restart. They do not text anyone or
connect to a real account. `--dev` uses the current OS identity for both sides, so it tests
protocol behavior but is **not** a privilege boundary.

To inspect the local service manually, choose private temporary directories and run:

```bash
python3 -m sidekick_control.service --dev --state /tmp/sidekick-demo-state --sockets /tmp/sidekick-demo-sockets
# In another terminal:
python3 -m sidekick_control.cli --socket /tmp/sidekick-demo-sockets/owner.sock status
```

No work runs until the owner connects an origin and resumes the worker. Never import real
account storage into a same-user development instance.

## Dedicated Linux VM deployment

Use a fresh VM without host shares, Python 3.11+ with venv/ensurepip, Node 20+, npm, systemd and a dedicated
unprivileged Hermes account. This is separate from the live development profile. Install
browser OS dependencies using Playwright's Linux prerequisites before the browser acceptance run.

```bash
sudo ./scripts/install-control.sh --check --agent-user sidekick-agent
sudo ./scripts/install-control.sh --apply --agent-user sidekick-agent
sudo systemctl start sidekick-control
cd /opt/hermes-sidekick-control
sudo -u sidekick-control python3 -m sidekick_control.cli status
```

The installer leaves the service stopped and enables it for future boots. A fresh database is
paused; a later service restart preserves the owner's existing pause state. Installed code is
root-owned and the service has a private cache/state directory. No raw Google credentials are
copied. Install Hermes separately under the unprivileged account, use the restricted configuration
in `config/controlled-hermes.example.yaml`, and verify its actual exposed tool list before
connecting accounts. Use `hermes chat --toolsets mcp-sidekick` for the restricted CLI. The
Sidekick MCP adapter supports proposals, task status, cancellation, read retries, approved-memory
reads and event cursors. It has no owner approval or resume capability.

The owner connects an exact origin (optionally with a private Playwright storage-state export),
reviews a prepared task including its target, page, fields, button, digest and expiry, then approves:

```bash
sudo -u sidekick-control python3 -m sidekick_control.cli connect-browser --origin https://example.com
sudo -u sidekick-control python3 -m sidekick_control.cli resume
sudo -u sidekick-control python3 -m sidekick_control.cli tasks
sudo -u sidekick-control python3 -m sidekick_control.cli task TASK_ID
sudo -u sidekick-control python3 -m sidekick_control.cli approve TASK_ID --digest EXACT_REVIEWED_DIGEST
sudo -u sidekick-control python3 -m sidekick_control.cli pause
sudo -u sidekick-control python3 -m sidekick_control.cli disconnect-browser
sudo -u sidekick-control python3 -m sidekick_control.cli memories
sudo -u sidekick-control python3 -m sidekick_control.cli forget MEMORY_ID
```

All commands run from `/opt/hermes-sidekick-control` on the VM. Stop the service before updating
its code or taking a consistent private backup of `/var/lib/sidekick-control`. On restore, start
paused for review; interrupted external tasks remain uncertain. Do not run two service instances
against one store. The service takes an exclusive process lock. The owner CLI is the approval
surface in this version; a verified messaging or web approval surface is future work. A plain
chat “yes” is never treated as an authenticated owner approval.

`status` includes worker health. A fatal queue/database error exits the service so systemd
can restart it and recover interrupted work, instead of leaving a silently dead worker behind.
The service installer has not yet been accepted on a fresh second-user VM; the fixture suite
tests execution and protocol behavior without installing system services.

## Conversation behavior

Use the task's concise `message` plus relevant result evidence. Say “prepared” while awaiting
approval, “working” while running, and “may have gone through” for uncertain outcomes. Never
report success merely because work was queued or the process restarted. Keep the same request
key across a repeated tool call. Don't include identifiers/digests in ordinary conversational
updates; direct approval review to the owner controls. When the user asks about progress, check
the durable task instead of guessing or starting it again.

Fetch approved memories only when useful; save stable preferences rather than task chatter.
Read event updates after the last seen cursor and combine related changes into one useful
update. Do not poll in a tight loop. Unsolicited scheduled follow-ups remain disabled during
development; this release provides durable updates to retrieve in conversation, not a new
background message sender.
