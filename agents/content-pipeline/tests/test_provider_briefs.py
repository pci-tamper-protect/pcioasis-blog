"""Tests for per-provider video/thumbnail brief files."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.provider_briefs import (  # noqa: E402
    resolve_provider_video_prompt,
    save_thumbnail_brief,
    save_video_brief,
)


def test_provider_video_brief_overrides_shared(tmp_path):
    provider = tmp_path / "azure_sora"
    provider.mkdir()
    save_video_brief(provider, "Sora-only phone chat prompt")
    assert resolve_provider_video_prompt("Shared script", provider) == "Sora-only phone chat prompt"


def test_empty_provider_brief_uses_shared(tmp_path):
    provider = tmp_path / "vertex_veo"
    provider.mkdir()
    assert resolve_provider_video_prompt("Shared script", provider) == "Shared script"


def test_thumbnail_brief_roundtrip(tmp_path):
    provider = tmp_path / "azure_sora"
    provider.mkdir()
    save_thumbnail_brief(provider, "max contrast; crop bottom 3/5")
    assert (provider / "thumbnail_brief.txt").read_text() == "max contrast; crop bottom 3/5"
