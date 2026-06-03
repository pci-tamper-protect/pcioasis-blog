"""Tests for deploy/secrets/load_ai_config.py (imported via repo root)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from deploy.secrets.load_ai_config import (  # noqa: E402
    _parse_secret_payload,
    foundry_services_url_to_openai_v1,
    normalize_azure_endpoint,
    normalize_sora_secret_fields,
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


class TestSoraSecretNormalization:
    def test_target_url_to_openai_v1(self):
        url = foundry_services_url_to_openai_v1(
            "https://management-ptp-global-resource.services.ai.azure.com"
        )
        assert url == "https://management-ptp-global-resource.openai.azure.com/openai/v1"

    def test_portal_style_json(self):
        raw = """{
          "target_url": "https://mgmt.services.ai.azure.com",
          "api_key": "azure-key",
          "model_name": "sora-2",
          "subscription": "management-ptp-global"
        }"""
        cfg = _parse_secret_payload(raw)
        assert cfg.azure_openai_endpoint.endswith("/openai/v1")
        assert cfg.api_key_name == "management-ptp-global"
