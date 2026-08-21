#!/usr/bin/env bash
# setup-google.sh — shrink the Google OAuth wall for the Gmail/Calendar/Contacts connectors.
#
# Creating a *personal* OAuth Desktop client still requires a few clicks in Google's console
# (there's no gcloud command for it — see docs/DECISIONS.md). This script automates everything
# that CAN be scripted (project + API enablement via gcloud) and gives you exact, deep-linked
# steps + a JSON hand-off for the parts that can't. Your client + token stay in your VM; no
# third-party broker (that's the whole point — this is the friction floor of "own your OAuth").
#
#   ./scripts/setup-google.sh          # guided; automates what it can, prompts for the rest
set -euo pipefail

VM="${HERMES_VM:-hermes}"
PROJECT_ID="${GOOGLE_PROJECT_ID:-hermes-assistant-$RANDOM}"
say()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
pause(){ printf '\n%s\n> press Enter when done… ' "$1"; read -r _; }

say "0/5  Google Cloud SDK"
if ! command -v gcloud >/dev/null; then
  cat <<EOF
gcloud isn't installed. Either install it (recommended — it automates the project setup):
  macOS:  brew install --cask google-cloud-sdk
…or do the two automated steps below manually in the console and re-run to continue.
EOF
  pause "Install gcloud (or choose to do project+APIs by hand), then continue."
fi

if command -v gcloud >/dev/null; then
  say "1/5  Sign in + create project (scriptable)"
  gcloud auth login
  gcloud projects create "$PROJECT_ID" --name="Hermes Assistant" 2>/dev/null \
    && echo "created project: $PROJECT_ID" \
    || { echo "project create failed/exists — pick your own:"; read -rp "PROJECT_ID: " PROJECT_ID; }
  gcloud config set project "$PROJECT_ID"

  say "2/5  Enable the APIs (scriptable)"
  gcloud services enable gmail.googleapis.com calendar-json.googleapis.com people.googleapis.com
  echo "enabled: Gmail, Calendar, People"
else
  say "1-2/5  Do these in the console (no gcloud):"
  echo "  • Create a project, then enable the Gmail, Calendar, and People APIs."
  read -rp "Your PROJECT_ID: " PROJECT_ID
fi

say "3/5  OAuth consent screen  (must be a browser — this is the irreducible part)"
cat <<EOF
Open:  https://console.cloud.google.com/apis/credentials/consent?project=$PROJECT_ID
  1. User type: External →  Create
  2. App name: "Hermes"  ·  your email for support + developer contact
  3. Publish status: click **Publish app → Confirm** (production) so the refresh token PERSISTS
     (in "Testing" Google expires it every 7 days). Unverified is fine for personal use.
EOF
pause "Consent screen configured + app PUBLISHED?"

say "4/5  Create the OAuth client + download JSON"
cat <<EOF
Open:  https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID
  1. Create Credentials → OAuth client ID
  2. Application type: **Desktop app**  ·  name it "Hermes"  →  Create
  3. Download the client_secret_*.json
EOF
read -rp "Path to the downloaded client_secret JSON: " CS
CS="${CS/#\~/$HOME}"
[ -f "$CS" ] || { echo "not found: $CS" >&2; exit 1; }

say "5/5  Stage the client into the VM (secrets stay in the VM, chmod 600)"
cat "$CS" | orb run -m "$VM" bash -lc '
  mkdir -p ~/.hermes/google-workspace/.credentials
  cat > ~/.hermes/google-workspace/client_secret.json
  chmod 600 ~/.hermes/google-workspace/client_secret.json
  echo "staged client_secret.json"'

cat <<EOF

Client is in the VM. Next — mint the token (browser approve, one time), then register the
connectors. See plugins/connectors/gmail/recipe.md ("One-time OAuth" + "Register with Hermes").
The onboarder runs those steps for you; to do it by hand, follow the recipe.
EOF
