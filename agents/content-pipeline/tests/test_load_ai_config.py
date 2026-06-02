"""Tests for deploy/secrets/load_ai_config.py (imported via repo root)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from deploy.secrets.load_ai_config import (  # noqa: E402
    _parse_secret_payload,
    normalize_azure_endpoint,
)


class TestParseSecretPayload:
    def test_bare_api_key(self):
        cfg = _parse_secret_payload("sk-test-bare-key")
        assert cfg.api_key == "sk-test-bare-key"
        assert cfg.source == "bare_key"

    def test_json_object(self):
        cfg = _parse_secret_payload(
            '{"api_key": "k", "azure_openai_endpoint": "https://x.openai.azure.com/"}'
        )
        assert cfg.api_key == "k"
        assert cfg.azure_openai_endpoint.startswith("https://")


class TestNormalizeAzureEndpoint:
    def test_foundry_v1(self):
        url, v1 = normalize_azure_endpoint("https://r.openai.azure.com/openai/v1")
        assert v1 is True
        assert url.endswith("/openai/v1/")
