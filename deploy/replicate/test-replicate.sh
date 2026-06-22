#!/usr/bin/env bash
# Replicate Hailuo smoke test.
# Usage: ./deploy/replicate/test-replicate.sh [--generate]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

eval "$("$SCRIPT_DIR/export-replicate.sh")"
exec "$REPO_ROOT/deploy/scripts/test-video-provider.sh" replicate_hailuo "$@"
