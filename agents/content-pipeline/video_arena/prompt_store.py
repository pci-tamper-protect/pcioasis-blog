"""Load and save the shared video-arena prompt (prompt.txt)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from video_arena.prompt_builder import build_video_prompt, find_reference_image


def load_prompt_text(arena_dir: Path, manifest: dict | None = None) -> str:
    """Prefer prompt.txt on disk over manifest snapshot."""
    path = arena_dir / "prompt.txt"
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    if manifest:
        return (manifest.get("prompt") or "").strip()
    return ""


def resolve_arena_prompt(
    post_dir: Path,
    arena_dir: Path,
    *,
    title: str = "",
) -> tuple[str, Path | None]:
    """Return (prompt, reference_image). Uses saved prompt.txt when present."""
    path = arena_dir / "prompt.txt"
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        prompt = path.read_text(encoding="utf-8").strip()
        ref = find_reference_image(post_dir)
        return prompt, ref
    prompt, ref = build_video_prompt(post_dir, title=title)
    arena_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt + "\n", encoding="utf-8")
    return prompt, ref


def save_arena_prompt(arena_dir: Path, prompt: str) -> None:
    """Persist edited prompt to prompt.txt and manifest.json."""
    text = prompt.strip()
    if not text:
        raise ValueError("prompt is empty")

    arena_dir.mkdir(parents=True, exist_ok=True)
    (arena_dir / "prompt.txt").write_text(text + "\n", encoding="utf-8")

    manifest_path = arena_dir / "manifest.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        data = {}
    data["prompt"] = text
    data["prompt_updated_at"] = datetime.now(UTC).isoformat()
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
