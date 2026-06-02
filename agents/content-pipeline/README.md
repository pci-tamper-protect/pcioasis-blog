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
export ANTHROPIC_API_KEY="sk-ant-…"

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

`requirements.txt` is removed; use `uv sync` from this directory.
