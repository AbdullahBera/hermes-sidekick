# Web Actions — private browser automation

Drive a real browser to do live web tasks — look something up on the actual page, fill a form,
build a cart, run a check-in — **inside your VM**, not a vendor's cloud. This is the category's
frontier capability, done privately. The engine is Hermes's built-in `browser` toolset
(Playwright/Chromium via `agent-browser`).

## Security posture (the product, not just the tool)
The raw ability to click around the web is only useful if it's *safe*. The hard rules
(in [`../../../config/SOUL.md`](../../../config/SOUL.md), always injected) are:
- **Stop before money or your name.** It builds a task to the final screen (cart, form, check-in)
  and **stops** before checkout / order / send / booking-confirm — shows the total + what's in it
  + where it's going, and waits for an explicit "yes".
- **Read the live source before acting** on anything time-sensitive (deadlines, prices, check-in
  windows) — never from memory.
- **Sensitive data never enters the thread or a form it fills** — passwords, full card numbers,
  passport/ID, 2FA codes. You provide those directly.
- **Cite what it found** (source link); only does the task asked.
- **Private by construction:** the browser runs in *your* VM. (A cloud option, Browserbase,
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
(`sudo systemctl restart hermes-gateway`). Chromium itself runs fine on arm64 (it just needs
`--no-sandbox`, which Hermes auto-injects in the VM).

## Verify
- "Open example.com and read me the heading" → returns the page's H1.
- "Add <thing> to my cart on <store> and stop before checkout" → builds the cart, shows the
  total, waits for your go.

## Config
`connectors.web_actions` (profile): `allowed_domains` (optional allowlist),
`always_confirm_before_submit` (keep `true`).

## Notes
- Real-time watching (sit on a page, alert on change) pairs with this — a backlog item.
- Keep the ask-first rule sacred: this is the capability most able to spend money or act as you.
