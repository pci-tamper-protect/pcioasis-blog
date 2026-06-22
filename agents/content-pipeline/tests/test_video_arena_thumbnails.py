"""Tests for video arena thumbnail extraction and review UI."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.review import build_review_html  # noqa: E402
from video_arena.thumbnails import (  # noqa: E402
    apply_thumbnail_selection,
    extract_thumbnail_candidates,
)

FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


class TestThumbnailReviewHtml:
    def test_renders_thumbnail_picker(self, tmp_path):
        arena = tmp_path / "video-arena"
        sub = arena / "vertex_veo"
        (sub / "thumbnails").mkdir(parents=True)
        (sub / "video.mp4").write_bytes(b"x")
        (sub / "thumbnails" / "first_non_black.jpg").write_bytes(b"jpeg")
        (sub / "thumbnails.json").write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "id": "first_non_black",
                            "label": "First non-black",
                            "file": "thumbnails/first_non_black.jpg",
                            "detail": "at 0.15s",
                        }
                    ],
                    "selected": None,
                }
            ),
            encoding="utf-8",
        )
        manifest = {
            "title": "T",
            "prompt": "p",
            "providers": {
                "vertex_veo": {
                    "display_name": "Veo",
                    "status": "ok",
                    "message": "ok",
                }
            },
        }
        html = build_review_html(
            arena,
            manifest,
            href_for=lambda pid: f"/arena/{pid}/video.mp4",
            thumb_href_for=lambda pid, rel: f"/arena/{pid}/{rel}",
            api_base="/arena",
        )
        assert "thumb-picker" in html
        assert "First non-black" in html
        assert "/arena/vertex_veo/thumbnails/first_non_black.jpg" in html
        assert "select-thumbnail" in html


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
class TestExtractThumbnails:
    def test_apply_selection(self, tmp_path):
        thumb = tmp_path / "thumbnails" / "max_contrast.jpg"
        thumb.parent.mkdir(parents=True)
        thumb.write_bytes(b"fake")
        (tmp_path / "thumbnails.json").write_text(
            json.dumps(
                {
                    "candidates": [
                        {
                            "id": "max_contrast",
                            "label": "Highest contrast",
                            "file": "thumbnails/max_contrast.jpg",
                        }
                    ],
                    "selected": None,
                }
            ),
            encoding="utf-8",
        )
        poster = apply_thumbnail_selection(tmp_path, "max_contrast")
        assert poster.is_file()
        assert (tmp_path / "THUMBNAIL.txt").read_text().strip() == "max_contrast"
