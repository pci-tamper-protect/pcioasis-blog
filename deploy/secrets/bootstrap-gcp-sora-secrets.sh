#!/usr/bin/env bash
# Upload Sora-only Foundry credentials to GCP Secret Manager.
#
# Default input:  /tmp/sora.json
# Secret id:      azure_ai_foundry_sora2  (override with GCP_SORA_SECRET_ID)
#
# Usage:
#   ./deploy/secrets/bootstrap-gcp-sora-secrets.sh
#   AZURE_SORA_SECRET_FILE=~/sora.json ./deploy/secrets/bootstrap-gcp-sora-secrets.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export AI_SECRET_FILE="${AZURE_SORA_SECRET_FILE:-/tmp/sora.json}"
export GCP_SECRET_ID="${GCP_SORA_SECRET_ID:-azure_ai_foundry_sora2}"

exec "$SCRIPT_DIR/bootstrap-gcp-secrets.sh"
