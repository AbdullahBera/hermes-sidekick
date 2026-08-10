# Gmail integration — self-hosted, private

The agent reads and drafts Gmail through
[`google_workspace_mcp`](https://github.com/taylorwilsdon/google_workspace_mcp),
running **inside the VM** with **your own Google OAuth client**. Nothing is brokered
by a third party — the server talks directly to Google's APIs. Secrets never leave
the VM. (Composio and other managed brokers were evaluated and rejected for privacy.)

## Security posture
- **Scope:** read + labels + drafts (`gmail.readonly`, `gmail.labels`, `gmail.compose`).
  `gmail.modify` was intentionally **not** granted, so it can't archive/trash.
- **No send, ever:** no send tool is exposed and the granted scope can't send mail.
- **Ask-first hard rule:** the agent may read/search/summarize freely, but must ask
  and get an explicit "yes" before any action that writes/changes the mailbox
  (draft, labels). Enforced in `~/.hermes/SOUL.md` (template: [`config/SOUL.md`](../config/SOUL.md)).
- **Secrets are VM-only:** the OAuth client JSON and the user token live in
  `~/.hermes/google-workspace/` (chmod 600). This repo references only paths.

## One-time setup

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

## Adding Calendar later
Same OAuth client — just enable the **Google Calendar API** in the same project and
re-auth with calendar scopes. No new client needed.
