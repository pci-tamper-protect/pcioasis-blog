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

## Tests

```bash
cd agents/content-pipeline
uv sync --extra dev
uv run pytest -q
```
