"""Tests for generate_variants.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_variants import (  # noqa: E402
    PLATFORM_SPECS,
    build_messages,
    generate_variants,
    parse_frontmatter,
)

# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\ntitle: Hello\nslug: hello\n---\nBody text"
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Hello"
        assert meta["slug"] == "hello"
        assert body == "Body text"

    def test_no_frontmatter(self):
        text = "Just body text"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == "Just body text"

    def test_empty_frontmatter(self):
        text = "---\n---\nBody"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == "Body"

    def test_missing_closing_delimiter(self):
        text = "---\ntitle: Broken"
        meta, body = parse_frontmatter(text)
        assert meta == {}

    def test_frontmatter_with_list(self):
        text = "---\ntags:\n  - pci\n  - tls\n---\nContent"
        meta, body = parse_frontmatter(text)
        assert meta["tags"] == ["pci", "tls"]


# ---------------------------------------------------------------------------
# PLATFORM_SPECS completeness
# ---------------------------------------------------------------------------


class TestPlatformSpecs:
    EXPECTED_KEYS = {
        "planetkesten",
        "kbroughton",
        "linkedin",
        "bluesky",
        "mastodon",
        "pixelfed",
        "clapper",
        "twitter_xref",
        "tiktok_xref",
        "douyin_xref",
        "rednote_xref",
        "youtube_shorts",
        "reels_xref",
        "youtube_script",
        "youtube_description",
        "youtube_chapters",
    }

    def test_all_platforms_present(self):
        assert set(PLATFORM_SPECS.keys()) == self.EXPECTED_KEYS

    def test_bluesky_mentions_char_limit(self):
        assert "300" in PLATFORM_SPECS["bluesky"]

    def test_mastodon_mentions_cw(self):
        spec = PLATFORM_SPECS["mastodon"]
        assert (
            "CW" in spec
            or "Content Warning" in spec.lower()
            or "content warning" in spec.lower()
        )

    def test_mastodon_mentions_infosec_exchange(self):
        assert "infosec.exchange" in PLATFORM_SPECS["mastodon"]

    def test_clapper_mentions_texas(self):
        spec = PLATFORM_SPECS["clapper"].lower()
        assert (
            "texas" in spec or "tx" in spec or "us-first" in spec or "domestic" in spec
        )

    def test_twitter_xref_has_placeholder(self):
        assert "[BLUESKY_URL]" in PLATFORM_SPECS["twitter_xref"]

    def test_tiktok_xref_has_placeholder(self):
        assert "[CLAPPER_URL]" in PLATFORM_SPECS["tiktok_xref"]

    def test_douyin_xref_has_placeholder(self):
        assert "[CLAPPER_URL]" in PLATFORM_SPECS["douyin_xref"]

    def test_rednote_xref_has_placeholder(self):
        assert "[CLAPPER_URL]" in PLATFORM_SPECS["rednote_xref"]

    def test_youtube_shorts_has_placeholder(self):
        assert "[CLAPPER_URL]" in PLATFORM_SPECS["youtube_shorts"]

    def test_reels_xref_has_placeholder(self):
        assert "[CLAPPER_URL]" in PLATFORM_SPECS["reels_xref"]

    def test_clapper_is_labeled_primary(self):
        spec = PLATFORM_SPECS["clapper"].lower()
        assert "primary" in spec or "us-first" in spec or "texas" in spec

    def test_youtube_script_mentions_sections(self):
        assert "INTRO" in PLATFORM_SPECS["youtube_script"]

    def test_youtube_chapters_mentions_timestamp(self):
        assert (
            "MM:SS" in PLATFORM_SPECS["youtube_chapters"]
            or "00:00" in PLATFORM_SPECS["youtube_chapters"]
        )


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_returns_user_message(self):
        messages, system = build_messages(
            "Source text", "Write a post.", "https://example.com/post/"
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_source_has_cache_control(self):
        messages, _ = build_messages("Source", "Spec", "https://example.com/")
        content = messages[0]["content"]
        cached = [c for c in content if c.get("cache_control")]
        assert len(cached) == 1

    def test_canonical_url_in_cached_block(self):
        url = "https://blog.pcioasis.com/posts/zktls/zktls-proof-of-provenance/"
        messages, _ = build_messages("Source", "Spec", url)
        cached_text = messages[0]["content"][0]["text"]
        assert url in cached_text

    def test_system_prompt_mentions_pci(self):
        _, system = build_messages("Source", "Spec", "https://example.com/")
        assert "PCI" in system

    def test_spec_in_second_content_block(self):
        spec = "Write a LinkedIn post."
        messages, _ = build_messages("Source", spec, "https://example.com/")
        task_block = messages[0]["content"][1]
        assert spec in task_block["text"]


# ---------------------------------------------------------------------------
# generate_variants (integration, mocked API)
# ---------------------------------------------------------------------------

SAMPLE_POST = """\
---
title: zkTLS Proof of Provenance
slug: zktls-proof-of-provenance
date: 2026-05-09
tags:
  - zktls
  - pci
section: zkTLS
---
# zkTLS Proof of Provenance

zkTLS lets you prove a TLS session happened without revealing credentials.
"""


def make_fake_client(response_text: str = "Generated content"):
    """Return a mock Anthropic client that returns a fixed response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]

    mock_messages = MagicMock()
    mock_messages.create.return_value = mock_response

    mock_client = MagicMock()
    mock_client.messages = mock_messages
    return mock_client


class TestGenerateVariants:
    def _write_post(self, tmp_path: Path) -> Path:
        post_dir = (
            tmp_path / "content" / "posts" / "zkTLS" / "zktls-proof-of-provenance"
        )
        post_dir.mkdir(parents=True)
        (post_dir / "index.md").write_text(SAMPLE_POST)
        return post_dir

    def test_creates_variants_dir(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("Hello world")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        assert (post_dir / "_variants").is_dir()

    def test_creates_youtube_subdir(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("content")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        assert (post_dir / "_variants" / "youtube").is_dir()

    def test_all_variant_files_created(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("Generated text")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)

        variants_dir = post_dir / "_variants"
        expected = [
            "planetkesten.md",
            "kbroughton.md",
            "linkedin.md",
            "bluesky.txt",
            "mastodon.txt",
            "pixelfed.txt",
            "clapper.txt",
            "tiktok-xref.txt",
            "douyin-xref.txt",
            "rednote-xref.txt",
            "youtube-shorts.txt",
            "reels-xref.txt",
            "twitter-xref.txt",
            "youtube/script.md",
            "youtube/description.md",
            "youtube/chapters.txt",
        ]
        for rel in expected:
            assert (variants_dir / rel).exists(), f"Missing: {rel}"

    def test_manifest_written(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("content")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        manifest_path = post_dir / "_variants" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["slug"] == "zktls-proof-of-provenance"
        assert "canonical" in manifest

    def test_canonical_url_derived_from_section(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("content")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        manifest = json.loads((post_dir / "_variants" / "manifest.json").read_text())
        # section = parent dir name = "zkTLS" -> lowercased in URL
        assert "zktls" in manifest["canonical"].lower()

    def test_dry_run_no_files_written(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("content")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir, dry_run=True)
        assert not (post_dir / "_variants").exists()

    def test_api_called_for_each_variant(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("content")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        # 16 variants expected
        assert fake_client.messages.create.call_count == 16

    def test_missing_api_key_exits(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        with patch.dict("os.environ", {}, clear=True):
            # ANTHROPIC_API_KEY not set
            with pytest.raises(SystemExit):
                generate_variants(post_dir)

    def test_missing_index_md_exits(self, tmp_path):
        post_dir = tmp_path / "empty-post"
        post_dir.mkdir()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            with pytest.raises(SystemExit):
                generate_variants(post_dir)

    def test_variant_content_written_verbatim(self, tmp_path):
        post_dir = self._write_post(tmp_path)
        fake_client = make_fake_client("EXACT OUTPUT TEXT")
        with patch(
            "generate_variants.anthropic.Anthropic", return_value=fake_client
        ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            generate_variants(post_dir)
        bluesky = (post_dir / "_variants" / "bluesky.txt").read_text()
        assert "EXACT OUTPUT TEXT" in bluesky
