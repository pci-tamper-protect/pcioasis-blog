#!/usr/bin/env python3
"""Load multi-vendor AI credentials and build SDK clients.

Supports:
  - Azure OpenAI (OpenAI-compatible) via azure_openai_endpoint + api_key
  - Azure AI Foundry project endpoint (stored; use with Foundry SDK when wired)
  - Anthropic (api_key from env or same secret file)
  - Plain OpenAI (when only api_key is set and AZURE_OPENAI_ENDPOINT is empty)

Resolution order:
  1. Explicit path argument or AI_SECRET_FILE env
  2. Environment variables (OPENAI_API_KEY, AZURE_OPENAI_*, AI_*)
  3. macOS Keychain (pcioasis-blog/azure-ai-foundry) if `security` is available

Example:
    from deploy.secrets.load_ai_config import load_ai_config, create_openai_client

    cfg = load_ai_config()
    client = create_openai_client(cfg)  # AzureOpenAI or OpenAI
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DEFAULT_SECRET_FILE = Path("/tmp/ai")
KEYCHAIN_SERVICE_JSON = "pcioasis-blog/azure-ai-foundry"
KEYCHAIN_SERVICE_API_KEY = "pcioasis-blog/azure-ai-foundry-api-key"
DEFAULT_API_VERSION = "2024-10-21"


@dataclass(frozen=True)
class AIConfig:
    """Normalized AI credentials for multiple vendors."""

    api_key: str
    api_key_name: str = "default"
    project_endpoint: str = ""
    azure_openai_endpoint: str = ""
    source: str = "unknown"

    @property
    def vendor(self) -> Literal["azure_openai", "openai", "anthropic", "unknown"]:
        if self.azure_openai_endpoint:
            return "azure_openai"
        if self.api_key.startswith("sk-ant-"):
            return "anthropic"
        if self.api_key.startswith("sk-"):
            return "openai"
        return "unknown"

    def as_dict(self) -> dict[str, str]:
        return {
            "project_endpoint": self.project_endpoint,
            "azure_openai_endpoint": self.azure_openai_endpoint,
            "api_key": self.api_key,
            "api_key_name": self.api_key_name,
        }


def _parse_secret_payload(raw: str) -> AIConfig:
    raw = raw.strip()
    if not raw:
        raise ValueError("secret payload is empty")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return AIConfig(api_key=raw, source="bare_key")

    if isinstance(data, str):
        return AIConfig(api_key=data, source="bare_key")

    if not isinstance(data, dict):
        raise ValueError("secret JSON must be an object")

    api_key = str(data.get("api_key") or data.get("key") or "")
    if not api_key:
        raise ValueError('secret JSON must include "api_key"')

    return AIConfig(
        api_key=api_key,
        api_key_name=str(data.get("api_key_name") or "default"),
        project_endpoint=str(data.get("project_endpoint") or ""),
        azure_openai_endpoint=str(data.get("azure_openai_endpoint") or ""),
        source="json",
    )


def _read_file(path: Path) -> AIConfig:
    return _parse_secret_payload(path.read_text(encoding="utf-8"))


def _read_keychain(service: str, account: str) -> str | None:
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _from_env() -> AIConfig | None:
    api_key = (
        os.environ.get("AI_API_KEY")
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not api_key:
        return None
    return AIConfig(
        api_key=api_key,
        api_key_name=os.environ.get("AI_API_KEY_NAME", "default"),
        project_endpoint=os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "")
        or os.environ.get("AI_PROJECT_ENDPOINT", ""),
        azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        or os.environ.get("AI_AZURE_OPENAI_ENDPOINT", ""),
        source="environment",
    )


def load_ai_config(
    secret_file: Path | str | None = None,
    *,
    keychain_account: str | None = None,
    prefer_keychain: bool = False,
) -> AIConfig:
    """Load credentials from file, env, or macOS Keychain."""
    account = keychain_account or os.environ.get("KEYCHAIN_ACCOUNT", "default")

    if prefer_keychain:
        for service in (KEYCHAIN_SERVICE_JSON, KEYCHAIN_SERVICE_API_KEY):
            raw = _read_keychain(service, account)
            if raw:
                cfg = _parse_secret_payload(raw)
                return AIConfig(**{**cfg.__dict__, "source": f"keychain:{service}"})

    path = Path(secret_file or os.environ.get("AI_SECRET_FILE", DEFAULT_SECRET_FILE))
    if path.is_file():
        cfg = _read_file(path)
        return AIConfig(**{**cfg.__dict__, "source": f"file:{path}"})

    env_cfg = _from_env()
    if env_cfg:
        return env_cfg

    if not prefer_keychain:
        for service in (KEYCHAIN_SERVICE_JSON, KEYCHAIN_SERVICE_API_KEY):
            raw = _read_keychain(service, account)
            if raw:
                cfg = _parse_secret_payload(raw)
                return AIConfig(**{**cfg.__dict__, "source": f"keychain:{service}"})

    raise FileNotFoundError(
        "no AI credentials found; set AI_SECRET_FILE, env vars, or run bootstrap-macos-keychain.sh"
    )


def apply_to_environ(cfg: AIConfig) -> None:
    """Export standard env vars for shell scripts and third-party CLIs."""
    os.environ["AI_API_KEY"] = cfg.api_key
    os.environ["AI_API_KEY_NAME"] = cfg.api_key_name
    os.environ["OPENAI_API_KEY"] = cfg.api_key
    os.environ["AZURE_OPENAI_API_KEY"] = cfg.api_key
    if cfg.azure_openai_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = cfg.azure_openai_endpoint
        os.environ["AI_AZURE_OPENAI_ENDPOINT"] = cfg.azure_openai_endpoint
    if cfg.project_endpoint:
        os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"] = cfg.project_endpoint
        os.environ["AI_PROJECT_ENDPOINT"] = cfg.project_endpoint


def create_openai_client(cfg: AIConfig | None = None, **kwargs: Any) -> Any:
    """Return OpenAI or AzureOpenAI client based on config."""
    cfg = cfg or load_ai_config()
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError as exc:
        raise ImportError("uv sync --extra secrets (openai>=1.0)") from exc

    if cfg.azure_openai_endpoint:
        return AzureOpenAI(
            azure_endpoint=cfg.azure_openai_endpoint.rstrip("/"),
            api_key=cfg.api_key,
            api_version=kwargs.pop("api_version", os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)),
            **kwargs,
        )
    return OpenAI(api_key=cfg.api_key, **kwargs)


def create_anthropic_client(cfg: AIConfig | None = None, **kwargs: Any) -> Any:
    """Return Anthropic client; uses ANTHROPIC_API_KEY env if set, else config api_key."""
    cfg = cfg or load_ai_config()
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError("uv sync (anthropic)") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.api_key
    return anthropic.Anthropic(api_key=api_key, **kwargs)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Load and print AI config (no secrets on stdout by default)")
    parser.add_argument("--file", type=Path, help="Secret JSON file (default: AI_SECRET_FILE or /tmp/ai)")
    parser.add_argument("--show-key", action="store_true", help="Print api_key (careful)")
    parser.add_argument("--export-shell", action="store_true", help="Print export statements for bash")
    parser.add_argument("--prefer-keychain", action="store_true")
    args = parser.parse_args()

    cfg = load_ai_config(args.file, prefer_keychain=args.prefer_keychain)

    if args.export_shell:
        apply_to_environ(cfg)
        for key in (
            "AI_API_KEY",
            "AI_API_KEY_NAME",
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
        ):
            val = os.environ.get(key)
            if val:
                print(f'export {key}={json.dumps(val)}')
        return

    info = {
        "source": cfg.source,
        "vendor": cfg.vendor,
        "api_key_name": cfg.api_key_name,
        "project_endpoint": cfg.project_endpoint,
        "azure_openai_endpoint": cfg.azure_openai_endpoint,
        "api_key_set": bool(cfg.api_key),
    }
    if args.show_key:
        info["api_key"] = cfg.api_key
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
