"""Per-provider video and thumbnail instruction text (arena dashboard)."""

from __future__ import annotations

from pathlib import Path

VIDEO_BRIEF_FILE = "video_brief.txt"
THUMBNAIL_BRIEF_FILE = "thumbnail_brief.txt"


def load_video_brief(provider_dir: Path) -> str:
    path = provider_dir / VIDEO_BRIEF_FILE
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def save_video_brief(provider_dir: Path, text: str) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    path = provider_dir / VIDEO_BRIEF_FILE
    if not text.strip():
        if path.is_file():
            path.unlink()
        return
    path.write_text(text, encoding="utf-8")


def load_thumbnail_brief(provider_dir: Path) -> str:
    path = provider_dir / THUMBNAIL_BRIEF_FILE
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def save_thumbnail_brief(provider_dir: Path, text: str) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / THUMBNAIL_BRIEF_FILE).write_text(text, encoding="utf-8")


def resolve_provider_video_prompt(shared_prompt: str, provider_dir: Path) -> str:
    """Provider textarea overrides shared script when non-empty."""
    brief = load_video_brief(provider_dir).strip()
    if brief:
        return brief
    return shared_prompt.strip()
