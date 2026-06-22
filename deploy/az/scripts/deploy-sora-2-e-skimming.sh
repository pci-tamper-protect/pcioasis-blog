#!/usr/bin/env bash
# Deploy Sora 2 on e-skimming-app-resource (crawl-ptp-prd).
#
# Note: Sora 2 may be blocked if the Foundry *project* region is canadacentral
# (Global Standard SKU not available there). Resource region is eastus2; check portal
# if deploy fails. For a working Sora slot today, see deploy-sora-2-management-global.sh.
#
# Usage:
#   ./deploy/az/scripts/deploy-sora-2-e-skimming.sh
#   AZ_SORA_MODEL_VERSION=2025-12-08 ./deploy/az/scripts/deploy-sora-2-e-skimming.sh
#
# Overrides (env):
#   AZ_SUBSCRIPTION          default: crawl-ptp-prd
#   AZ_RESOURCE_GROUP        default: crawl-ptp-prd-rg
#   AZ_COGNITIVE_ACCOUNT     default: e-skimming-app-resource
#   AZ_SORA_DEPLOYMENT_NAME  default: sora-2
#   AZ_SORA_MODEL_NAME       default: sora-2
#   AZ_SORA_MODEL_VERSION    default: 2025-10-06
#   AZ_SORA_SKU_NAME         default: Standard
#   AZ_SORA_SKU_CAPACITY     default: 1

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

: "${AZ_SORA_DEPLOYMENT_NAME:=sora-2}"
: "${AZ_SORA_MODEL_NAME:=sora-2}"
: "${AZ_SORA_MODEL_VERSION:=2025-10-06}"
: "${AZ_SORA_SKU_NAME:=Standard}"
: "${AZ_SORA_SKU_CAPACITY:=1}"

az_account_set

echo "Available Sora models on $AZ_COGNITIVE_ACCOUNT:"
list_sora_models || true
echo ""

echo "Existing deployments:"
list_deployments || true
echo ""

echo "Creating deployment $AZ_SORA_DEPLOYMENT_NAME ($AZ_SORA_MODEL_NAME @ $AZ_SORA_MODEL_VERSION)..."
az cognitiveservices account deployment create \
  --name "$AZ_COGNITIVE_ACCOUNT" \
  --resource-group "$AZ_RESOURCE_GROUP" \
  --subscription "$AZ_SUBSCRIPTION" \
  --deployment-name "$AZ_SORA_DEPLOYMENT_NAME" \
  --model-name "$AZ_SORA_MODEL_NAME" \
  --model-version "$AZ_SORA_MODEL_VERSION" \
  --model-format OpenAI \
  --sku-name "$AZ_SORA_SKU_NAME" \
  --sku-capacity "$AZ_SORA_SKU_CAPACITY"

echo ""
echo "Done. Deployments:"
list_deployments
