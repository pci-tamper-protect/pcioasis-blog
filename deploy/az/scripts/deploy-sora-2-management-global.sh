#!/usr/bin/env bash
# Deploy Sora 2 on management-ptp-global-resource (Azure subscription 1 / eastus2).
# This is the subscription where Sora 2 deployed successfully for the video arena.
#
# Usage:
#   ./deploy/az/scripts/deploy-sora-2-management-global.sh
#   AZ_SORA_MODEL_VERSION=2025-12-08 ./deploy/az/scripts/deploy-sora-2-management-global.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export AZ_SUBSCRIPTION="${AZ_SUBSCRIPTION:-781e4664-655c-453c-a743-470e6d0c7421}"
export AZ_RESOURCE_GROUP="${AZ_RESOURCE_GROUP:-rg-kesten.broughton-3609}"
export AZ_COGNITIVE_ACCOUNT="${AZ_COGNITIVE_ACCOUNT:-management-ptp-global-resource}"

exec "$SCRIPT_DIR/deploy-sora-2-e-skimming.sh"
