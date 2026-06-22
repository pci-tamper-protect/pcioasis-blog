"""Tests for ffmpeg final-pass combine assessment."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.final_pass_combine import assess_combine_brief  # noqa: E402


def test_brief_sora_veo_sequential_is_ffmpeg_feasible():
    brief = (
        "Use the phone chat image from sora2 and the image animation from veo. "
        "The voice can be from either"
    )
    a = assess_combine_brief(brief)
    assert a.ffmpeg_feasible
    assert a.mode == "concat_xfade"
    assert not a.llm_regen_recommended


def test_sora_filter_chain_applies_crop_from_brief():
    from video_arena.final_pass_combine import _sora_video_filter_chain

    brief = "Poster: crop away bottom 3/5; dewarp phone UI to straight-on."
    chain = _sora_video_filter_chain(brief, "azure_sora")
    assert "crop=iw:ih*2/5" in chain
    assert "perspective=" in chain


def test_brief_same_frame_needs_generative():
    a = assess_combine_brief("Put both in the same frame at the same time with new dialogue")
    assert not a.ffmpeg_feasible
    assert a.llm_regen_recommended
    assert a.suggested_models
