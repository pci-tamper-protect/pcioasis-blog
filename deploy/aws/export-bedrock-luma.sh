#!/usr/bin/env bash
# Export Bedrock Luma Ray 2 env vars for the video arena.
# Usage: eval "$(./deploy/aws/export-bedrock-luma.sh)"
#
# AWS credentials: aws configure, AWS_PROFILE, or standard AWS_* env vars (not in JSON).
# Config JSON: BEDROCK_LUMA_CONFIG_FILE (default /tmp/bedrock-luma.json)

set -euo pipefail

CONFIG_FILE="${BEDROCK_LUMA_CONFIG_FILE:-/tmp/bedrock-luma.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${BEDROCK_LUMA_CONFIG_GCP_SECRET:-}"

if [[ ! -f "$CONFIG_FILE" ]] && [[ -n "$GCP_SECRET" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "error: missing $CONFIG_FILE (copy deploy/aws/bedrock-luma-config.json.example)" >&2
  echo "  aws configure && enable Luma Ray 2 in us-west-2" >&2
  exit 1
fi

python3 - "$CONFIG_FILE" <<'PY'
import json, shlex, sys
data = json.load(open(sys.argv[1]))
exports = {
    "AWS_REGION": data.get("region", "us-west-2"),
    "VIDEO_ARENA_S3_OUTPUT_URI": data.get("s3_output_uri", ""),
}
if data.get("duration"):
    exports["BEDROCK_LUMA_DURATION"] = data["duration"]
if data.get("resolution"):
    exports["BEDROCK_LUMA_RESOLUTION"] = data["resolution"]
for k, v in exports.items():
    if v:
        print(f"export {k}={shlex.quote(str(v))}")
PY
