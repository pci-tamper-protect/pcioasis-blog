"""Build a shared text-to-video prompt from Clapper variant + optional reference image."""

from __future__ import annotations

import re
from pathlib import Path


def parse_clapper_variant(text: str) -> dict[str, str | list[str]]:
    """Parse HOOK / TALK / CAPTION blocks from clapper.txt."""
    hook = ""
    talks: list[str] = []
    caption = ""
    section: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal hook, caption, section, buf
        if section == "HOOK" and buf:
            hook = " ".join(buf).strip()
        elif section == "TALK" and buf:
            block = "\n".join(buf).strip()
            for line in block.splitlines():
                cleaned = line.strip().lstrip("-•").strip()
                if cleaned:
                    talks.append(cleaned)
        elif section == "CAPTION" and buf:
            caption = "\n".join(buf).strip()
        buf = []

    for line in text.splitlines():
        if line.startswith("HOOK:"):
            flush()
            section = "HOOK"
            buf = [line.removeprefix("HOOK:").strip()]
            continue
        if line.startswith("TALK:"):
            flush()
            section = "TALK"
            buf = [line.removeprefix("TALK:").strip()]
            continue
        if line.startswith("CAPTION:"):
            flush()
            section = "CAPTION"
            buf = [line.removeprefix("CAPTION:").strip()]
            continue
        if section:
            buf.append(line)

    flush()
    return {"hook": hook, "talk": talks, "caption": caption}


def find_reference_image(post_dir: Path) -> Path | None:
    """Prefer portrait/square diagram PNGs in the post directory."""
    candidates = [
        post_dir / "zktls-flow-animation.gif",
        post_dir / "slide-001.png",
        post_dir / "hero.png",
        post_dir / "diagram.png",
    ]
    for path in candidates:
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return path
    for path in sorted(post_dir.glob("*.png")):
        if path.is_file():
            return path
    return None


def build_video_prompt(post_dir: Path, *, title: str = "") -> tuple[str, Path | None]:
    """Return (shared_prompt, optional_reference_image_path)."""
    clapper_path = post_dir / "_variants" / "clapper.txt"
    if not clapper_path.is_file():
        raise FileNotFoundError(
            f"Missing {clapper_path}. Run generate_variants.py first."
        )

    parsed = parse_clapper_variant(clapper_path.read_text(encoding="utf-8"))
    hook = parsed.get("hook") or "Security explainer"
    talks = parsed.get("talk") or []
    talk_line = talks[0] if talks else "Explain the core idea in one visual beat."

    ref = find_reference_image(post_dir)
    ref_hint = (
        f"Visual anchor: match the diagram in the reference image ({ref.name})."
        if ref
        else "Visual anchor: abstract cybersecurity motif (locks, browser chrome, data flow)."
    )

    prompt = f"""Vertical 9:16 short-form tech explainer, 6 seconds, documentary realism.
Title context: {title or post_dir.name}.
On-screen moment: {hook}
Narration beat: {talk_line}
{ref_hint}
Camera: slow stable push-in, no whip pans, no dutch angles.
Lighting: natural office or neutral studio.
Avoid: on-screen text, logos, watermarks, distorted hands/faces, cartoon style, sci-fi neon.
"""
    return prompt.strip(), ref
