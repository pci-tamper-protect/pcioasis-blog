"""Tests for Azure endpoint normalization."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_backend import normalize_azure_endpoint  # noqa: E402


class TestNormalizeAzureEndpoint:
    def test_foundry_v1_path(self):
        url, v1 = normalize_azure_endpoint(
            "https://resource.openai.azure.com/openai/v1"
        )
        assert v1 is True
        assert url == "https://resource.openai.azure.com/openai/v1/"

    def test_classic_resource_root(self):
        url, v1 = normalize_azure_endpoint("https://resource.openai.azure.com/")
        assert v1 is False
        assert url == "https://resource.openai.azure.com/"

    def test_strips_openai_suffix_for_classic_sdk(self):
        url, v1 = normalize_azure_endpoint(
            "https://resource.openai.azure.com/openai"
        )
        assert v1 is False
        assert url == "https://resource.openai.azure.com/"
