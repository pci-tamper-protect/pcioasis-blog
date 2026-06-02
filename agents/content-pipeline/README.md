# Content pipeline

Generate and review platform-specific variants from Hugo `index.md` posts.

## Setup (`uv`)

```bash
cd agents/content-pipeline
uv sync
```

Dev dependencies (tests):

```bash
uv sync --extra dev
```

## Run (from repo root)

Use `--project` (not `--directory`) so post paths stay relative to `pcioasis-blog/`:

```bash
cd ~/projectos/pcioasis-blog

# Credentials (first match): ANTHROPIC_API_KEY → Azure OpenAI env → OPENAI_API_KEY / AI_API_KEY → /tmp/ai
eval "$(./deploy/secrets/export-macos-keychain.sh)"   # sets AZURE_OPENAI_* and AI_API_KEY
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"  # required for Azure backend

# Or Anthropic only (must be sk-ant-…, not an Azure key):
# export ANTHROPIC_API_KEY="sk-ant-…"

# If you previously ran export-macos-keychain.sh, clear a bad alias:
# unset ANTHROPIC_API_KEY

uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_variants.py \
  content/posts/zkTLS/zktls-proof-of-provenance

uv run --project agents/content-pipeline \
  python agents/content-pipeline/preview_server.py \
  content/posts/zkTLS/zktls-proof-of-provenance

uv run --project agents/content-pipeline \
  python agents/content-pipeline/assemble_pr.py \
  content/posts/zkTLS/zktls-proof-of-provenance --dry-run
```

Dry-run (no API key, no files):

```bash
uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_variants.py \
  content/posts/zkTLS/zktls-proof-of-provenance --dry-run
```

## Video arena (Phase 3a)

After text variants exist, compare four text-to-video APIs and pick a winner in the browser.

```bash
uv sync --project agents/content-pipeline --extra dev --extra video-arena
eval "$(./deploy/secrets/export-macos-keychain.sh)"   # Azure
export GOOGLE_CLOUD_PROJECT=your-project              # Vertex (GCP credits)
export VIDEO_ARENA_S3_OUTPUT_URI=s3://bucket/arena/   # Bedrock Luma
export REPLICATE_API_TOKEN=r8_...                     # comparison lane

uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_video_arena.py \
  content/posts/zkTLS/zktls-proof-of-provenance

open content/posts/zkTLS/zktls-proof-of-provenance/_variants/video-arena/review.html
```

See `docs/content-pipeline/VIDEO_ARENA.md`.

## Tests

```bash
cd agents/content-pipeline
uv sync --extra dev
uv run pytest -q
```
