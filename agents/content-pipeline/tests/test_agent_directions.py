"""Tests for video arena agent directions and direct tool mapping."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.agent_directions import (  # noqa: E402
    execute_tool,
    get_role_spec,
    load_arena_agent_context_extended,
    try_direct_tools,
)


def test_role_spec_includes_tool_catalog():
    spec = get_role_spec("orchestrator")
    assert "ffmpeg_combine" in spec
    assert "azure_sora" in spec


def test_try_direct_thumbnails_sora(tmp_path):
    arena = tmp_path / "video-arena"
    (arena / "azure_sora").mkdir(parents=True)
    steps = try_direct_tools("Regenerate thumbnails for sora2", tmp_path, arena)
    assert steps is not None
    assert steps[0].id == "regenerate_provider_thumbnails"
    assert steps[0].args["provider_id"] == "azure_sora"


def test_try_direct_final_pass(tmp_path):
    arena = tmp_path / "video-arena"
    arena.mkdir()
    brief = "Use phone from sora and animation from veo"
    steps = try_direct_tools(f"final pass combine: {brief}", tmp_path, arena)
    assert steps is not None
    assert any(s.id == "run_final_pass" for s in steps)


def test_save_brief_tool(tmp_path):
    arena = tmp_path / "video-arena"
    arena.mkdir()
    execute_tool(
        "save_final_pass_brief",
        tmp_path,
        arena,
        {"brief": "Test brief\n"},
    )
    assert (arena / "final_pass_brief.txt").read_text() == "Test brief\n"


def test_extended_context_paths(tmp_path):
    post = tmp_path / "post"
    arena = post / "_variants" / "video-arena"
    arena.mkdir(parents=True)
    (arena / "prompt.txt").write_text("p", encoding="utf-8")
    ctx = load_arena_agent_context_extended(post, arena)
    assert ctx["post_dir"] == str(post.resolve())
    assert "tool_catalog" in ctx
