#!/usr/bin/env bash
# Upload Vertex Veo config to GCP Secret Manager (project: pcioasis-blog).
#
# Default input:  deploy/vertex/veo-config.json  (no API keys — project/region/model)
# Secret id:      vertex_veo_config  (override with VERTEX_CONFIG_GCP_SECRET)
#
# Usage:
#   ./deploy/vertex/bootstrap-gcp-veo-config.sh
#   VERTEX_CONFIG_FILE=/path/to/veo.json ./deploy/vertex/bootstrap-gcp-veo-config.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../secrets/lib/common.sh
source "$SCRIPT_DIR/../secrets/lib/common.sh"

CONFIG_FILE="${VERTEX_CONFIG_FILE:-$SCRIPT_DIR/veo-config.json}"
GCP_SECRET_ID="${VERTEX_CONFIG_GCP_SECRET:-vertex_veo_config}"

need_cmd gcloud
[[ -f "$CONFIG_FILE" ]] || die "missing config file: $CONFIG_FILE"

python3 - "$CONFIG_FILE" <<'PY' || die "invalid JSON in $CONFIG_FILE"
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
project = (data.get("project_id") or "").strip()
if not project or project in ("REPLACE_ME", "YOUR_PROJECT_ID"):
    raise SystemExit(f'set "project_id" in {path}')
PY

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
cp "$CONFIG_FILE" "$tmp"

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
echo "Fetch locally (CI / agents without repo checkout):"
echo "  gcloud secrets versions access latest --secret=$GCP_SECRET_ID --project=$GCP_PROJECT > /tmp/veo.json"
echo "  export VERTEX_CONFIG_FILE=/tmp/veo.json"
echo "  eval \"\$(./deploy/vertex/export-veo.sh)\""
echo ""
echo "Or rely on export-veo.sh auto-fetch when \$VERTEX_CONFIG_FILE is missing and only GCP has the config."
