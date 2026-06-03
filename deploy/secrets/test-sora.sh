#!/usr/bin/env bash
# Azure Sora 2 smoke test.
# Usage: ./deploy/secrets/test-sora.sh [--generate]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

eval "$("$SCRIPT_DIR/export-sora.sh")"
exec "$REPO_ROOT/deploy/scripts/test-video-provider.sh" azure_sora "$@"
