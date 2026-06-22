# shellcheck shell=bash
# Shared helpers for deploy/az/scripts. Source only; do not execute directly.

set -euo pipefail

: "${AZ_SUBSCRIPTION:=crawl-ptp-prd}"
: "${AZ_RESOURCE_GROUP:=crawl-ptp-prd-rg}"
: "${AZ_COGNITIVE_ACCOUNT:=e-skimming-app-resource}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: $1 not found" >&2
    exit 1
  }
}

az_account_set() {
  need_cmd az
  az account set --subscription "$AZ_SUBSCRIPTION"
  echo "Azure subscription: $(az account show --query name -o tsv) ($AZ_SUBSCRIPTION)"
}

list_deployments() {
  az cognitiveservices account deployment list \
    --name "$AZ_COGNITIVE_ACCOUNT" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --subscription "$AZ_SUBSCRIPTION" \
    -o table
}

list_sora_models() {
  az cognitiveservices account list-models \
    --name "$AZ_COGNITIVE_ACCOUNT" \
    --resource-group "$AZ_RESOURCE_GROUP" \
    --subscription "$AZ_SUBSCRIPTION" \
    --query "[?contains(name, 'sora')].{name:name, version:version}" \
    -o table
}
