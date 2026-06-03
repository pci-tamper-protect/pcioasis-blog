"""Tests for shared arena prompt load/save."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.prompt_store import load_prompt_text, save_arena_prompt  # noqa: E402
from video_arena.review import build_review_html  # noqa: E402


def test_save_updates_prompt_txt_and_manifest(tmp_path):
    arena = tmp_path / "video-arena"
    arena.mkdir()
    (arena / "manifest.json").write_text(
        json.dumps({"title": "T", "prompt": "old", "providers": {}}),
        encoding="utf-8",
    )
    save_arena_prompt(arena, "new shared prompt")
    assert (arena / "prompt.txt").read_text().strip() == "new shared prompt"
    data = json.loads((arena / "manifest.json").read_text())
    assert data["prompt"] == "new shared prompt"
    assert data.get("prompt_updated_at")


def test_load_prefers_prompt_txt(tmp_path):
    arena = tmp_path / "video-arena"
    arena.mkdir()
    (arena / "prompt.txt").write_text("from file\n", encoding="utf-8")
    assert load_prompt_text(arena, {"prompt": "from manifest"}) == "from file"


def test_review_html_has_editable_prompt(tmp_path):
    arena = tmp_path / "video-arena"
    arena.mkdir()
    (arena / "prompt.txt").write_text("Edit me\n", encoding="utf-8")
    manifest = {"title": "T", "prompt": "Edit me", "providers": {}}
    html = build_review_html(arena, manifest, api_base="/arena")
    assert 'id="shared-prompt-text"' in html
    assert "Edit me" in html
    assert "save-prompt" in html
    assert "Save prompt" in html
