#!/usr/bin/env bash
# Export REPLICATE_API_TOKEN for the video arena.
# Usage: eval "$(./deploy/replicate/export-replicate.sh)"
#
# Status messages go to stderr; export statements go to stdout (for eval).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../scripts/export-common.sh
source "$SCRIPT_DIR/../scripts/export-common.sh"

CONFIG_FILE="${REPLICATE_CONFIG_FILE:-/tmp/replicate.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${REPLICATE_CONFIG_GCP_SECRET:-replicate-api-token}"
SOURCE="$CONFIG_FILE"

if [[ ! -f "$CONFIG_FILE" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
    SOURCE="gcp secret $GCP_SECRET"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  export_report_err "Replicate: missing $CONFIG_FILE"
  echo "  cp deploy/replicate/replicate-config.json.example $CONFIG_FILE" >&2
  echo "  https://replicate.com/account/api-tokens" >&2
  exit 1
fi

EXPORTS="$(python3 - "$CONFIG_FILE" <<'PY' || exit 1
import json, shlex, sys

path = sys.argv[1]
try:
    data = json.load(open(path))
except json.JSONDecodeError as exc:
    print(f"Replicate: invalid JSON in {path}: {exc}", file=sys.stderr)
    sys.exit(1)

token = (data.get("api_token") or data.get("REPLICATE_API_TOKEN") or data.get("api_key") or "").strip()
if not token or token in ("r8_REPLACE_ME", "REPLACE_ME"):
    print(f'Replicate: set "api_token" in {path}', file=sys.stderr)
    sys.exit(1)

print(f"export REPLICATE_API_TOKEN={shlex.quote(token)}")
PY
)"

export_emit_or_fail "Replicate Hailuo" "$SOURCE" "$EXPORTS" || exit 1
