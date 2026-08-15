# Contacts integration — self-hosted, read-only

Google Contacts via the **same** `google_workspace_mcp` + OAuth client as Gmail and
Calendar. See the [Gmail recipe](../gmail/recipe.md) for the shared foundation; this
covers only the contacts-specific bits.

## Security posture
- **Scope:** `contacts.readonly` — read people, numbers, emails, birthdays. No writes.
- Registered as a separate `contacts` MCP server (`list_contacts`, `search_contacts`,
  `get_contact`, …), sharing the same token. Secrets stay in the VM.

## Setup (after the Google foundation in the Gmail recipe)
1. Enable the **Google People API** in the same project:
   `https://console.cloud.google.com/flows/enableapi?apiid=people.googleapis.com`
2. Re-auth with `contacts:readonly` added and approve "See your contacts".
3. Register + reload:
   ```bash
   echo Y | hermes mcp add contacts \
     --command "$HOME/.local/bin/workspace-mcp" \
     --env GOOGLE_CLIENT_SECRET_PATH=... WORKSPACE_MCP_CREDENTIALS_DIR=... USER_GOOGLE_EMAIL=you@gmail.com \
     --args --single-user --permissions contacts:readonly
   sudo systemctl restart hermes-gateway
   ```
4. Verify: `list_contacts` returns your contacts.
