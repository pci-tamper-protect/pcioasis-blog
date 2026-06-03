#!/usr/bin/env bash
# Export AZURE_SORA_* for video arena (separate from chat /tmp/ai creds).
# Usage: eval "$(./deploy/secrets/export-sora.sh)"
#
# Reads (in order):
#   AZURE_SORA_SECRET_FILE, /tmp/sora.json, or GCP secret azure_ai_foundry_sora2

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SORA_FILE="${AZURE_SORA_SECRET_FILE:-/tmp/sora.json}"
GCP_PROJECT="${GCP_PROJECT:-pcioasis-blog}"
GCP_SORA_SECRET="${GCP_SORA_SECRET_ID:-azure_ai_foundry_sora2}"

if [[ ! -f "$SORA_FILE" ]] && command -v gcloud >/dev/null 2>&1; then
  if gcloud secrets describe "$GCP_SORA_SECRET" --project="$GCP_PROJECT" >/dev/null 2>&1; then
    gcloud secrets versions access latest \
      --secret="$GCP_SORA_SECRET" \
      --project="$GCP_PROJECT" >"$SORA_FILE"
  fi
fi

if [[ ! -f "$SORA_FILE" ]]; then
  echo "error: Sora: no secret at $SORA_FILE (create from azure-ai-foundry-sora2.json.example)" >&2
  echo "  gcloud secrets versions access latest --secret=$GCP_SORA_SECRET --project=$GCP_PROJECT > $SORA_FILE" >&2
  exit 1
fi

EXPORTS="$(uv run --project "$REPO_ROOT/agents/content-pipeline" \
  python "$REPO_ROOT/deploy/secrets/load_ai_config.py" \
  --sora --file "$SORA_FILE" --export-shell)" || {
  echo "error: Sora: failed to load $SORA_FILE (invalid JSON or missing api_key)" >&2
  exit 1
}

if [[ -z "$EXPORTS" ]]; then
  echo "error: Sora: no exports from $SORA_FILE" >&2
  exit 1
fi

printf '%s\n' "$EXPORTS"
echo "ok: Azure Sora loaded from $SORA_FILE" >&2
