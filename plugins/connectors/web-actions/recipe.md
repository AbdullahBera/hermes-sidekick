# Web Actions — private browser automation

Drive a real browser to do live web tasks — look something up on the actual page, fill a form,
build a cart, run a check-in — **inside your VM**, not a vendor's cloud. This is the category's
frontier capability, done privately. The engine is Hermes's built-in `browser` toolset
(Playwright/Chromium via `agent-browser`).

## Security posture (the product, not just the tool)
The raw Hermes browser follows the instructions in
[`../../../config/SOUL.md`](../../../config/SOUL.md). These are behavioral policies,
not an enforced approval boundary:
- **Stop before money or your name.** It builds a task to the final screen (cart, form, check-in)
  and **stops** before checkout / order / send / booking-confirm — shows the total + what's in it
  + where it's going, and waits for an explicit "yes".
- **Read the live source before acting** on anything time-sensitive (deadlines, prices, check-in
  windows) — never from memory.
- **Sensitive data never enters the thread or a form it fills** — passwords, full card numbers,
  passport/ID, 2FA codes. You provide those directly.
- **Cite what it found** (source link); only does the task asked.
- **Local browser execution:** the browser runs in *your* VM. Host mounts and account
  permissions determine its actual access. (A cloud option, Browserbase,
  exists in Hermes but needs an API key and sends pages to a third party — off by default here.)

## Setup
The `browser` toolset ships enabled with Hermes, but the local engine has to be installed:
```bash
# Chromium (Playwright) + the agent-browser wrapper:
hermes tools post-setup agent_browser        # fetches Chromium
npm install -g agent-browser                 # the wrapper CLI (see the gotcha below)
hermes tools list | grep browser             # confirm: ✓ enabled  browser
```
**Gotcha (found on arm64 Linux):** `hermes tools post-setup agent_browser` may report
"already installed" while `agent-browser` is in fact missing from PATH. If the browser tool says
"Chrome isn't installed," run `npm install -g agent-browser` explicitly and restart the gateway
(`sudo systemctl restart hermes-gateway`). Check the browser's actual sandbox configuration;
the controlled adapter below keeps Chromium's sandbox enabled on arm64 Linux.

## Verify
- "Open example.com and read me the heading" → returns the page's H1.
- "Add <thing> to my cart on <store> and stop before checkout" → builds the cart, shows the
  total, waits for your go.

## Config
`connectors.web_actions` (profile): `allowed_domains` (optional allowlist),
`always_confirm_before_submit` (keep `true`).

## Controlled workflow and performance

The opt-in [control service](../../../docs/CONTROL.md) adds durable inspection/preparation tasks,
exact owner approval, one-attempt submission transport, and pause/disconnect. It supports ordinary
server-rendered POST forms with page JavaScript disabled. Use its restricted MCP configuration
under a separate agent OS identity; do not expose raw browser/shell tools in that deployment.
A chat "yes" does not grant this service owner authority.

Earlier raw-tool runs were slow, but did not establish the cause or a GPU requirement. The new
local appointment fixture runs inspection and submission below a second each on the reference
Linux VM, with Chromium sandboxing enabled. That measures the bounded browser path, not model
reasoning, real-site latency or general task success. Run the tests in CONTROL.md and benchmark
the intended sites before making performance promises. Use the service's task cancellation or
pause control to terminate its browser process group.

## Notes
- Real-time watching (sit on a page, alert on change) pairs with this — a backlog item.
- Keep the ask-first rule sacred: this is the capability most able to spend money or act as you.
