#!/usr/bin/env bash
# Show current az CLI subscription and locate a Cognitive Services account by name.
#
# Usage:
#   ./deploy/az/scripts/show-subscription.sh
#   ./deploy/az/scripts/show-subscription.sh e-skimming-app-resource

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

need_cmd az

echo "Current default subscription:"
az account show --query "{name:name, id:id, user:user.name}" -o table

RESOURCE_NAME="${1:-}"
if [[ -z "$RESOURCE_NAME" ]]; then
  exit 0
fi

echo ""
echo "Searching all subscriptions for resource: $RESOURCE_NAME"
for sub in $(az account list --query "[].id" -o tsv); do
  az resource list --subscription "$sub" --name "$RESOURCE_NAME" \
    --query "[].{subscription:subscriptionId, rg:resourceGroup, type:type, location:location}" \
    -o table 2>/dev/null || true
done
