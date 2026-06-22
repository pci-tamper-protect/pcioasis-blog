#!/usr/bin/env bash
# Export Bedrock Luma Ray 2 env vars for the video arena.
# Usage: eval "$(./deploy/aws/export-bedrock-luma.sh)"
#
# Status messages go to stderr; export statements go to stdout (for eval).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/export-common.sh
source "$SCRIPT_DIR/../scripts/export-common.sh"

CONFIG_FILE="${BEDROCK_LUMA_CONFIG_FILE:-/tmp/bedrock-luma.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${BEDROCK_LUMA_CONFIG_GCP_SECRET:-}"
SOURCE="$CONFIG_FILE"

if [[ ! -f "$CONFIG_FILE" ]] && [[ -n "$GCP_SECRET" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
    SOURCE="gcp secret $GCP_SECRET"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  export_report_err "Bedrock Luma: missing $CONFIG_FILE"
  echo "  cp deploy/aws/bedrock-luma-config.json.example $CONFIG_FILE" >&2
  echo "  aws configure && enable Luma Ray 2 in us-west-2" >&2
  exit 1
fi

EXPORTS="$(python3 - "$CONFIG_FILE" <<'PY' || exit 1
import json, shlex, sys

path = sys.argv[1]
try:
    data = json.load(open(path))
except json.JSONDecodeError as exc:
    print(f"Bedrock Luma: invalid JSON in {path}: {exc}", file=sys.stderr)
    sys.exit(1)

s3_uri = (data.get("s3_output_uri") or "").strip()
if not s3_uri or "your-bucket" in s3_uri:
    print(f'Bedrock Luma: set "s3_output_uri" in {path}', file=sys.stderr)
    sys.exit(1)

exports = {
    "AWS_REGION": (data.get("region") or "us-west-2").strip(),
    "VIDEO_ARENA_S3_OUTPUT_URI": s3_uri,
}
if data.get("duration"):
    exports["BEDROCK_LUMA_DURATION"] = str(data["duration"])
if data.get("resolution"):
    exports["BEDROCK_LUMA_RESOLUTION"] = str(data["resolution"])

lines = [f"export {k}={shlex.quote(v)}" for k, v in exports.items() if v]
print("\n".join(lines))
PY
)"

export_emit_or_fail "Bedrock Luma" "$SOURCE" "$EXPORTS" || exit 1

if command -v aws >/dev/null 2>&1; then
  if aws sts get-caller-identity >/dev/null 2>&1; then
    export_report_ok "AWS credentials active ($(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo unknown account))"
  else
    echo "warning: Bedrock Luma: S3 URI set but AWS CLI not authenticated — run: aws configure" >&2
  fi
else
  echo "warning: Bedrock Luma: aws CLI not installed" >&2
fi
