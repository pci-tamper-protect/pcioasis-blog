#!/usr/bin/env bash
# Export Vertex Veo env vars for the video arena.
# Usage: eval "$(./deploy/vertex/export-veo.sh)"
#
# Reads: VERTEX_CONFIG_FILE (default /tmp/veo.json)
# Optional fetch: VERTEX_CONFIG_GCP_SECRET + GCP_PROJECT

set -euo pipefail

CONFIG_FILE="${VERTEX_CONFIG_FILE:-/tmp/veo.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${VERTEX_CONFIG_GCP_SECRET:-}"

if [[ ! -f "$CONFIG_FILE" ]] && [[ -n "$GCP_SECRET" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "error: missing $CONFIG_FILE (copy deploy/vertex/veo-config.json.example)" >&2
  echo "  gcloud auth application-default login" >&2
  exit 1
fi

python3 - "$CONFIG_FILE" <<'PY'
import json, shlex, sys
data = json.load(open(sys.argv[1]))
exports = {
    "GOOGLE_CLOUD_PROJECT": data.get("project_id", ""),
    "GOOGLE_CLOUD_LOCATION": data.get("location", "us-central1"),
    "VERTEX_VEO_MODEL": data.get("model", "veo-3.1-fast-generate-001"),
}
if data.get("seconds"):
    exports["VERTEX_VEO_SECONDS"] = str(data["seconds"])
for k, v in exports.items():
    if v:
        print(f"export {k}={shlex.quote(str(v))}")
PY
