# Azure CLI scripts (`deploy/az/scripts`)

Helper scripts for Foundry / Azure OpenAI resource management. Requires [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (`az`) and `az login`.

## Layout

| Script | Purpose |
|--------|---------|
| `deploy-sora-2-e-skimming.sh` | Deploy Sora 2 on `e-skimming-app-resource` / `crawl-ptp-prd` |
| `deploy-sora-2-management-global.sh` | Same deploy flow on `management-ptp-global-resource` (video arena) |
| `list-deployments.sh` | List deployments on an account |
| `show-subscription.sh` | Show active subscription; find which sub owns a resource |

Shared defaults live in `scripts/lib/common.sh` (override via env vars).

## Deploy Sora 2 (e-skimming / crawl-ptp-prd)

```bash
chmod +x deploy/az/scripts/*.sh
./deploy/az/scripts/deploy-sora-2-e-skimming.sh
```

Equivalent raw command:

```bash
az cognitiveservices account deployment create \
  --name e-skimming-app-resource \
  --resource-group crawl-ptp-prd-rg \
  --subscription crawl-ptp-prd \
  --deployment-name sora-2 \
  --model-name sora-2 \
  --model-version "2025-10-06" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --sku-capacity 1
```

If the portal reports Sora 2 unavailable in **canadacentral**, use the management-global script instead (resource in **eastus2**):

```bash
./deploy/az/scripts/deploy-sora-2-management-global.sh
```

Prefer a non-retiring model version when listed:

```bash
AZ_SORA_MODEL_VERSION=2025-12-08 ./deploy/az/scripts/deploy-sora-2-management-global.sh
```

## After deploy — video arena creds

Sora secrets are separate from chat (`/tmp/ai`). See `deploy/secrets/export-sora.sh` and `azure-ai-foundry-sora2.json.example`.
