# Calendar integration — self-hosted, read + write

Google Calendar is served by the **same** `google_workspace_mcp` setup as Gmail —
same VM, same OAuth client, same token. See [the Gmail recipe](../gmail/recipe.md) for the shared
OAuth/install foundation; this doc covers only the calendar-specific bits.

## Security posture
- **Scope:** `calendar.readonly` — read events, list calendars, check free/busy. No create/edit/delete.
- **No write:** read-only scope + no write tools exposed. Adding create/edit later is a
  deliberate scope bump, and is already covered by the ask-first hard rule in
  [`config/SOUL.md`](../../../config/SOUL.md).
- Registered as a separate Hermes MCP server `calendar` (tools: `list_calendars`,
  `get_events`, `query_freebusy`), sharing the same token as `gmail`.

## Setup (after the Google foundation in the Gmail recipe)

### 1. Enable the Calendar API (browser)
Same GCP project → enable **Google Calendar API**:
`https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com`

### 2. Re-auth to add the calendar scope
Run the auth server with gmail + calendar permissions and re-approve. This adds
`calendar.readonly` to the existing token; Gmail access is preserved.
```bash
export GOOGLE_CLIENT_SECRET_PATH=~/.hermes/google-workspace/client_secret.json
export WORKSPACE_MCP_CREDENTIALS_DIR=~/.hermes/google-workspace/.credentials
export USER_GOOGLE_EMAIL=you@gmail.com
export WORKSPACE_MCP_PORT=8000 OAUTHLIB_INSECURE_TRANSPORT=1

workspace-mcp --single-user --permissions gmail:drafts calendar:full --transport streamable-http &
workspace-cli --url http://localhost:8000/mcp call start_google_auth \
  user_google_email=you@gmail.com service_name=calendar
# open the consent URL, approve "See your calendars"; token updates. Stop the server after.
```
Note: calendar levels are `readonly` or `full` (not `read`).

### 3. Register with Hermes + reload
```bash
echo Y | hermes mcp add calendar \
  --command "$HOME/.local/bin/workspace-mcp" \
  --env GOOGLE_CLIENT_SECRET_PATH=... WORKSPACE_MCP_CREDENTIALS_DIR=... USER_GOOGLE_EMAIL=you@gmail.com \
  --args --single-user --permissions calendar:full
sudo systemctl restart hermes-gateway
```

## Adding create/edit later
Bump to `calendar:full` and re-auth (adds the calendar write scope). The ask-first
rule already requires confirmation before any event change.
