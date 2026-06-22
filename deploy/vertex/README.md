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

[`deploy/vertex/veo-config.json`](veo-config.json) is committed in-repo (project, region, model — no secrets). Edit `project_id` if you use a different GCP project, or override:

```bash
export VERTEX_CONFIG_FILE=/path/to/veo.json
```

## Load env

Status prints to **stderr**; only `export …` lines go to stdout (for `eval`).

```bash
chmod +x deploy/vertex/export-veo.sh
eval "$(./deploy/vertex/export-veo.sh)"
# expect on stderr: ok: Vertex Veo loaded from .../deploy/vertex/veo-config.json
```

## GCP Secret Manager

Same JSON as [`veo-config.json`](veo-config.json) (no API keys — ADC handles auth). Mirrors Sora’s `azure_ai_foundry_sora2` pattern for CI and remote agents.

```bash
chmod +x deploy/vertex/bootstrap-gcp-veo-config.sh
./deploy/vertex/bootstrap-gcp-veo-config.sh
# secret id: vertex_veo_config (project pcioasis-blog)
```

Fetch in CI:

```bash
export VERTEX_CONFIG_FILE=/tmp/veo.json
eval "$(./deploy/vertex/export-veo.sh)"   # auto-fetches from GCP when /tmp/veo.json missing
```

## Test

```bash
./deploy/vertex/test-veo.sh
./deploy/scripts/verify-video-credentials.sh vertex_veo
```
