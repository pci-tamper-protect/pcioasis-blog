# Vertex AI — Veo 3.1 Fast (video arena)

Arena provider: `vertex_veo` · Model: `veo-3.1-fast-generate-001`

**Hub:** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md)

## Prerequisites

- GCP project with billing (credits OK)
- [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) enabled
- Veo access in your project/region ([video generation overview](https://cloud.google.com/vertex-ai/generative-ai/docs/video/overview))
- `gcloud` + Application Default Credentials

## One-time auth

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
```

## Config file

```bash
cp deploy/vertex/veo-config.json.example /tmp/veo.json
# edit project_id and location
```

## Load env

```bash
chmod +x deploy/vertex/export-veo.sh
eval "$(./deploy/vertex/export-veo.sh)"
```

## Optional: GCP Secret Manager

```bash
gcloud secrets create vertex-veo-config --project=pcioasis-blog --replication-policy=automatic 2>/dev/null || true
gcloud secrets versions add vertex-veo-config --project=pcioasis-blog --data-file=/tmp/veo.json
export VERTEX_CONFIG_GCP_SECRET=vertex-veo-config
eval "$(./deploy/vertex/export-veo.sh)"
```

## Test

```bash
./deploy/scripts/verify-video-credentials.sh vertex_veo
```
