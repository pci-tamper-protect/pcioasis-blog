"""Generate a two-host podcast script and multi-speaker WAV from a blog post."""

from __future__ import annotations

import json
import os
import re
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_SCRIPT_MODEL = "gemini-2.5-flash"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
HOST_A = "Alex"
HOST_B = "Sam"
VOICE_A = "Kore"
VOICE_B = "Puck"

SCRIPT_SYSTEM = """You write NotebookLM-style audio overview scripts: two curious hosts
discuss one source document in a conversational podcast. Output ONLY the dialogue,
no stage directions or markdown. Each line must start with exactly one speaker name
followed by a colon, e.g. "Alex: ..." or "Sam: ...". Use those two names only.
Keep it engaging, cite specific facts from the source, and avoid filler. Target length
when spoken: about {minutes} minutes."""

SCRIPT_USER = """Title: {title}

Source document:

{body}

Write the two-host dialogue now."""


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    import yaml

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


def build_script_prompt(title: str, body: str, *, minutes: int) -> tuple[str, str]:
    return (
        SCRIPT_SYSTEM.format(minutes=minutes),
        SCRIPT_USER.format(title=title or "Untitled", body=body),
    )


def generate_script(client, *, title: str, body: str, minutes: int) -> str:
    from google.genai import types

    model = os.environ.get("GEMINI_SCRIPT_MODEL", DEFAULT_SCRIPT_MODEL)
    system, user = build_script_prompt(title, body, minutes=minutes)
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.9,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty script")
    return normalize_script(text)


def normalize_script(text: str) -> str:
    """Ensure Alex/Sam speaker labels for TTS multi-speaker config."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^(Alex|Sam)\s*:", line, re.I):
            speaker, rest = line.split(":", 1)
            lines.append(f"{speaker.strip().title()}: {rest.strip()}")
            continue
        # Alternate speakers for unlabeled lines
        speaker = HOST_A if len(lines) % 2 == 0 else HOST_B
        lines.append(f"{speaker}: {line}")
    return "\n".join(lines)


def tts_prompt_from_script(script: str) -> str:
    return f"TTS the following conversation between {HOST_A} and {HOST_B}:\n{script}"


def write_pcm_as_wav(path: Path, pcm: bytes, *, rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def synthesize_overview(client, script: str, dest: Path) -> None:
    from google.genai import types

    model = os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)
    response = client.models.generate_content(
        model=model,
        contents=tts_prompt_from_script(script),
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker=HOST_A,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=VOICE_A,
                                )
                            ),
                        ),
                        types.SpeakerVoiceConfig(
                            speaker=HOST_B,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=VOICE_B,
                                )
                            ),
                        ),
                    ]
                )
            ),
        ),
    )
    parts = response.candidates[0].content.parts
    pcm = parts[0].inline_data.data
    write_pcm_as_wav(dest, pcm)


def run_audio_overview(
    post_dir: Path,
    *,
    minutes: int = 4,
    skip_tts: bool = False,
) -> Path:
    """Write _variants/audio-overview/{script.txt, overview.wav, manifest.json}."""
    post_dir = post_dir.resolve()
    index_md = post_dir / "index.md"
    if not index_md.is_file():
        raise FileNotFoundError(f"No index.md at {index_md}")

    from gemini_client import make_gemini_client

    client, backend = make_gemini_client()
    meta, body = parse_frontmatter(index_md.read_text(encoding="utf-8"))
    title = str(meta.get("title") or post_dir.name)

    out_dir = post_dir / "_variants" / "audio-overview"
    out_dir.mkdir(parents=True, exist_ok=True)

    script = generate_script(client, title=title, body=body, minutes=minutes)
    (out_dir / "script.txt").write_text(script + "\n", encoding="utf-8")

    wav_path = out_dir / "overview.wav"
    tts_model = os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)
    script_model = os.environ.get("GEMINI_SCRIPT_MODEL", DEFAULT_SCRIPT_MODEL)
    status = "script_only" if skip_tts else "ok"
    message = ""

    if not skip_tts:
        try:
            synthesize_overview(client, script, wav_path)
        except Exception as exc:  # noqa: BLE001
            status = "script_ok_tts_failed"
            message = str(exc)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "title": title,
        "post_dir": str(post_dir),
        "backend": backend,
        "script_model": script_model,
        "tts_model": tts_model if not skip_tts else None,
        "hosts": [HOST_A, HOST_B],
        "status": status,
        "message": message,
        "script_path": str(out_dir / "script.txt"),
        "audio_path": str(wav_path) if wav_path.is_file() else None,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return out_dir
