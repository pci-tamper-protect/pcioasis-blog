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
DEFAULT_SORA_SECRET_FILE = Path("/tmp/sora.json")
KEYCHAIN_SERVICE_JSON = "pcioasis-blog/azure-ai-foundry"
KEYCHAIN_SERVICE_SORA_JSON = "pcioasis-blog/azure-ai-foundry-sora2"
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

    data = normalize_sora_secret_fields(data)

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


def normalize_sora_secret_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Accept portal-friendly aliases (target_url, model_name) for Sora secrets."""
    out = dict(data)
    target = (
        out.get("target_url")
        or out.get("target_uri")
        or out.get("project_endpoint")
        or ""
    )
    if target and not out.get("azure_openai_endpoint"):
        out["azure_openai_endpoint"] = foundry_services_url_to_openai_v1(str(target))
    if target and not out.get("project_endpoint"):
        out["project_endpoint"] = str(target).rstrip("/")
    if out.get("model_name") and not out.get("deployment_name"):
        out["deployment_name"] = out["model_name"]
    if out.get("subscription") and not out.get("api_key_name"):
        out["api_key_name"] = out["subscription"]
    return out


def foundry_services_url_to_openai_v1(url: str) -> str:
    """Map …services.ai.azure.com base URL to OpenAI v1 surface for video/chat SDK."""
    host = url.strip().rstrip("/").replace("https://", "").split("/")[0]
    resource = host.replace(".services.ai.azure.com", "").replace(
        ".cognitiveservices.azure.com", ""
    )
    if not resource or resource == host:
        ep = url.strip().rstrip("/")
        if ep.endswith("/openai/v1"):
            return ep
        return ep
    return f"https://{resource}.openai.azure.com/openai/v1"


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


def _mask_api_key(key: str) -> str:
    """Return a non-reversible preview safe for logs and JSON stdout."""
    if not key:
        return ""
    if len(key) <= 8:
        return "(set)"
    return f"{key[:4]}…{key[-4:]}"


def normalize_azure_endpoint(endpoint: str) -> tuple[str, bool]:
    """Return (endpoint_for_client, use_openai_v1_client). Matches ai_backend.py."""
    ep = endpoint.strip().rstrip("/")
    if ep.endswith("/openai/v1"):
        return f"{ep}/", True
    for suffix in ("/openai/v1", "/openai"):
        if ep.endswith(suffix):
            ep = ep[: -len(suffix)]
    return ep.rstrip("/") + "/", False


def apply_sora_to_environ(cfg: AIConfig, raw: dict[str, Any] | None = None) -> None:
    """Export AZURE_SORA_* vars without overwriting chat LLM env (crawl-ptp-prd /tmp/ai)."""
    data = raw or {}
    deployment = str(
        data.get("deployment_name")
        or data.get("model_name")
        or os.environ.get("AZURE_SORA_DEPLOYMENT", "sora-2")
    )
    os.environ["AZURE_SORA_API_KEY"] = cfg.api_key
    if cfg.azure_openai_endpoint:
        os.environ["AZURE_SORA_ENDPOINT"] = cfg.azure_openai_endpoint
    if cfg.project_endpoint:
        os.environ["AZURE_SORA_PROJECT_ENDPOINT"] = cfg.project_endpoint
    os.environ["AZURE_SORA_DEPLOYMENT"] = deployment
    os.environ["AZURE_SORA_MODEL"] = deployment


def load_sora_config(
    secret_file: Path | str | None = None,
    *,
    prefer_keychain: bool = False,
) -> tuple[AIConfig, dict[str, Any]]:
    """Load Sora-only Foundry creds (separate subscription/resource from chat)."""
    path = Path(
        secret_file
        or os.environ.get("AZURE_SORA_SECRET_FILE")
        or os.environ.get("AI_SORA_SECRET_FILE")
        or DEFAULT_SORA_SECRET_FILE
    )

    if prefer_keychain:
        raw = _read_keychain(KEYCHAIN_SERVICE_SORA_JSON, os.environ.get("KEYCHAIN_ACCOUNT", "default"))
        if raw:
            data = json.loads(raw) if raw.strip().startswith("{") else {"api_key": raw}
            data = normalize_sora_secret_fields(data if isinstance(data, dict) else {})
            cfg = _parse_secret_payload(raw)
            return AIConfig(**{**cfg.__dict__, "source": f"keychain:{KEYCHAIN_SERVICE_SORA_JSON}"}), data

    if path.is_file():
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text) if raw_text.strip().startswith("{") else {}
        if isinstance(data, dict):
            data = normalize_sora_secret_fields(data)
        cfg = _read_file(path)
        return AIConfig(**{**cfg.__dict__, "source": f"file:{path}"}), data if isinstance(data, dict) else {}

    raise FileNotFoundError(
        f"no Sora credentials at {path}; create /tmp/sora.json or set AZURE_SORA_SECRET_FILE"
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
        raise ImportError(
            "openai package required; run: uv sync --project agents/content-pipeline"
        ) from exc

    if cfg.azure_openai_endpoint:
        client_endpoint, use_v1 = normalize_azure_endpoint(cfg.azure_openai_endpoint)
        if use_v1:
            return OpenAI(base_url=client_endpoint, api_key=cfg.api_key, **kwargs)
        return AzureOpenAI(
            azure_endpoint=client_endpoint,
            api_key=cfg.api_key,
            api_version=kwargs.pop(
                "api_version",
                os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION),
            ),
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
    parser.add_argument(
        "--show-key-mask",
        action="store_true",
        help="Include masked api_key preview in JSON (never prints the full key)",
    )
    parser.add_argument(
        "--export-shell",
        action="store_true",
        help="Print export statements for bash (writes secrets to stdout; pipe to eval only)",
    )
    parser.add_argument("--prefer-keychain", action="store_true")
    parser.add_argument(
        "--sora",
        action="store_true",
        help="Load Sora/video Foundry secret (/tmp/sora.json or AZURE_SORA_SECRET_FILE)",
    )
    args = parser.parse_args()

    if args.sora:
        cfg, raw = load_sora_config(args.file, prefer_keychain=args.prefer_keychain)
        if args.export_shell:
            apply_sora_to_environ(cfg, raw)
            for key in (
                "AZURE_SORA_API_KEY",
                "AZURE_SORA_ENDPOINT",
                "AZURE_SORA_PROJECT_ENDPOINT",
                "AZURE_SORA_DEPLOYMENT",
                "AZURE_SORA_MODEL",
            ):
                val = os.environ.get(key)
                if val:
                    print(f"export {key}={json.dumps(val)}")
            return
        info = {
            "source": cfg.source,
            "azure_openai_endpoint": cfg.azure_openai_endpoint,
            "project_endpoint": cfg.project_endpoint,
            "deployment": raw.get("deployment_name") or raw.get("model_name") or "sora-2",
            "api_key_set": bool(cfg.api_key),
        }
        if args.show_key_mask:
            info["api_key_mask"] = _mask_api_key(cfg.api_key)
        print(json.dumps(info, indent=2))
        return

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
                # codeql[py/clear-text-logging-sensitive-data]: intentional for local eval "$(...)"
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
    if args.show_key_mask:
        info["api_key_mask"] = _mask_api_key(cfg.api_key)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
