"""Tests for video arena review HTML."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.review import build_review_html, load_arena_manifest  # noqa: E402


class TestBuildReviewHtml:
    def test_renders_provider_with_custom_video_href(self, tmp_path):
        arena = tmp_path / "video-arena"
        provider_dir = arena / "azure_sora"
        provider_dir.mkdir(parents=True)
        (provider_dir / "video.mp4").write_bytes(b"fake-mp4")

        manifest = {
            "title": "Test Post",
            "prompt": "Vertical 9:16 explainer",
            "providers": {
                "azure_sora": {
                    "display_name": "Azure Sora 2",
                    "status": "ok",
                    "message": "done",
                }
            },
        }
        html = build_review_html(
            arena,
            manifest,
            href_for=lambda pid: f"/arena/{pid}/video.mp4",
            back_href="/",
        )
        assert "/arena/azure_sora/video.mp4" in html
        assert "← Back to variants" in html
        assert "Vertical 9:16 explainer" in html

    def test_provider_card_splits_video_and_thumbnail_actions(self, tmp_path):
        arena = tmp_path / "video-arena"
        provider_dir = arena / "azure_sora"
        provider_dir.mkdir(parents=True)
        (provider_dir / "video.mp4").write_bytes(b"fake-mp4")

        manifest = {
            "title": "T",
            "prompt": "p",
            "providers": {
                "azure_sora": {
                    "display_name": "Azure Sora 2",
                    "status": "ok",
                    "message": "done",
                }
            },
        }
        html = build_review_html(
            arena,
            manifest,
            href_for=lambda pid: f"/arena/{pid}/video.mp4",
            api_base="/arena",
        )
        assert "Regenerate video" in html
        assert "provider-field-video" in html
        assert "provider-field-thumbs" in html
        assert "provider-video-brief" in html
        assert "provider-thumb-brief" in html
        assert "btn-regenerate-video" in html
        assert 'data-role="video-regen-status"' in html
        assert "Regenerate thumbnails" in html
        assert "btn-regenerate-thumbnails" in html
        assert 'data-role="thumb-regen-status"' in html
        assert "regenerate-thumbnails" in html
        assert "setJobStatus" in html

    def test_load_manifest_missing_returns_none(self, tmp_path):
        assert load_arena_manifest(tmp_path / "missing") is None

    def test_shows_winner_when_present(self, tmp_path):
        arena = tmp_path / "video-arena"
        arena.mkdir()
        (arena / "WINNER.txt").write_text("vertex_veo — best motion\n")
        manifest = {"title": "T", "prompt": "p", "providers": {}}
        html = build_review_html(arena, manifest)
        assert "vertex_veo" in html
        assert "Current winner" in html
