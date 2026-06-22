#!/usr/bin/env bash
# Vertex Veo smoke test — load config then probe permissions or generate a clip.
#
# Usage:
#   ./deploy/vertex/test-veo.sh              # permission check (default)
#   ./deploy/vertex/test-veo.sh --generate   # minimal billed generation

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

eval "$("$SCRIPT_DIR/export-veo.sh")"
exec "$REPO_ROOT/deploy/scripts/test-video-provider.sh" vertex_veo "$@"
