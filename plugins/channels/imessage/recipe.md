# BlueBubbles ↔ Hermes-in-VM bridge — prepared config

BlueBubbles runs on the **Mac** (needs Messages.app). Hermes runs in the **OrbStack VM**.
They talk over OrbStack's **internal virtual network** (not your Wi‑Fi LAN), so the
macOS "Local Network" permission is **not required**.

```
 iMessage ─► Messages.app ─► BlueBubbles Server (Mac, :1234)
     ▲                                   │  webhook POST
     │ REST send                         ▼
 BlueBubbles REST  ◄── Hermes gateway (VM, :8645)   [agent loop → Claude API]
```

## 1. Addresses (live values — re-derive with `scripts/bridge-values.sh`)

| Direction | Address | Notes |
|---|---|---|
| VM → Mac (reach BlueBubbles) | `192.168.139.1:1234` | OrbStack host gateway; stable |
| Mac → VM (deliver webhook) | `192.168.139.41:8645` | VM IP; **can change on VM rebuild** — re-run the script |

> The adapter uses `WEBHOOK_HOST` for **both** the socket bind and the URL it
> registers with BlueBubbles (`bluebubbles.py:337`). `192.168.139.41` is the one
> value that is valid to bind *inside* the VM **and** reachable *from* the Mac.
> Do NOT use `127.0.0.1`/`0.0.0.0`/`localhost` — the code would advertise
> `http://localhost:…`, which points the Mac at itself.

## 2. VM `~/.hermes/.env` — bridge block

Add these to the VM's env (`orb run -m hermes bash -lc 'nano ~/.hermes/.env'`).
Secrets live only in the VM. Replace every `<...>` placeholder.

```bash
# --- BlueBubbles bridge ---
BLUEBUBBLES_SERVER_URL=http://192.168.139.1:1234
BLUEBUBBLES_PASSWORD=<STRONG_RANDOM_PASSWORD>          # == the BlueBubbles server password
BLUEBUBBLES_WEBHOOK_HOST=192.168.139.41
BLUEBUBBLES_WEBHOOK_PORT=8645
BLUEBUBBLES_WEBHOOK_PATH=/bluebubbles-webhook

# --- authorization (allowlist ONLY; never open) ---
BLUEBUBBLES_ALLOWED_USERS=<YOUR_IMESSAGE_HANDLE>       # the handle YOU text FROM: +1XXXXXXXXXX and/or you@icloud.com
BLUEBUBBLES_ALLOW_ALL_USERS=false
BLUEBUBBLES_HOME_CHANNEL=<YOUR_IMESSAGE_HANDLE>        # where proactive/cron messages are delivered (you)
```

The single `BLUEBUBBLES_PASSWORD` authenticates **both** directions: Hermes→REST
uses it as the API password; the inbound webhook carries it as `?password=…` and
the handler rejects mismatches with 401 (`bluebubbles.py:906`).

## 3. VM `~/.hermes/config.yaml` — platform block

```yaml
platforms:
  bluebubbles:
    enabled: true
    extra:
      send_read_receipts: true
      # require_mention: false      # DMs always respond; only gates group chats
```

## 4. BlueBubbles Server (Mac) settings — when installing

- Settings → **API**: enable the web server, port **1234**, set the **same**
  strong password used above, bind to **all interfaces (0.0.0.0)** so the VM can
  reach it at `192.168.139.1` (not localhost-only).
- Install the **Private API helper bundle** (typing indicators, tapbacks, read receipts).
- Webhook registration is **automatic** — Hermes registers
  `http://192.168.139.41:8645/bluebubbles-webhook?password=…` on gateway start
  (events: `new-message`, `updated-message`). No manual webhook entry needed.
- macOS: allow incoming connections for BlueBubbles if the firewall is on.

## 5. Start + verify

```bash
orb run -m hermes bash -lc 'export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"; hermes gateway run'
# then, one message from your phone, watch for 3 events:
orb run -m hermes bash -lc 'export PATH="$HOME/.hermes/bin:$HOME/.local/bin:$PATH"; hermes logs -f'
#   webhook received → model called → response sent
```

## 6. Blocker / open items

- **Secondary Apple ID: BLOCKED** — user cannot create new Apple accounts.
  The echo-loop fix (Messages.app on a *separate* Apple ID) is unresolved. The
  bridge values above are independent of this and are ready. Options: use an
  existing spare Apple ID, have someone provision one, or fall back to Photon
  (managed, no Apple account) — see conversation.
- VM IP stability: `192.168.139.41` may change on VM rebuild → re-run
  `scripts/bridge-values.sh` and update `BLUEBUBBLES_WEBHOOK_HOST`.
- BlueBubbles is not installed yet; these are prepared, not applied.
