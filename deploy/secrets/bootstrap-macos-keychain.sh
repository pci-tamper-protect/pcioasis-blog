#!/usr/bin/env bash
# Store Azure AI Foundry credentials in macOS Keychain from a local secret file.
#
# Default input: /tmp/ai  (JSON object or bare api_key string)
#
# Creates two generic-password entries:
#   - pcioasis-blog/azure-ai-foundry        → full JSON (for multi-field loaders)
#   - pcioasis-blog/azure-ai-foundry-api-key → api_key only (simple tools)
#
# Usage:
#   ./deploy/secrets/bootstrap-macos-keychain.sh
#   AI_SECRET_FILE=~/secrets/ai.json ./deploy/secrets/bootstrap-macos-keychain.sh
#
# Load into the current shell:
#   eval "$(./deploy/secrets/export-macos-keychain.sh)"

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

load_ai_secret "$AI_SECRET_FILE"

account="${AI_API_KEY_NAME:-default}"

add_or_update() {
  local service="$1"
  local password="$2"
  if security find-generic-password -s "$service" -a "$account" >/dev/null 2>&1; then
    security delete-generic-password -s "$service" -a "$account" >/dev/null
  fi
  security add-generic-password \
    -U \
    -s "$service" \
    -a "$account" \
    -w "$password" \
    -T /usr/bin/security \
    -T /usr/bin/python3 \
    >/dev/null
}

add_or_update "$KEYCHAIN_SERVICE_JSON" "$AI_JSON"
add_or_update "$KEYCHAIN_SERVICE_API_KEY" "$AI_API_KEY"

echo "Keychain updated:"
echo "  service (JSON):  $KEYCHAIN_SERVICE_JSON"
echo "  service (key):   $KEYCHAIN_SERVICE_API_KEY"
echo "  account:         $account"
echo ""
echo "Export for tools:"
if [[ "$account" == "default" ]]; then
  echo "  eval \"\$(./deploy/secrets/export-macos-keychain.sh)\""
else
  echo "  eval \"\$(KEYCHAIN_ACCOUNT=$account ./deploy/secrets/export-macos-keychain.sh)\""
  echo "  # or (auto-detects the only entry): eval \"\$(./deploy/secrets/export-macos-keychain.sh)\""
fi
