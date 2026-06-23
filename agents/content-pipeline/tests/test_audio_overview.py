"""Tests for Gemini audio overview pipeline (no API calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_overview.pipeline import (  # noqa: E402
    build_script_prompt,
    normalize_script,
    parse_frontmatter,
    tts_prompt_from_script,
)


def test_parse_frontmatter():
    text = "---\ntitle: Hello\n---\n\nBody here.\n"
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "Hello"
    assert "Body here" in body


def test_normalize_script_adds_speakers():
    raw = "First line\nSecond line"
    out = normalize_script(raw)
    assert out.startswith("Alex: First line")
    assert "Sam: Second line" in out


def test_normalize_script_preserves_labels():
    raw = "Alex: Hi\nSam: Hello"
    out = normalize_script(raw)
    assert "Alex: Hi" in out
    assert "Sam: Hello" in out


def test_tts_prompt_includes_both_hosts():
    script = "Alex: One\nSam: Two"
    prompt = tts_prompt_from_script(script)
    assert "Alex" in prompt and "Sam" in prompt
    assert script in prompt


def test_build_script_prompt_includes_title():
    system, user = build_script_prompt("My Post", "content", minutes=3)
    assert "3" in system
    assert "My Post" in user
    assert "content" in user
