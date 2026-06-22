"""Tests for deploy/secrets/load_ai_config.py (imported via repo root)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from deploy.secrets.load_ai_config import (  # noqa: E402
    _parse_secret_payload,
    foundry_services_url_to_openai_v1,
    load_sora_config,
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
        assert cfg.azure_openai_endpoint == "https://mgmt.openai.azure.com/openai/v1"
        assert cfg.api_key_name == "management-ptp-global"


class TestLoadSoraConfig:
    def test_load_from_file(self, tmp_path):
        sora_file = tmp_path / "sora.json"
        sora_file.write_text(
            json.dumps({
                "target_url": "https://my-resource.services.ai.azure.com",
                "api_key": "test-key-abc",
                "model_name": "sora-2",
            }),
            encoding="utf-8",
        )
        cfg, data = load_sora_config(sora_file)
        assert cfg.api_key == "test-key-abc"
        assert cfg.azure_openai_endpoint == "https://my-resource.openai.azure.com/openai/v1"
        assert data.get("deployment_name") == "sora-2"

    def test_missing_file_raises(self, tmp_path):
        import pytest
        with pytest.raises(FileNotFoundError, match="no Sora credentials"):
            load_sora_config(tmp_path / "nonexistent.json")
