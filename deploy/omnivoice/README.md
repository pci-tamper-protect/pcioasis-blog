# OmniVoice Studio — local TTS, dubbing & voice clone

[OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio) is a local, open-source desktop app — an ElevenLabs-style alternative that runs **entirely on your machine** (voice clone, dubbing, dictation, diarization). Includes a built-in **MCP server** for Cursor / Claude tooling.

**Hub:** [`deploy/VIDEO_GENERATORS.md`](../VIDEO_GENERATORS.md) · **Overview:** [MarkTechPost (May 2026)](https://www.marktechpost.com/2026/05/26/meet-omnivoice-studio-a-local-open-source-alternative-to-elevenlabs/)

## What it covers

| Capability | Stack |
|------------|--------|
| Voice clone | Zero-shot from ~3s clip; default **OmniVoice** engine (600+ languages) |
| Video dubbing | WhisperX → translate → TTS → Demucs stem mix → MP4 |
| Dictation | System-wide overlay (macOS `⌘+⇧+Space`) |
| Speaker diarization | Pyannote + WhisperX (HF token optional) |
| MCP server | Exposes API to Cursor / MCP clients alongside FastAPI |

## Prerequisites

- `ffmpeg`, [Bun](https://bun.sh), [uv](https://docs.astral.sh/uv/)
- Optional GPU: CUDA / Apple MPS / ROCm (CPU-only works, ~3× slower TTS)

## Run from source

```bash
git clone https://github.com/debpalash/OmniVoice-Studio.git
cd OmniVoice-Studio
uv sync
bun install
bun dev
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:5173 |
| FastAPI | http://localhost:8000 |

Pre-built installers (DMG / MSI / AppImage) are on [GitHub Releases](https://github.com/debpalash/OmniVoice-Studio/releases).

## Config (env)

No cloud API key required for core TTS. Optional overrides:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNIVOICE_TTS_BACKEND` | `omnivoice` | `cosyvoice`, `mlx-audio`, `voxcpm2`, `moss-tts-nano`, `kittentts`, … |
| Hugging Face token | — | Pyannote diarization only; see repo `docs/setup/huggingface-token.md` |

Example committed config (paths only, no secrets): [`omnivoice-config.json.example`](omnivoice-config.json.example)

## TTS engines (built-in)

| Engine | Languages | Clone | Platform |
|--------|-----------|-------|----------|
| OmniVoice (default) | 600+ | ✓ | CUDA / MPS / CPU |
| CosyVoice 3 | 9 + 18 dialects | ✓ | CUDA / MPS / CPU |
| MLX-Audio | Multi | Varies | Apple Silicon |
| VoxCPM2 | 30 | ✓ | CUDA / MPS / CPU |
| MOSS-TTS-Nano | 20 | ✓ | CUDA / CPU |
| KittenTTS | English | ✗ | CPU only |

## Content pipeline fit

- **Phase 3b narration**: synthesize MP3 from `_variants/youtube/script.md` without ElevenLabs billing
- **Video arena / Clapper**: re-voice or dub short clips locally before publish
- **Cursor**: use MCP server for scripted TTS from the content pipeline

## Links

- [GitHub — debpalash/OmniVoice-Studio](https://github.com/debpalash/OmniVoice-Studio)
- [Install docs](https://github.com/debpalash/OmniVoice-Studio/tree/main/docs/install)
- [Discord](https://discord.gg/bzQavDfVV9)
