#!/usr/bin/env bash
# AWS Bedrock Luma Ray 2 smoke test.
# Usage: ./deploy/aws/test-bedrock-luma.sh [--generate]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

eval "$("$SCRIPT_DIR/export-bedrock-luma.sh")"
exec "$REPO_ROOT/deploy/scripts/test-video-provider.sh" bedrock_luma "$@"
