# Replicate — MiniMax Hailuo 2.3 (video arena)

Arena provider: `replicate_hailuo` · Model: [minimax/hailuo-2.3](https://replicate.com/minimax/hailuo-2.3)

**Hub:** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md)

## Get API token

1. Create account at [replicate.com](https://replicate.com).
2. Open [API tokens](https://replicate.com/account/api-tokens).
3. **Create token** → copy `r8_…` value.

## Config file

```bash
cp deploy/replicate/replicate-config.json.example /tmp/replicate.json
# set api_token
```

## Load env

```bash
chmod +x deploy/replicate/export-replicate.sh
eval "$(./deploy/replicate/export-replicate.sh)"
```

## Python dependency

```bash
uv sync --project agents/content-pipeline --extra video-arena
```

## Optional: GCP Secret Manager

```bash
gcloud secrets create replicate-api-token --project=pcioasis-blog --replication-policy=automatic 2>/dev/null || true
gcloud secrets versions add replicate-api-token --project=pcioasis-blog --data-file=/tmp/replicate.json
export REPLICATE_CONFIG_GCP_SECRET=replicate-api-token
eval "$(./deploy/replicate/export-replicate.sh)"
```

## Test

```bash
./deploy/scripts/verify-video-credentials.sh replicate_hailuo
```
