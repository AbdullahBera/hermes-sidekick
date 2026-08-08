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

## Registration (pending — needs the GV number, a captcha, and the voice code)

Signal requires a captcha for registration. Google Voice needs **voice** verification
(SMS often isn't delivered to GV).

```bash
export PATH="$HOME/.local/bin:$PATH"
ACC=+1XXXXXXXXXX          # the agent's Google Voice number, E.164

# 1. Get a captcha token: open in a browser
#    https://signalcaptchas.org/registration/generate.html
#    solve it, then copy the "Open Signal" link — it's signalcaptcha://<TOKEN>
# 2. Register with voice verification:
signal-cli -a "$ACC" register --voice --captcha "signalcaptcha://<TOKEN>"
# 3. Signal calls the GV number and reads a 6-digit code:
signal-cli -a "$ACC" verify <CODE>
```

## Run the daemon (after registration)

```bash
signal-cli -a "$ACC" daemon --http 127.0.0.1:8080
# (will be daemonized as a background service so it survives reboots)
```

## Hermes `~/.hermes/.env` — Signal block

```bash
SIGNAL_ACCOUNT=+1XXXXXXXXXX               # the agent's GV number
SIGNAL_HTTP_URL=http://127.0.0.1:8080
SIGNAL_ALLOWED_USERS=<your personal number>   # who may talk to it (you)
SIGNAL_ALLOW_ALL_USERS=false
SIGNAL_HOME_CHANNEL=<your personal number>    # proactive/cron delivery target
```

## Status
- ✅ Tooling installed and native lib verified.
- ⬜ Registration (blocked on captcha + voice code — interactive).
- ⬜ Daemon service + `.env` wiring + `hermes gateway` round-trip test.
