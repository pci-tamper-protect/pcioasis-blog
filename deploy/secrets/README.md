# AI secrets bootstrap (`deploy/secrets`)

Bootstrap scripts move Azure AI Foundry credentials from a **local file** into macOS Keychain and GCP Secret Manager (`pcioasis-blog`). A small Python loader normalizes the same JSON for **Azure OpenAI**, plain **OpenAI**, and **Anthropic** callers.

Azure CLI deploy helpers (Sora 2, list deployments): `deploy/az/scripts/` — see `deploy/az/README.md`.

**Video arena (cloud T2V):** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md)  
**Local audio (Open Notebook, OmniVoice):** same hub — sections 5–6

## Secret file format

Default path: `/tmp/ai` (override with `AI_SECRET_FILE`).

**JSON (recommended):**

```json
{
  "project_endpoint": "https://….services.ai.azure.com/api/projects/…",
  "azure_openai_endpoint": "https://….openai.azure.com/",
  "api_key": "…",
  "api_key_name": "default"
}
```

**Bare API key** (single line, no JSON) is also accepted; stored in Keychain under account `default`.

| Field | Used for |
|--------|-----------|
| `project_endpoint` | Azure AI Foundry project API |
| `azure_openai_endpoint` | OpenAI-compatible chat/embeddings via Azure |
| `api_key` | API key for Azure OpenAI / Foundry |
| `api_key_name` | Keychain account name (default: `default`) |

## macOS Keychain

```bash
chmod +x deploy/secrets/bootstrap-macos-keychain.sh deploy/secrets/export-macos-keychain.sh

# Reads /tmp/ai by default
./deploy/secrets/bootstrap-macos-keychain.sh

# Load into current shell (content pipeline, OpenAI SDK, etc.)
eval "$(./deploy/secrets/export-macos-keychain.sh)"
```

The Keychain **account** is `api_key_name` from your JSON (default: `default`). If bootstrap printed a different account, either omit `KEYCHAIN_ACCOUNT` (export auto-detects the single entry) or set it explicitly:

```bash
eval "$(KEYCHAIN_ACCOUNT=e-skimming-app ./deploy/secrets/export-macos-keychain.sh)"
```

Creates:

| Service | Contents |
|---------|----------|
| `pcioasis-blog/azure-ai-foundry` | Full JSON |
| `pcioasis-blog/azure-ai-foundry-api-key` | `api_key` only |

Exported env vars include: `AI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, and `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT`. Does **not** set `ANTHROPIC_API_KEY` (Azure keys must not be sent to Anthropic).

## GCP Secret Manager

```bash
chmod +x deploy/secrets/bootstrap-gcp-secrets.sh

# Project: pcioasis-blog, secret id: azure-ai-foundry
./deploy/secrets/bootstrap-gcp-secrets.sh
```

**Sora (video arena, separate subscription/resource):**

```bash
chmod +x deploy/secrets/bootstrap-gcp-sora-secrets.sh deploy/secrets/export-sora.sh

# /tmp/sora.json — see azure-ai-foundry-sora2.json.example
./deploy/secrets/bootstrap-gcp-sora-secrets.sh
# or manually:
# gcloud secrets versions add azure_ai_foundry_sora2 --project=pcioasis-blog --data-file=/tmp/sora.json

eval "$(./deploy/secrets/export-sora.sh)"   # sets AZURE_SORA_* only (not chat LLM env)
```

**Vertex Veo (video arena, config only — ADC for auth):**

```bash
chmod +x deploy/vertex/bootstrap-gcp-veo-config.sh deploy/vertex/export-veo.sh

# deploy/vertex/veo-config.json — committed in repo
./deploy/vertex/bootstrap-gcp-veo-config.sh
# or: gcloud secrets versions add vertex_veo_config --project=pcioasis-blog --data-file=deploy/vertex/veo-config.json

eval "$(./deploy/vertex/export-veo.sh)"   # sets GOOGLE_CLOUD_* / VERTEX_VEO_*
```

Bootstrap scripts require `gcloud` with permission to create/update secrets.

In GitHub Actions / Cloud Build, mount or fetch:

```bash
gcloud secrets versions access latest \
  --secret=azure-ai-foundry \
  --project=pcioasis-blog > /tmp/ai
```

## Python loader (multi-vendor)

```bash
uv sync --project agents/content-pipeline
uv run --project agents/content-pipeline python deploy/secrets/load_ai_config.py
uv run --project agents/content-pipeline \
  python deploy/secrets/load_ai_config.py --export-shell | source /dev/stdin
```

```python
# From repo root — import by path (no package install required)
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "load_ai_config", Path("deploy/secrets/load_ai_config.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

cfg = _mod.load_ai_config()
client = _mod.create_openai_client(cfg)  # AzureOpenAI if azure_openai_endpoint set
```

Vendor selection:

- **`azure_openai_endpoint` set** → `openai.AzureOpenAI` (OpenAI-compatible Azure AI Foundry / Azure OpenAI)
- **Otherwise `sk-…`** → `openai.OpenAI`
- **Anthropic** → `ANTHROPIC_API_KEY` env if set, else `api_key` from config

Optional env: `AZURE_OPENAI_API_VERSION` (default `2024-10-21`).

## Content pipeline example

```bash
eval "$(./deploy/secrets/export-macos-keychain.sh)"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"   # Azure AI Foundry deployment id
uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_variants.py \
  content/posts/zkTLS/zktls-proof-of-provenance
```

`generate_variants.py` picks **Anthropic** if `ANTHROPIC_API_KEY` is set; otherwise **Azure OpenAI** when `AZURE_OPENAI_ENDPOINT` + a key are present. Force a backend with `CONTENT_PIPELINE_LLM_BACKEND=azure_openai`.

## Security

- Never commit `/tmp/ai` or real JSON under this repo (see `azure-ai-foundry.json.example` only).
- Remove bootstrap source after loading: `shred -u /tmp/ai` (or delete securely).
- Keychain entries are created for `python3` and `security`; adjust `-T` in the bootstrap script if your runtime binary differs.
