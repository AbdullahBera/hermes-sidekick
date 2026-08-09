# Signal transport — setup notes (VM)

Hermes' Signal connector talks to a **`signal-cli` daemon** (HTTP/JSON-RPC mode).
Used as the prototype transport while the iMessage/BlueBubbles Apple ID is blocked.
Transport-independent from the agent brain — swappable later.

## Tooling installed in the VM

| Component | Version | Location |
|---|---|---|
| Java (JRE) | openjdk-25 | apt; `update-alternatives` default |
| signal-cli | 0.14.7 | `~/.local/opt/signal-cli-0.14.7`, symlink `~/.local/bin/signal-cli` |
| libsignal native (arm64) | v0.99.1 | `/usr/lib/aarch64-linux-gnu/libsignal_jni.so` |

### The arm64 gotcha (important if signal-cli is upgraded)
signal-cli's bundled `libsignal-client-<ver>.jar` ships a Linux **x86_64** `.so`
and a macOS arm64 `.dylib`, but **no Linux-arm64 `.so`** — so it fails on this VM
with "Missing required native library dependency: libsignal-client".
Fix: drop in the matching community build from
[`exquo/signal-libs-build`](https://github.com/exquo/signal-libs-build):

```bash
# version MUST match the libsignal-client-<ver>.jar in ~/.local/opt/signal-cli-*/lib/
V=0.99.1
curl -fsSL -o /tmp/ls.tgz "https://github.com/exquo/signal-libs-build/releases/download/libsignal_v${V}/libsignal_jni.so-v${V}-aarch64-unknown-linux-gnu.tar.gz"
tar xf /tmp/ls.tgz -C /tmp
sudo cp /tmp/libsignal_jni.so /usr/lib/aarch64-linux-gnu/libsignal_jni.so
signal-cli listAccounts   # clean exit, no native error = fixed
```

## Registration

Signal requires a captcha, and **SMS must be requested before voice** (a voice-first
request is rejected). Google Voice receives the SMS fine — use `--voice` only as a
fallback if the SMS never arrives. Captcha tokens are single-use and the registration
window is short, so verify promptly.

```bash
export PATH="$HOME/.local/bin:$PATH"
ACC=+1XXXXXXXXXX          # the agent's Google Voice number, E.164

# 1. Captcha token: open https://signalcaptchas.org/registration/generate.html
#    solve it, right-click "Open Signal" -> Copy Link -> signalcaptcha://<TOKEN>
# 2. Request the SMS code (add --voice ONLY as a fallback if SMS never arrives):
signal-cli -a "$ACC" register --captcha "signalcaptcha://<TOKEN>"
# 3. Read the 6-digit code from Google Voice, then verify promptly:
signal-cli -a "$ACC" verify <CODE>
```

## Run the daemon (systemd service in the VM)

Runs as `/etc/systemd/system/signal-cli.service` (`Restart=always`, enabled at boot),
exposing JSON-RPC over HTTP on loopback:

```bash
signal-cli -a "$ACC" daemon --http 127.0.0.1:8080
```

The Hermes gateway is likewise a system service (`hermes-gateway`), so both come back
after a VM reboot.

## Hermes `~/.hermes/.env` — Signal block

```bash
SIGNAL_ACCOUNT=+1XXXXXXXXXX               # the agent's GV number
SIGNAL_HTTP_URL=http://127.0.0.1:8080
SIGNAL_ALLOWED_USERS=<your personal number>   # who may talk to it (you)
SIGNAL_ALLOW_ALL_USERS=false
SIGNAL_HOME_CHANNEL=<your personal number>    # proactive/cron delivery target
```

## Recommended agent config (clean, text-native replies)

Set in the VM's `~/.hermes/config.yaml` so replies read like a person texting, not a
chatbot dumping tool logs:

```yaml
model:
  default: anthropic/claude-sonnet-5   # cheap + capable for an always-on assistant
display:
  tool_progress: off                   # don't narrate tool calls
  interim_assistant_messages: false    # no "let me check…" filler messages
  busy_ack_detail: false
```

Plus `SIGNAL_REACTIONS=false` in `~/.hermes/.env` (no 👀 reactions on inbound
messages). The texting persona lives in `~/.hermes/SOUL.md` — a starting template is
in [`config/SOUL.md`](../config/SOUL.md).

## Status
- ✅ Tooling, registration, daemon, and gateway — **live**; the agent responds on Signal.
- ✅ Model `claude-sonnet-5`; web search on (keyless DuckDuckGo); clean text-only replies.
- ⬜ Next: integrations (calendar / email / tasks via MCP), proactivity, persistent memory.
