#!/usr/bin/env python3
"""Generate a culturally-variant audio overview with configurable hosts/voices/persona.

Usage:
    GOOGLE_CLOUD_PROJECT=pcioasis-blog \
      uv run --extra gemini python generate_audio_overview_variant.py \
      --variant black-hosts POST_DIR
"""

from __future__ import annotations

import argparse
import json
import os
import re
import wave
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_SCRIPT_MODEL = "gemini-2.5-flash"

VARIANTS: dict[str, dict] = {
    "black-hosts": {
        "host_a": "Marcus",
        "host_b": "Keisha",
        "voice_a": "Aoede",
        "voice_b": "Charon",
        "system": (
            "You write NotebookLM-style audio overview scripts: two curious hosts "
            "discuss one source document in a conversational podcast. Your hosts are "
            "Marcus and Keisha. Follow the source document closely — cover the same "
            "points, in roughly the same order, at roughly the same depth. Do NOT add "
            "historical detours, extra framing, or themes not in the source. The only "
            "difference from a neutral script: Marcus and Keisha speak with the natural "
            "register of Black journalists — warm, direct, occasionally dry — and may "
            "briefly note when a pattern resonates with lived community experience, but "
            "only when the source itself raises that point. Keep it grounded in the "
            "document. Output ONLY the dialogue, no stage directions or markdown. Each "
            "line must start with exactly one speaker name followed by a colon: "
            "\"Marcus: ...\" or \"Keisha: ...\". "
            "Target length when spoken: about {minutes} minutes."
        ),
    },
}


def parse_frontmatter(text: str):
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


def normalize_script(text: str, host_a: str, host_b: str) -> str:
    pattern = re.compile(rf"^({re.escape(host_a)}|{re.escape(host_b)})\s*:", re.I)
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if pattern.match(line):
            speaker, rest = line.split(":", 1)
            lines.append(f"{speaker.strip().title()}: {rest.strip()}")
        else:
            speaker = host_a if len(lines) % 2 == 0 else host_b
            lines.append(f"{speaker}: {line}")
    return "\n".join(lines)


def generate_script(client, *, title: str, body: str, minutes: int, system: str, host_a: str, host_b: str) -> str:
    from google.genai import types

    model = os.environ.get("GEMINI_SCRIPT_MODEL", DEFAULT_SCRIPT_MODEL)
    user = f"Title: {title}\n\nSource document:\n\n{body}\n\nWrite the two-host dialogue now."
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
    return normalize_script(text, host_a, host_b)


def synthesize(client, script: str, dest: Path, *, host_a: str, host_b: str, voice_a: str, voice_b: str) -> None:
    from google.genai import types

    model = os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)
    prompt = f"TTS the following conversation between {host_a} and {host_b}:\n{script}"
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker=host_a,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_a)
                            ),
                        ),
                        types.SpeakerVoiceConfig(
                            speaker=host_b,
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_b)
                            ),
                        ),
                    ]
                )
            ),
        ),
    )
    pcm = response.candidates[0].content.parts[0].inline_data.data
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a culturally-variant audio overview")
    parser.add_argument("post_dir", type=Path)
    parser.add_argument("--variant", default="black-hosts", choices=list(VARIANTS))
    parser.add_argument("--minutes", type=int, default=4)
    parser.add_argument("--script-only", action="store_true")
    args = parser.parse_args()

    v = VARIANTS[args.variant]
    host_a, host_b = v["host_a"], v["host_b"]
    voice_a, voice_b = v["voice_a"], v["voice_b"]
    system = v["system"].format(minutes=args.minutes)

    from gemini_client import gemini_configured, missing_gemini_help, make_gemini_client
    import sys
    if not gemini_configured():
        print(missing_gemini_help(), file=sys.stderr)
        sys.exit(1)

    client, backend = make_gemini_client()
    post_dir = args.post_dir.resolve()
    index_md = post_dir / "index.md"
    meta, body = parse_frontmatter(index_md.read_text(encoding="utf-8"))
    title = str(meta.get("title") or post_dir.name)

    out_dir = post_dir / "_variants" / f"audio-overview-{args.variant}"
    out_dir.mkdir(parents=True, exist_ok=True)

    script = generate_script(client, title=title, body=body, minutes=args.minutes,
                             system=system, host_a=host_a, host_b=host_b)
    (out_dir / "script.txt").write_text(script + "\n", encoding="utf-8")
    print(f"Script: {out_dir / 'script.txt'}")

    wav_path = out_dir / "overview.wav"
    tts_model = os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)
    script_model = os.environ.get("GEMINI_SCRIPT_MODEL", DEFAULT_SCRIPT_MODEL)
    status = "script_only"
    message = ""

    if not args.script_only:
        try:
            synthesize(client, script, wav_path, host_a=host_a, host_b=host_b,
                       voice_a=voice_a, voice_b=voice_b)
            status = "ok"
            print(f"WAV:    {wav_path}")
        except Exception as exc:
            status = "tts_failed"
            message = str(exc)
            print(f"TTS failed: {exc}", file=sys.stderr)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "variant": args.variant,
        "title": title,
        "post_dir": str(post_dir),
        "backend": backend,
        "script_model": script_model,
        "tts_model": tts_model if not args.script_only else None,
        "hosts": [host_a, host_b],
        "voices": [voice_a, voice_b],
        "status": status,
        "message": message,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
