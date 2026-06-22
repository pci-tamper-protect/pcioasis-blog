# Media generators — setup hub

How to obtain API keys and config for **video arena** cloud providers (`generate_video_arena.py`) and **local audio / research** tools for narration, podcasts, and dubbing. Chat/LLM creds for text variants are separate — see [`deploy/secrets/README.md`](secrets/README.md).

**Pipeline docs:** [`docs/content-pipeline/VIDEO_ARENA.md`](../docs/content-pipeline/VIDEO_ARENA.md) · Phase 3b narration: [`docs/content-pipeline/PLAN.md`](../docs/content-pipeline/PLAN.md)

---

## Quick map — Video arena (cloud T2V)

| Provider | Arena ID | Deploy folder | Secret file (local) | Export script |
|----------|----------|---------------|---------------------|---------------|
| Azure Sora 2 | `azure_sora` | [`deploy/az/`](az/README.md) | `/tmp/sora.json` | [`deploy/secrets/export-sora.sh`](secrets/export-sora.sh) |
| Azure Sora v1 | `azure_sora_v1` | [`deploy/az/`](az/README.md) | same as Sora 2 | same |
| Vertex Veo 3.1 Fast | `vertex_veo` | [`deploy/vertex/`](vertex/README.md) | [`deploy/vertex/veo-config.json`](vertex/veo-config.json) (+ GCP `vertex_veo_config`) | [`deploy/vertex/export-veo.sh`](vertex/export-veo.sh) |
| Bedrock Luma Ray 2 | `bedrock_luma` | [`deploy/aws/`](aws/README.md) | `/tmp/bedrock-luma.json` | [`deploy/aws/export-bedrock-luma.sh`](aws/export-bedrock-luma.sh) |
| Replicate Hailuo 2.3 | `replicate_hailuo` | [`deploy/replicate/`](replicate/README.md) | `/tmp/replicate.json` | [`deploy/replicate/export-replicate.sh`](replicate/export-replicate.sh) |

| Test script (per provider) | `./deploy/…/test-*.sh` | Permission check (default) or `--generate` |

**Verify config (env only):**

```bash
chmod +x deploy/scripts/verify-video-credentials.sh
./deploy/scripts/verify-video-credentials.sh
```

**Smoke test (API permission probe — default, fast):**

```bash
chmod +x deploy/scripts/test-video-provider.sh deploy/**/test-*.sh

./deploy/vertex/test-veo.sh
./deploy/secrets/test-sora.sh
./deploy/aws/test-bedrock-luma.sh
./deploy/replicate/test-replicate.sh
./deploy/scripts/test-video-provider.sh all --load
```

**Minimal generation (slow, billed):** append `--generate` to any test script above.

Export scripts print **`ok:`** / **`error:`** on **stderr**; only `export …` lines go to stdout for `eval`.

---

## Quick map — Local audio & research

Self-hosted tools for **narration**, **podcasts**, and **dubbing** (no video arena slot yet). Prefer these over cloud TTS when you want privacy or to avoid ElevenLabs-style subscriptions.

| Tool | Role | Deploy folder | Config | Auth |
|------|------|---------------|--------|------|
| [Open Notebook](https://www.open-notebook.ai/) | Research → multi-speaker **podcasts** / narration from notes | [`deploy/open-notebook/`](open-notebook/README.md) | [`open-notebook-config.json.example`](open-notebook/open-notebook-config.json.example) | Provider keys in UI (or Ollama + local TTS) |
| [OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio) | Local **TTS**, voice clone, **video dubbing**, MCP | [`deploy/omnivoice/`](omnivoice/README.md) | [`omnivoice-config.json.example`](omnivoice/omnivoice-config.json.example) | None (optional HF token for diarization) |

**Read:** [Open Notebook vs Notebook LM](https://www.open-notebook.ai/) · [OmniVoice overview (MarkTechPost, May 2026)](https://www.marktechpost.com/2026/05/26/meet-omnivoice-studio-a-local-open-source-alternative-to-elevenlabs/)

---

## 1. Azure Foundry — Sora 2 & Sora v1

Two arena slots can share one Foundry resource; video often lives on a **different subscription** than chat LLM (`/tmp/ai`).

### Manual: get API key

1. [Azure Portal](https://portal.azure.com) → **Azure AI Foundry** → your project.
2. **Management center** → **Connected resources** → OpenAI / Cognitive Services account (e.g. `management-ptp-global-resource`).
3. **Keys and Endpoint** → copy **Key 1** and note:
   - **Azure OpenAI endpoint** (or Foundry `…services.ai.azure.com` base URL).
4. **Models + endpoints** → confirm deployment name (`sora-2`, optionally `sora` for v1).

Or via CLI (see [`deploy/az/scripts/show-subscription.sh`](az/scripts/show-subscription.sh)):

```bash
az login
./deploy/az/scripts/show-subscription.sh management-ptp-global-resource
az cognitiveservices account keys list \
  --name management-ptp-global-resource \
  --resource-group rg-kesten.broughton-3609 \
  --subscription "Azure subscription 1" \
  --query "key1" -o tsv
```

### Deploy Sora 2 (if missing)

```bash
chmod +x deploy/az/scripts/*.sh
./deploy/az/scripts/deploy-sora-2-management-global.sh
# blocked in canadacentral? use management-global (eastus2), not e-skimming project region
```

Details: [`deploy/az/README.md`](az/README.md)

### Config file

Copy [`deploy/secrets/azure-ai-foundry-sora2.json.example`](secrets/azure-ai-foundry-sora2.json.example) → `/tmp/sora.json`:

```json
{
  "target_url": "https://YOUR-RESOURCE.services.ai.azure.com",
  "api_key": "YOUR_KEY",
  "deployment_name": "sora-2",
  "subscription": "your-subscription-name-or-id"
}
```

`target_url` is enough — `export-sora.sh` derives `azure_openai_endpoint` (`…/openai/v1`).

### Load & GCP backup

```bash
eval "$(./deploy/secrets/export-sora.sh)"
# GCP Secret Manager (project pcioasis-blog):
./deploy/secrets/bootstrap-gcp-sora-secrets.sh
# or: gcloud secrets versions add azure_ai_foundry_sora2 --project=pcioasis-blog --data-file=/tmp/sora.json
```

### Env vars (video arena)

| Variable | Example |
|----------|---------|
| `AZURE_SORA_ENDPOINT` | `https://….openai.azure.com/openai/v1` |
| `AZURE_SORA_API_KEY` | from portal |
| `AZURE_SORA_DEPLOYMENT` | `sora-2` |
| `AZURE_SORA_SECONDS` | `4`, `8`, or `12` (API does not accept `5`) |
| `AZURE_SORA_V1_DEPLOYMENT` | `sora` (v1 slot only) |

**Docs:** [Sora 2 on Foundry](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/video-generation) · [Model catalog](https://ai.azure.com/catalog/models/sora-2)

---

## 2. Google Vertex AI — Veo 3.1 Fast

Uses **Application Default Credentials** (ADC), not a static API key in repo.

### Manual: enable & auth

1. [Google Cloud Console](https://console.cloud.google.com) → project with billing / credits (e.g. `pcioasis-blog` or your GCP project).
2. Enable **Vertex AI API**: APIs & Services → Enable APIs → “Vertex AI API”.
3. Request access to **Veo** if the model is gated in your project/region ([Vertex video docs](https://cloud.google.com/vertex-ai/generative-ai/docs/video/overview)).
4. Install [gcloud](https://cloud.google.com/sdk/docs/install) and authenticate:

```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT
gcloud auth application-default login
```

5. Confirm region — adapter default is `us-central1`:

```bash
gcloud ai models list --region=us-central1 --filter="displayName:veo" 2>/dev/null | head
```

### Config file

Committed in-repo (no secrets): [`deploy/vertex/veo-config.json`](vertex/veo-config.json):

```json
{
  "project_id": "pcioasis-blog",
  "location": "us-central1",
  "model": "veo-3.1-fast-generate-001"
}
```

Override path: `export VERTEX_CONFIG_FILE=/path/to/veo.json`

### Load & GCP backup

```bash
eval "$(./deploy/vertex/export-veo.sh)"

# GCP Secret Manager (project pcioasis-blog) — same JSON, no API keys:
chmod +x deploy/vertex/bootstrap-gcp-veo-config.sh
./deploy/vertex/bootstrap-gcp-veo-config.sh
# or: gcloud secrets versions add vertex_veo_config --project=pcioasis-blog --data-file=deploy/vertex/veo-config.json
```

CI/agents without repo checkout: set `VERTEX_CONFIG_FILE=/tmp/veo.json`; `export-veo.sh` fetches from `vertex_veo_config` when the local file is missing.

### Load

```bash
eval "$(./deploy/vertex/export-veo.sh)"
```

### Env vars

| Variable | Example |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | your GCP project id |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` |
| `VERTEX_VEO_MODEL` | `veo-3.1-fast-generate-001` |
| `VERTEX_VEO_SECONDS` | `6` (optional) |

**Python extra:** `uv sync --project agents/content-pipeline --extra video-arena`

**Docs:** [`deploy/vertex/README.md`](vertex/README.md) · [Generate videos from text](https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-text)

---

## 3. AWS Bedrock — Luma Ray 2

Async generation; output lands in **S3** (adapter polls Bedrock, optional local download).

### Manual: access & S3

1. [AWS Console](https://console.aws.amazon.com) → **Amazon Bedrock** → **Model access** → enable **Luma Ray 2** (`luma.ray-v2:0`) in **us-west-2** ([model params](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-luma.html)).
2. Create (or pick) an S3 bucket prefix for outputs, e.g. `s3://pcioasis-video-arena/bedrock/`.
3. IAM user/role needs at minimum:
   - `bedrock:InvokeModel`, `bedrock:GetAsyncInvoke`, `bedrock:StartAsyncInvoke`
   - `s3:PutObject`, `s3:GetObject` on that prefix
4. Configure AWS CLI:

```bash
aws configure   # or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
aws bedrock list-foundation-models --region us-west-2 \
  --query "modelSummaries[?contains(modelId,'luma')].modelId" --output table
```

### Config file

Copy [`deploy/aws/bedrock-luma-config.json.example`](aws/bedrock-luma-config.json.example) → `/tmp/bedrock-luma.json`:

```json
{
  "region": "us-west-2",
  "s3_output_uri": "s3://your-bucket/video-arena/",
  "model_id": "luma.ray-v2:0"
}
```

### Load

```bash
eval "$(./deploy/aws/export-bedrock-luma.sh)"
```

After a job completes, set `VIDEO_ARENA_S3_DOWNLOAD=1` and `VIDEO_ARENA_S3_OUTPUT_KEY` to fetch MP4 locally (see [`deploy/aws/README.md`](aws/README.md)).

### Env vars

| Variable | Example |
|----------|---------|
| `AWS_REGION` | `us-west-2` |
| `VIDEO_ARENA_S3_OUTPUT_URI` | `s3://bucket/video-arena/` |
| `BEDROCK_LUMA_DURATION` | `5s` or `9s` |
| `BEDROCK_LUMA_RESOLUTION` | `720p` |

**Docs:** [`deploy/aws/README.md`](aws/README.md)

---

## 4. Replicate — MiniMax Hailuo 2.3

Pay-per-run comparison lane; simplest token-based setup.

### Manual: API token

1. Sign in at [replicate.com](https://replicate.com).
2. [Account → API tokens](https://replicate.com/account/api-tokens) → **Create token**.
3. Confirm model page loads: [minimax/hailuo-2.3](https://replicate.com/minimax/hailuo-2.3).

### Config file

Copy [`deploy/replicate/replicate-config.json.example`](replicate/replicate-config.json.example) → `/tmp/replicate.json`:

```json
{
  "api_token": "r8_…"
}
```

### Load

```bash
eval "$(./deploy/replicate/export-replicate.sh)"
```

### Env vars

| Variable | Example |
|----------|---------|
| `REPLICATE_API_TOKEN` | `r8_…` |

**Python extra:** `uv sync --project agents/content-pipeline --extra video-arena`

**Docs:** [`deploy/replicate/README.md`](replicate/README.md)

---

## 5. Open Notebook — podcasts & narration from research

Privacy-first, self-hosted [Notebook LM alternative](https://github.com/lfnovo/open-notebook). Best for turning post research into **multi-speaker podcast audio** (async, customizable speakers). Supports cloud TTS (OpenAI, Google, ElevenLabs) or **local TTS** for fully offline narration.

### Manual: Docker

1. Clone [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook).
2. `docker compose up -d` — UI **8502**, REST API **5055**.
3. **Settings → API Keys** — add LLM provider(s) and optional TTS (or use [Ollama example compose](https://github.com/lfnovo/open-notebook/blob/main/examples/docker-compose-ollama.yml) for local models).

### Config file

[`deploy/open-notebook/open-notebook-config.json.example`](open-notebook/open-notebook-config.json.example) — base URLs only; API keys stay in the Open Notebook UI.

### Content pipeline

- Input: research notes, `script.md`, or ingested PDFs/YouTube in a notebook.
- Output: podcast MP3 for Phase 3b (`_variants/youtube/`) or narration tracks.
- Docs: [`deploy/open-notebook/README.md`](open-notebook/README.md) · [Podcasts explained](https://github.com/lfnovo/open-notebook/blob/main/docs/2-CORE-CONCEPTS/podcasts-explained.md)

---

## 6. OmniVoice Studio — local ElevenLabs alternative

Desktop app ([debpalash/OmniVoice-Studio](https://github.com/debpalash/OmniVoice-Studio)): **voice cloning** (~3s sample), **video dubbing** (YouTube URL or local file), dictation, diarization, and an **MCP server** for Cursor. Runs fully local — no subscription or cloud API key for core TTS.

**Overview:** [Meet OmniVoice Studio (MarkTechPost)](https://www.marktechpost.com/2026/05/26/meet-omnivoice-studio-a-local-open-source-alternative-to-elevenlabs/)

### Manual: install & run

1. Install `ffmpeg`, [Bun](https://bun.sh), [uv](https://docs.astral.sh/uv/).
2. Clone repo and start dev stack:

```bash
git clone https://github.com/debpalash/OmniVoice-Studio.git
cd OmniVoice-Studio
uv sync && bun install && bun dev
```

3. UI: http://localhost:5173 · API: http://localhost:8000 (model weights download on first use).
4. Optional: Hugging Face token for Pyannote diarization — see repo `docs/setup/huggingface-token.md`.

### Config / env

Copy [`deploy/omnivoice/omnivoice-config.json.example`](omnivoice/omnivoice-config.json.example) for local URLs and default engine.

| Variable | Example |
|----------|---------|
| `OMNIVOICE_TTS_BACKEND` | `omnivoice` (or `cosyvoice`, `mlx-audio`, `kittentts`, …) |

### MCP (Cursor)

MCP server starts with `bun dev` — point your MCP client at the local OmniVoice endpoint to drive TTS/dubbing from agents without the desktop UI.

### Content pipeline

- Phase 3b: generate narration MP3 from script text without `ELEVENLABS_API_KEY`.
- Dub arena clips or YouTube sources before ffmpeg assembly.
- Docs: [`deploy/omnivoice/README.md`](omnivoice/README.md)

---

## Run the arena

```bash
cd ~/projectos/pcioasis-blog
uv sync --project agents/content-pipeline --extra dev --extra video-arena

# Load whichever providers you configured (examples):
eval "$(./deploy/secrets/export-sora.sh)"
eval "$(./deploy/vertex/export-veo.sh)"          # optional
eval "$(./deploy/aws/export-bedrock-luma.sh)"    # optional
eval "$(./deploy/replicate/export-replicate.sh)" # optional

uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_video_arena.py \
  content/posts/llm-security/meta-instagram-ai-excessive-agency \
  --skip-critique
```

Preview on phone: `preview_server.py` → `http://<LAN-IP>:5050/arena`

---

## Security

- Never commit `/tmp/*.json` with real keys. Examples use `REPLACE_ME` / `r8_…` placeholders only.
- Rotate keys if they appear in logs or chat.
- Prefer GCP Secret Manager + `export-*.sh` fetch for CI (see [`deploy/secrets/README.md`](secrets/README.md)).

---

## Related

| Path | Purpose |
|------|---------|
| [`deploy/secrets/`](secrets/README.md) | Chat LLM + Sora GCP bootstrap, Keychain, `load_ai_config.py` |
| [`deploy/az/`](az/README.md) | `az` deploy scripts for Sora 2 |
| [`deploy/open-notebook/`](open-notebook/README.md) | Open Notebook — podcasts & narration |
| [`deploy/omnivoice/`](omnivoice/README.md) | OmniVoice Studio — local TTS / dubbing / MCP |
| [`docs/content-pipeline/VIDEO_ARENA.md`](../docs/content-pipeline/VIDEO_ARENA.md) | Arena workflow, output layout, human review |
| [`docs/content-pipeline/PLAN.md`](../docs/content-pipeline/PLAN.md) | Phase 3b long-form video + narration |
