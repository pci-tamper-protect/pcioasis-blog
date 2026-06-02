"""Tests for platform_specs.py — per-channel format contracts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from platform_specs import (  # noqa: E402
    BLUESKY_TARGET_MAX,
    BLUESKY_TARGET_MIN,
    PLATFORM_SPECS,
)


class TestPlatformSpecsContracts:
    def test_linkedin_krebs_link_format(self):
        spec = PLATFORM_SPECS["linkedin"]
        assert "From the post:" in spec
        assert "100–180" in spec or "100-180" in spec
        assert "FORBIDDEN" in spec
        assert "Brian Krebs" in spec or "Krebs" in spec

    def test_bluesky_sweet_spot_documented(self):
        spec = PLATFORM_SPECS["bluesky"]
        assert str(BLUESKY_TARGET_MIN) in spec
        assert str(BLUESKY_TARGET_MAX) in spec
        assert "300" in spec

    def test_mastodon_cw_hashtags_in_warning_line(self):
        spec = PLATFORM_SPECS["mastodon"]
        assert "CW:" in spec
        assert "hashtags" in spec.lower()
        assert "infosec.exchange" in spec

    def test_clapper_parsed_prefixes(self):
        spec = PLATFORM_SPECS["clapper"]
        assert "HOOK:" in spec
        assert "TALK:" in spec
        assert "CAPTION:" in spec

    def test_youtube_shorts_three_lines(self):
        spec = PLATFORM_SPECS["youtube_shorts"]
        assert "CAPTION:" in spec
        assert "OVERLAY:" in spec
        assert "#Shorts" in spec

    def test_all_specs_include_preamble(self):
        for key, spec in PLATFORM_SPECS.items():
            assert "CHANNEL:" in spec, key
            assert "Do NOT imitate" in spec or "not his voice" in spec.lower(), key
