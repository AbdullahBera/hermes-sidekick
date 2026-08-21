# Gmail integration — self-hosted, private

The agent reads, drafts, and label-sorts Gmail through
[`google_workspace_mcp`](https://github.com/taylorwilsdon/google_workspace_mcp),
running **inside the VM** with **your own Google OAuth client**. Nothing is brokered
by a third party — the server talks directly to Google's APIs. Secrets never leave
the VM. (Composio and other managed brokers were evaluated and rejected for privacy.)

> **Existing installs:** to enable label-sorting you must re-auth to add the
> `gmail.modify` scope (see [Enabling label-sorting](#enabling-label-sorting-gmailmodify)).

## Security posture
- **Scope:** read + drafts + labels + modify (`gmail.readonly`, `gmail.compose`,
  `gmail.labels`, `gmail.modify`). `gmail.modify` is what lets it **add your labels to
  messages** — message-labeling goes through `messages.modify`; `gmail.labels` alone only
  edits label *definitions*. The full-mailbox scope (`https://mail.google.com/`) is **not**
  granted, so it can never *permanently* delete — worst case is recoverable Trash, and that
  is ask-first.
- **No send, ever:** no send tool is exposed. Note the honest caveat: the `gmail.compose`
  *scope* can technically send — the guarantee is **tool non-exposure + the ask-first rule,
  not the scope**. There is no code path from the agent to a sent email.
- **Ask-first hard rule (policy, not scope):** because `gmail.modify` also permits archive/
  trash/mark-read, the protection is behavioral. Unprompted, the agent may only ADD your own
  triage labels to messages (mail stays in the inbox) and write DRAFTS (shown to you, never
  sent). Archive, trash, mark read/spam, unsubscribe — all require an explicit "yes".
  Enforced in `~/.hermes/SOUL.md` (template: [`config/SOUL.md`](../../../config/SOUL.md)).
  The accepted residual risk (incl. prompt-injection from a hostile email) is documented in
  [`docs/DECISIONS.md`](../../../docs/DECISIONS.md).
- **Secrets are VM-only:** the OAuth client JSON and the user token live in
  `~/.hermes/google-workspace/` (chmod 600). This repo references only paths.

## One-time setup

> **Shortcut:** [`scripts/setup-google.sh`](../../../scripts/setup-google.sh) automates the
> project + API enablement (via `gcloud`) and deep-links the console steps below, then stages
> `client_secret.json` into the VM. The steps here are the manual equivalent / reference.

### 1. Google Cloud (browser, ~10 min)
- New project → enable the **Gmail API**.
- **OAuth consent screen** → External; add yourself as a user; **Publish app → In
  production**. Production is what makes the refresh token *persist* — in "Testing"
  Google expires it every 7 days. Unverified is fine for personal use (you click past
  one "unverified app" screen at first auth).
- **Credentials → OAuth client ID → Desktop app** → Download the `client_secret_*.json`.

### 2. Install the server (in the VM)
```bash
uv tool install workspace-mcp     # provides `workspace-mcp` + `workspace-cli`
```
Pure Python — no native-lib workaround needed (unlike signal-cli on arm64).

### 3. One-time OAuth (mint the token)
Stage the client JSON in the VM, then run the server in HTTP mode and authorize:
```bash
export GOOGLE_CLIENT_SECRET_PATH=~/.hermes/google-workspace/client_secret.json
export WORKSPACE_MCP_CREDENTIALS_DIR=~/.hermes/google-workspace/.credentials
export USER_GOOGLE_EMAIL=you@gmail.com
export WORKSPACE_MCP_PORT=8000 OAUTHLIB_INSECURE_TRANSPORT=1

workspace-mcp --single-user --permissions gmail:drafts --transport streamable-http &
workspace-cli --url http://localhost:8000/mcp call start_google_auth \
  user_google_email=you@gmail.com service_name=gmail
```
Open the printed consent URL in your browser and approve. OrbStack auto-forwards the
VM's `:8000` to the Mac's `localhost:8000`, so the loopback OAuth callback just works
— no tunnel needed. The token saves to `.credentials/`. Stop the HTTP server after.

### 4. Register with Hermes (stdio) + reload
```bash
echo Y | hermes mcp add gmail \
  --command "$HOME/.local/bin/workspace-mcp" \
  --env GOOGLE_CLIENT_SECRET_PATH=... WORKSPACE_MCP_CREDENTIALS_DIR=... USER_GOOGLE_EMAIL=you@gmail.com \
  --args --single-user --permissions gmail:drafts
sudo systemctl restart hermes-gateway
```
`echo Y` answers the interactive "Enable all tools?" prompt. Restart so the gateway
loads the server.

## Config (documented in `.env.example`; real values stay in the VM)
| Var | Meaning |
|---|---|
| `GOOGLE_CLIENT_SECRET_PATH` | Path to the client JSON (**not** the secret itself) |
| `WORKSPACE_MCP_CREDENTIALS_DIR` | Where the user token is stored |
| `USER_GOOGLE_EMAIL` | Single-user identity |

## Enabling label-sorting (gmail.modify)

Adding a label to a *message* requires the `gmail.modify` scope — the **`organize`**
permission level. It's cumulative under `gmail:drafts`, so a token minted with an older
scope set (read + compose + labels only) just needs a **re-auth** to re-mint with current
scopes:

```bash
export GOOGLE_CLIENT_SECRET_PATH=~/.hermes/google-workspace/client_secret.json
export WORKSPACE_MCP_CREDENTIALS_DIR=~/.hermes/google-workspace/.credentials
export USER_GOOGLE_EMAIL=you@gmail.com
export WORKSPACE_MCP_PORT=8000 OAUTHLIB_INSECURE_TRANSPORT=1

workspace-mcp --single-user --permissions gmail:drafts --transport streamable-http &
workspace-cli --url http://localhost:8000/mcp call start_google_auth \
  user_google_email=you@gmail.com service_name=gmail
```

Approve the consent screen (it now asks for the "organize"/modify permission), stop the HTTP
server, and restart the gateway:

```bash
sudo systemctl restart hermes-gateway
```

Verify the token carries modify — prints only scope names, never the token:
```bash
python3 -c "import json,os,glob; f=glob.glob(os.path.expanduser('~/.hermes/google-workspace/.credentials/*@*.json'))[0]; print(json.load(open(f)).get('scopes'))"
```
You should see `.../auth/gmail.modify`. Levels are cumulative (`readonly < organize < drafts
< send < full`); we deliberately stop at `drafts` — read + organize + compose — and never
request `send` or `full`.

## Adding Calendar later
Same OAuth client — just enable the **Google Calendar API** in the same project and
re-auth with calendar scopes. No new client needed.
