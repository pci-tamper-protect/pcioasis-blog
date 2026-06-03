#!/usr/bin/env bash
# Check which video arena providers are configured in the current shell.
# Usage:
#   eval "$(./deploy/secrets/export-sora.sh)"   # optional, load first
#   ./deploy/scripts/verify-video-credentials.sh
#   ./deploy/scripts/verify-video-credentials.sh azure_sora

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ONLY="${1:-}"

check() {
  local id="$1"
  local ok="$2"
  local detail="$3"
  if [[ -n "$ONLY" && "$ONLY" != "$id" ]]; then
    return 0
  fi
  if [[ "$ok" == "yes" ]]; then
    printf "  ✓ %-18s %s\n" "$id" "$detail"
  elif [[ "$ok" == "partial" ]]; then
    printf "  ~ %-18s %s\n" "$id" "$detail"
  else
    printf "  ✗ %-18s %s\n" "$id" "$detail"
  fi
}

echo "Video arena credential check (current shell env):"
echo ""

# Azure Sora
if [[ -n "${AZURE_SORA_ENDPOINT:-}" && -n "${AZURE_SORA_API_KEY:-}" ]]; then
  check azure_sora yes "AZURE_SORA_ENDPOINT + key set (deployment=${AZURE_SORA_DEPLOYMENT:-sora-2})"
elif [[ -n "${AZURE_OPENAI_ENDPOINT:-}" && -n "${AZURE_OPENAI_API_KEY:-}${AI_API_KEY:-}" ]]; then
  check azure_sora yes "fallback AZURE_OPENAI_* (prefer export-sora.sh for video-only resource)"
else
  check azure_sora no "run: eval \"\$(./deploy/secrets/export-sora.sh)\""
fi

# Azure Sora v1 — same endpoint as Sora 2
if [[ -n "${AZURE_SORA_ENDPOINT:-}${AZURE_OPENAI_ENDPOINT:-}" ]]; then
  check azure_sora_v1 yes "shares Sora endpoint (AZURE_SORA_V1_DEPLOYMENT=${AZURE_SORA_V1_DEPLOYMENT:-sora})"
else
  check azure_sora_v1 no "needs Azure video endpoint first"
fi

# Vertex Veo
if [[ -n "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  if command -v gcloud >/dev/null 2>&1 && gcloud auth application-default print-access-token >/dev/null 2>&1; then
    check vertex_veo yes "project=${GOOGLE_CLOUD_PROJECT} location=${GOOGLE_CLOUD_LOCATION:-us-central1} ADC ok"
  else
    check vertex_veo partial "project set; run: gcloud auth application-default login"
  fi
else
  check vertex_veo no "run: eval \"\$(./deploy/vertex/export-veo.sh)\""
fi

# Bedrock Luma
if [[ -n "${VIDEO_ARENA_S3_OUTPUT_URI:-}" ]]; then
  if command -v aws >/dev/null 2>&1 && aws sts get-caller-identity >/dev/null 2>&1; then
    check bedrock_luma yes "S3=${VIDEO_ARENA_S3_OUTPUT_URI} region=${AWS_REGION:-us-west-2}"
  else
    check bedrock_luma partial "S3 URI set; aws CLI not authenticated"
  fi
else
  check bedrock_luma no "run: eval \"\$(./deploy/aws/export-bedrock-luma.sh)\""
fi

# Replicate
if [[ -n "${REPLICATE_API_TOKEN:-}" ]]; then
  check replicate_hailuo yes "REPLICATE_API_TOKEN set"
else
  check replicate_hailuo no "run: eval \"\$(./deploy/replicate/export-replicate.sh)\""
fi

echo ""
echo "Hub: deploy/VIDEO_GENERATORS.md"
