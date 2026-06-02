"""Tests for ai_backend credential resolution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_backend import (  # noqa: E402
    _anthropic_config,
    _azure_config,
    _merge_secret_file_into_env,
    _openai_config,
    resolve_backend,
)


class TestBackendResolution:
    def test_prefers_anthropic_when_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
        monkeypatch.setenv("AI_API_KEY", "azure-key")
        cfg = resolve_backend()
        assert cfg.name == "anthropic"

    def test_azure_when_anthropic_env_is_azure_key(self, monkeypatch):
        """Stale ANTHROPIC_API_KEY from keychain export must not force Anthropic."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "azure-foundry-key-not-sk-ant")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
        monkeypatch.setenv("AI_API_KEY", "azure-foundry-key-not-sk-ant")
        cfg = resolve_backend()
        assert cfg.name == "azure_openai"

    def test_azure_when_no_anthropic(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
        monkeypatch.setenv("AI_API_KEY", "azure-key")
        cfg = resolve_backend()
        assert cfg.name == "azure_openai"
        assert cfg.azure_endpoint.startswith("https://")

    def test_openai_plain_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        cfg = resolve_backend()
        assert cfg.name == "openai"

    def test_forced_backend(self, monkeypatch):
        monkeypatch.setenv("CONTENT_PIPELINE_LLM_BACKEND", "azure_openai")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
        monkeypatch.setenv("OPENAI_API_KEY", "key")
        cfg = resolve_backend()
        assert cfg.name == "azure_openai"

    def test_secret_file_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        secret = tmp_path / "ai.json"
        secret.write_text(
            json.dumps(
                {
                    "azure_openai_endpoint": "https://x.openai.azure.com/",
                    "api_key": "foundry-key",
                    "api_key_name": "test",
                }
            )
        )
        monkeypatch.setenv("AI_SECRET_FILE", str(secret))
        cfg = resolve_backend()
        assert cfg.name == "azure_openai"
        assert "foundry-key" == cfg.api_key

    def test_exits_when_no_credentials(self, monkeypatch):
        monkeypatch.setenv("CONTENT_PIPELINE_SKIP_SECRET_FILE", "1")
        for key in (
            "ANTHROPIC_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AI_AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AI_API_KEY",
            "OPENAI_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        with pytest.raises(SystemExit):
            resolve_backend()


class TestHelpers:
    def test_merge_secret_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        secret = tmp_path / "ai"
        secret.write_text(
            json.dumps(
                {
                    "azure_openai_endpoint": "https://a.openai.azure.com/",
                    "api_key": "k",
                }
            )
        )
        monkeypatch.setenv("AI_SECRET_FILE", str(secret))
        _merge_secret_file_into_env()
        assert _azure_config("test") is not None
        assert not _anthropic_config("test")
