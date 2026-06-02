#!/usr/bin/env bash
# Print shell exports for AI credentials from macOS Keychain (stdout only).
# Usage: eval "$(./deploy/secrets/export-macos-keychain.sh)"
#
# Optional: KEYCHAIN_ACCOUNT=default  KEYCHAIN_SERVICE_JSON=...

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

read_keychain() {
  local service="$1"
  local password=""

  if [[ -n "${KEYCHAIN_ACCOUNT:-}" ]]; then
    password="$(security find-generic-password -s "$service" -a "$KEYCHAIN_ACCOUNT" -w 2>/dev/null)" \
      || print_missing_keychain_help
    echo "$password"
    return
  fi

  # Prefer account "default", then any single entry for this service (api_key_name from bootstrap).
  password="$(security find-generic-password -s "$service" -a "default" -w 2>/dev/null)" \
    && { echo "$password"; return; }
  password="$(security find-generic-password -s "$service" -w 2>/dev/null)" \
    && { echo "$password"; return; }

  print_missing_keychain_help
}

json="$(read_keychain "$KEYCHAIN_SERVICE_JSON")"
export AI_SECRET_JSON="$json"

python3 - "$json" <<'PY'
import json
import os
import shlex
import sys

raw = sys.argv[1]
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {"api_key": raw, "api_key_name": os.environ.get("KEYCHAIN_ACCOUNT", "default")}

api_key = data.get("api_key") or data.get("key") or raw
exports = {
    "AI_API_KEY": api_key,
    "AI_API_KEY_NAME": data.get("api_key_name") or os.environ.get("KEYCHAIN_ACCOUNT", "default"),
    "AI_PROJECT_ENDPOINT": data.get("project_endpoint", ""),
    "AI_AZURE_OPENAI_ENDPOINT": data.get("azure_openai_endpoint", ""),
    # Vendor-neutral aliases used by load_ai_config.py and OpenAI SDKs
    "OPENAI_API_KEY": api_key,
    "AZURE_OPENAI_API_KEY": api_key,
    "AZURE_OPENAI_ENDPOINT": data.get("azure_openai_endpoint", ""),
    "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT": data.get("project_endpoint", ""),
}
# Do not set ANTHROPIC_API_KEY from Azure/Foundry keys — that breaks generate_variants.
for key, value in exports.items():
    if value:
        print(f"export {key}={shlex.quote(str(value))}")
PY
