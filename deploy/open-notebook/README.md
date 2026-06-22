# Open Notebook — research podcasts & narration

[Open Notebook](https://www.open-notebook.ai/) is a privacy-first, self-hosted alternative to Google Notebook LM. Use it for **multi-speaker podcast generation** from research notes — a local/cloud-hybrid option for Phase 3b narration instead of ElevenLabs alone.

**Hub:** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md) · **Repo:** [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)

## What it covers

| Capability | Notes |
|------------|--------|
| Podcast from notes | 1–4 custom speakers, async generation, Episode Profiles |
| Content ingestion | PDFs, YouTube, audio, web pages, Office docs |
| TTS providers | OpenAI, Google, ElevenLabs, **local TTS** (no API calls) |
| REST API | Port **5055** (Docker default) |

## Quick start (Docker)

```bash
git clone https://github.com/lfnovo/open-notebook.git
cd open-notebook
docker compose up -d
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:8502 |
| REST API | http://localhost:5055 |

Docs: [docker-compose install](https://github.com/lfnovo/open-notebook/blob/main/docs/1-INSTALLATION/docker-compose.md)

## Fully local stack (Ollama)

```bash
cp examples/docker-compose-ollama.yml docker-compose.yml
docker compose up -d
```

Then in **Settings → API Keys**: add Ollama (`http://ollama:11434`), discover models, register. Use **local TTS** in podcast Episode Profiles for narration without cloud TTS.

## Credentials

No repo secret file — configure in the Open Notebook UI:

| Provider | Where | Used for |
|----------|--------|----------|
| OpenAI / Anthropic / etc. | Settings → API Keys | Chat, summarization, optional TTS |
| ElevenLabs | Settings → API Keys | High-quality podcast voices (optional) |
| Ollama | Settings → API Keys | Local LLM + local TTS path |

For content-pipeline narration, prefer **local TTS** or point podcast output at `_variants/youtube/script.md` sources in a dedicated notebook.

## Content pipeline fit

- **Phase 3b** ([`docs/content-pipeline/PLAN.md`](../../docs/content-pipeline/PLAN.md)): generate narration MP3 from `script.md` via podcast or TTS workflow
- Complements **OmniVoice Studio** (raw TTS/dubbing) when you want structured research → dialogue audio

## Links

- [What is Open Notebook?](https://www.open-notebook.ai/)
- [Podcasts explained](https://github.com/lfnovo/open-notebook/blob/main/docs/2-CORE-CONCEPTS/podcasts-explained.md)
- [Discord](https://discord.gg/37XJPXfz2w)
