"""Tests for video arena prompt builder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.prompt_builder import build_video_prompt, parse_clapper_variant  # noqa: E402


SAMPLE_CLAPPER = """\
HOOK: Can you trust this TLS proof?

TALK:
- TLS hides data between two parties
- zkTLS proves facts to a third party

CAPTION: Short explainer on zkTLS for compliance teams.

https://blog.pcioasis.com/posts/zktls/zktls-proof-of-provenance/
"""


class TestParseClapper:
    def test_parses_hook_talk_caption(self):
        parsed = parse_clapper_variant(SAMPLE_CLAPPER)
        assert "trust" in parsed["hook"]
        assert len(parsed["talk"]) == 2
        assert "compliance" in parsed["caption"]


class TestBuildVideoPrompt:
    def test_builds_from_clapper_file(self, tmp_path):
        post = tmp_path / "post"
        post.mkdir()
        (post / "index.md").write_text("---\ntitle: Test\n---\n")
        variants = post / "_variants"
        variants.mkdir()
        (variants / "clapper.txt").write_text(SAMPLE_CLAPPER)
        (post / "diagram.png").write_bytes(b"png")

        prompt, ref = build_video_prompt(post, title="Test Post")
        assert "9:16" in prompt
        assert "trust" in prompt.lower() or "TLS" in prompt
        assert ref is not None
        assert ref.name == "diagram.png"
