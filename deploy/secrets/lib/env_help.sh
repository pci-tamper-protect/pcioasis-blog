# shellcheck shell=bash
# Print copy-paste commands when secrets / tools are missing.
# Source from deploy/secrets/*.sh after common.sh.

_secrets_repo_root() {
  local lib_dir
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "$lib_dir/../../.." && pwd)
}

print_llm_env_commands() {
  local repo_root
  repo_root="$(_secrets_repo_root)"
  cat <<EOF
Commands to set credentials (run from repo root):

  cd ${repo_root}

  # Bootstrap Keychain once (requires JSON at \${AI_SECRET_FILE:-/tmp/ai}):
  ./deploy/secrets/bootstrap-macos-keychain.sh

  # Azure AI Foundry (typical):
  eval "\$(./deploy/secrets/export-macos-keychain.sh)"
  export AZURE_OPENAI_DEPLOYMENT="\${AZURE_OPENAI_DEPLOYMENT:-YOUR_DEPLOYMENT_NAME}"
  export CONTENT_PIPELINE_LLM_BACKEND="\${CONTENT_PIPELINE_LLM_BACKEND:-azure_openai}"

  # If ANTHROPIC_API_KEY was wrongly set to an Azure key:
  unset ANTHROPIC_API_KEY

  # Anthropic (real key only — sk-ant-...):
  export ANTHROPIC_API_KEY="sk-ant-..."

  # Then generate variants:
  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/generate_variants.py content/posts/SECTION/SLUG
EOF
}

print_missing_secret_file_help() {
  local file="${1:-${AI_SECRET_FILE:-/tmp/ai}}"
  echo "error: secret file not found: ${file}" >&2
  echo "" >&2
  echo "Commands to fix:" >&2
  echo "  export AI_SECRET_FILE=/path/to/ai.json   # JSON with api_key, azure_openai_endpoint, ..." >&2
  echo "  # or copy your Foundry credentials file to /tmp/ai" >&2
  echo "" >&2
  print_llm_env_commands >&2
  exit 1
}

print_missing_keychain_help() {
  echo "error: no Keychain entry for ${KEYCHAIN_SERVICE_JSON:-pcioasis-blog/azure-ai-foundry}" >&2
  echo "" >&2
  echo "Commands to fix:" >&2
  echo "  ./deploy/secrets/bootstrap-macos-keychain.sh" >&2
  echo '  eval "$(./deploy/secrets/export-macos-keychain.sh)"' >&2
  echo '  export AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-YOUR_DEPLOYMENT_NAME}"' >&2
  exit 1
}

print_missing_gcloud_help() {
  echo "error: gcloud CLI not found" >&2
  echo "" >&2
  echo "Commands to fix:" >&2
  echo "  brew install --cask google-cloud-sdk" >&2
  echo "  gcloud auth login" >&2
  echo "  gcloud config set project ${GCP_PROJECT:-pcioasis-blog}" >&2
  exit 1
}
