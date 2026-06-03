#!/usr/bin/env bash
# List model deployments on an Azure OpenAI / AIServices account.
#
# Usage:
#   ./deploy/az/scripts/list-deployments.sh
#   AZ_SUBSCRIPTION=management-ptp-global AZ_COGNITIVE_ACCOUNT=management-ptp-global-resource \
#     AZ_RESOURCE_GROUP=rg-kesten.broughton-3609 ./deploy/az/scripts/list-deployments.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

az_account_set
echo "Account: $AZ_COGNITIVE_ACCOUNT ($AZ_RESOURCE_GROUP)"
list_deployments
