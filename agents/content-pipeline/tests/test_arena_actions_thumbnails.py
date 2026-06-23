"""Tests for arena thumbnail regeneration action."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.arena_actions import regenerate_provider_thumbnails  # noqa: E402


def test_regenerate_provider_thumbnails_requires_video(tmp_path):
    arena = tmp_path / "video-arena"
    (arena / "azure_sora").mkdir(parents=True)
    try:
        regenerate_provider_thumbnails(arena, "azure_sora")
    except FileNotFoundError as exc:
        assert "azure_sora" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")
