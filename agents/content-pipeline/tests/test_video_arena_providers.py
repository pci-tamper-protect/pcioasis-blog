"""Tests for video arena provider registry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from video_arena.providers import PROVIDERS, all_providers  # noqa: E402


class TestVideoArenaProviders:
    EXPECTED = (
        "azure_sora",
        "azure_sora_v1",
        "vertex_veo",
        "bedrock_luma",
        "replicate_hailuo",
    )

    def test_all_providers_registered(self):
        all_providers()
        assert tuple(p.provider_id for p in all_providers()) == self.EXPECTED

    def test_azure_sora_v1_is_text_only_on_foundry(self):
        from video_arena.providers.azure_sora_v1 import AzureSoraV1Provider

        provider = AzureSoraV1Provider()
        assert provider.provider_id == "azure_sora_v1"
        assert provider.default_model == "sora"
        assert "AZURE_SORA_V1_DEPLOYMENT" in provider.missing_config_help()

    def test_provider_ids_unique(self):
        all_providers()
        ids = [p.provider_id for p in all_providers()]
        assert len(ids) == len(set(ids))
        assert set(ids) == set(PROVIDERS.keys()) == set(self.EXPECTED)
