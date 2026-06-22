#!/usr/bin/env bash
# Smoke-test a video arena provider (permission check or minimal generation).
#
# Usage:
#   ./deploy/scripts/test-video-provider.sh vertex_veo --load --check
#   ./deploy/scripts/test-video-provider.sh azure_sora --load --generate
#   ./deploy/scripts/test-video-provider.sh all --load
#
# Or load env yourself:
#   eval "$(./deploy/vertex/export-veo.sh)"
#   ./deploy/scripts/test-video-provider.sh vertex_veo --check

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec uv run --project "$REPO_ROOT/agents/content-pipeline" --extra video-arena \
  python "$SCRIPT_DIR/smoke_video_provider.py" "$@"
