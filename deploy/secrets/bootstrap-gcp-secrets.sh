#!/usr/bin/env bash
# Upload Azure AI Foundry credentials to GCP Secret Manager (project: pcioasis-blog).
#
# Default input: /tmp/ai
# Secret id:     azure-ai-foundry  (override with GCP_SECRET_ID)
#
# Usage:
#   ./deploy/secrets/bootstrap-gcp-secrets.sh
#   AI_SECRET_FILE=~/secrets/ai.json GCP_SECRET_ID=my-secret ./deploy/secrets/bootstrap-gcp-secrets.sh
#
# Requires: gcloud CLI authenticated with secretmanager.admin (or secrets access)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

need_cmd gcloud
load_ai_secret "$AI_SECRET_FILE"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
printf '%s' "$AI_JSON" >"$tmp"

if gcloud secrets describe "$GCP_SECRET_ID" --project="$GCP_PROJECT" >/dev/null 2>&1; then
  gcloud secrets versions add "$GCP_SECRET_ID" \
    --project="$GCP_PROJECT" \
    --data-file="$tmp" \
    >/dev/null
  action="new version added"
else
  gcloud secrets create "$GCP_SECRET_ID" \
    --project="$GCP_PROJECT" \
    --replication-policy="automatic" \
    --data-file="$tmp" \
    >/dev/null
  action="secret created"
fi

echo "GCP Secret Manager ($action):"
echo "  project:  $GCP_PROJECT"
echo "  secret:   $GCP_SECRET_ID"
echo ""
echo "Grant runtime access (example — Cloud Build / GitHub Actions SA):"
echo "  gcloud secrets add-iam-policy-binding $GCP_SECRET_ID \\"
echo "    --project=$GCP_PROJECT \\"
echo "    --member=serviceAccount:YOUR_SA@$GCP_PROJECT.iam.gserviceaccount.com \\"
echo "    --role=roles/secretmanager.secretAccessor"
echo ""
echo "Fetch locally:"
echo "  gcloud secrets versions access latest --secret=$GCP_SECRET_ID --project=$GCP_PROJECT"
