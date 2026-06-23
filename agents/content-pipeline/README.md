# Content pipeline

Generate and review platform-specific variants from Hugo `index.md` posts.

Per-platform format rules: `platform_specs.py` (agent prompts) and `docs/content-pipeline/PLATFORM_PLAYBOOK.md` (research summary).

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

See `docs/content-pipeline/VIDEO_ARENA.md` and `video_arena/AGENTS.md`.

## Audio overview (Gemini API)

NotebookLM-style two-host podcast from a post — **bills to your GCP project** via Vertex (same env as Veo), no Enterprise license.

```bash
uv sync --project agents/content-pipeline --extra gemini
eval "$(./deploy/vertex/export-veo.sh)"
export GOOGLE_CLOUD_QUOTA_PROJECT=pcioasis-blog

uv run --project agents/content-pipeline --extra gemini \
  python agents/content-pipeline/generate_audio_overview.py \
  content/posts/llm-security/meta-instagram-ai-excessive-agency

# Script only (skip TTS):
uv run --project agents/content-pipeline --extra gemini \
  python agents/content-pipeline/generate_audio_overview.py POST_DIR --script-only
```

Output: `_variants/audio-overview/script.txt`, `overview.wav`, `manifest.json`.

Optional: `GEMINI_API_KEY` (AI Studio) instead of Vertex; `GEMINI_SCRIPT_MODEL`, `GEMINI_TTS_MODEL`.

**Agent from user text** (tools direct or LLM-planned):

```bash
uv run --project agents/content-pipeline \
  python agents/content-pipeline/run_video_arena_agent.py POST_DIR \
  "Run final pass combine"
```

## Post variants to social platforms

After `generate_variants.py` writes `_variants/`, post them directly to platforms.

```bash
uv sync --project agents/content-pipeline --extra social
uv run --project agents/content-pipeline --extra social \
  python -m playwright install chromium   # one-time browser install
```

**One-time login per Playwright platform** (opens a real headed browser):

```bash
# Run once per platform; session saved to ~/.config/pcioasis-posting/sessions/
uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py --login facebook

uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py --login threads

uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py --login twitter

uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py --login linkedin
```

**API platforms** (set env vars, no login needed):

```bash
export BLUESKY_HANDLE="yourhandle.bsky.social"
export BLUESKY_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"   # Settings → App passwords
export MASTODON_ACCESS_TOKEN="..."                    # Settings → Development → New app
export MASTODON_SERVER="infosec.exchange"             # or your instance
```

**Post all text platforms:**

```bash
uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py \
  content/posts/district31/cisa-brief

# Specific platforms only
uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py \
  content/posts/district31/cisa-brief --platforms bluesky,mastodon,linkedin

# Dry run first
uv run --project agents/content-pipeline --extra social \
  python agents/content-pipeline/post_variants.py \
  content/posts/district31/cisa-brief --dry-run
```

**Platforms:** `facebook` `threads` `twitter` `linkedin` — Playwright browser sessions
`bluesky` `mastodon` — direct API (env vars above)
`tiktok` `instagram` `snapchat` `youtube` — video platforms; script printed, post manually

## Tests

```bash
cd agents/content-pipeline
uv sync --extra dev
uv run pytest -q
```
