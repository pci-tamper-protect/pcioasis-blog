# shellcheck shell=bash
# Shared helpers for deploy/secrets bootstrap scripts.
# Source from bootstrap-*.sh; do not execute directly.

set -euo pipefail

: "${AI_SECRET_FILE:=/tmp/ai}"
: "${GCP_PROJECT:=pcioasis-blog}"
: "${GCP_SECRET_ID:=azure-ai-foundry}"
: "${KEYCHAIN_SERVICE_JSON:=pcioasis-blog/azure-ai-foundry}"
: "${KEYCHAIN_SERVICE_API_KEY:=pcioasis-blog/azure-ai-foundry-api-key}"

# shellcheck source=env_help.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env_help.sh"

die() {
  echo "error: $*" >&2
  exit 1
}

need_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    return 0
  fi
  case "$1" in
    gcloud) print_missing_gcloud_help ;;
    python3) die "missing required command: python3 (install Python 3.11+)" ;;
    *) die "missing required command: $1" ;;
  esac
}

# Parse AI secret file into shell-exportable variables.
# Sets: AI_PROJECT_ENDPOINT, AI_AZURE_OPENAI_ENDPOINT, AI_API_KEY, AI_API_KEY_NAME, AI_JSON
load_ai_secret() {
  local file="${1:-$AI_SECRET_FILE}"
  [[ -f "$file" ]] || print_missing_secret_file_help "$file"

  need_cmd python3
  local parsed
  parsed="$(python3 - "$file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_text(encoding="utf-8").strip()
if not raw:
    raise SystemExit("secret file is empty")

data = json.loads(raw)
if isinstance(data, str):
    # Bare API key string only.
    data = {"api_key": data, "api_key_name": "default"}

if not isinstance(data, dict):
    raise SystemExit("secret must be a JSON object or a bare API key string")

api_key = data.get("api_key") or data.get("key")
if not api_key:
    raise SystemExit('secret JSON must include "api_key"')

def esc(value: str) -> str:
    return value.replace("'", "'\"'\"'")

out = {
    "AI_PROJECT_ENDPOINT": data.get("project_endpoint", ""),
    "AI_AZURE_OPENAI_ENDPOINT": data.get("azure_openai_endpoint", ""),
    "AI_API_KEY": api_key,
    "AI_API_KEY_NAME": data.get("api_key_name") or "default",
    "AI_JSON": json.dumps(
        {
            "project_endpoint": data.get("project_endpoint", ""),
            "azure_openai_endpoint": data.get("azure_openai_endpoint", ""),
            "api_key": api_key,
            "api_key_name": data.get("api_key_name") or "default",
        },
        separators=(",", ":"),
    ),
}
for key, value in out.items():
    print(f"{key}='{esc(str(value))}'")
PY
)" || die "failed to parse $file (expected JSON object or bare api key string)"

  # shellcheck disable=SC1090
  eval "$parsed"
  [[ -n "${AI_API_KEY:-}" ]] || die "api_key is empty after parse"
}
