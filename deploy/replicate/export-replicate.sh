#!/usr/bin/env bash
# Export REPLICATE_API_TOKEN for the video arena.
# Usage: eval "$(./deploy/replicate/export-replicate.sh)"
#
# Reads: REPLICATE_CONFIG_FILE (default /tmp/replicate.json)

set -euo pipefail

CONFIG_FILE="${REPLICATE_CONFIG_FILE:-/tmp/replicate.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SECRET="${REPLICATE_CONFIG_GCP_SECRET:-replicate-api-token}"

if [[ ! -f "$CONFIG_FILE" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SECRET" \
      --project="$GCP_PROJECT" >"$CONFIG_FILE"
  fi
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "error: missing $CONFIG_FILE (copy deploy/replicate/replicate-config.json.example)" >&2
  echo "  https://replicate.com/account/api-tokens" >&2
  exit 1
fi

python3 - "$CONFIG_FILE" <<'PY'
import json, shlex, sys
data = json.load(open(sys.argv[1]))
token = data.get("api_token") or data.get("REPLICATE_API_TOKEN") or data.get("api_key")
if not token:
    raise SystemExit('error: replicate json needs "api_token"')
print(f"export REPLICATE_API_TOKEN={shlex.quote(str(token))}")
PY
