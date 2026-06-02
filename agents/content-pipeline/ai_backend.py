"""Resolve LLM credentials and complete variant prompts (multi-vendor).

Backend priority (unless CONTENT_PIPELINE_LLM_BACKEND is set):
  1. anthropic  — ANTHROPIC_API_KEY
  2. azure_openai — AZURE_OPENAI_ENDPOINT + API key
  3. openai — OPENAI_API_KEY or AI_API_KEY (no Azure endpoint)
  4. secret file — AI_SECRET_FILE (default /tmp/ai) then retry

Environment variables:
  ANTHROPIC_API_KEY, ANTHROPIC_MODEL (default: claude-opus-4-7)
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
  AZURE_OPENAI_DEPLOYMENT
  OPENAI_API_KEY, OPENAI_MODEL
  AI_API_KEY, AI_AZURE_OPENAI_ENDPOINT, AI_PROJECT_ENDPOINT
  CONTENT_PIPELINE_LLM_BACKEND=anthropic|azure_openai|openai
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

BackendName = Literal["anthropic", "azure_openai", "openai"]

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-7"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_AZURE_API_VERSION = "2024-10-21"
CACHE_TYPE = "ephemeral"

SYSTEM_PROMPT = (
    "You are an expert technical content writer specialising in PCI-DSS, "
    "payments security, and cloud engineering. You transform source blog posts "
    "into platform-specific content variants. Follow the output format instructions precisely. "
    "Do not add commentary or explanations outside the requested output."
)


@dataclass(frozen=True)
class BackendConfig:
    name: BackendName
    api_key: str
    model: str
    azure_endpoint: str = ""
    azure_api_version: str = DEFAULT_AZURE_API_VERSION
    project_endpoint: str = ""
    credential_source: str = ""
    # True when endpoint is …/openai/v1 (Azure AI Foundry OpenAI-compatible surface).
    azure_use_v1_base_url: bool = False


def _read_secret_file(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"api_key": raw}
    if isinstance(data, str):
        return {"api_key": data}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if v is not None}


def _secret_file_path() -> Path | None:
    if os.environ.get("CONTENT_PIPELINE_SKIP_SECRET_FILE") == "1":
        return None
    if explicit := os.environ.get("AI_SECRET_FILE"):
        return Path(explicit)
    # Convenience default for local bootstrap (see deploy/secrets/).
    default = Path("/tmp/ai")
    return default if default.is_file() else None


def _merge_secret_file_into_env() -> str | None:
    """Load secret file into os.environ for unset keys. Returns path if read."""
    path = _secret_file_path()
    if path is None or not path.is_file():
        return None
    data = _read_secret_file(path)
    if not data:
        return None

    mapping = {
        "api_key": ["AI_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"],
        "project_endpoint": ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "AI_PROJECT_ENDPOINT"],
        "azure_openai_endpoint": ["AZURE_OPENAI_ENDPOINT", "AI_AZURE_OPENAI_ENDPOINT"],
        "api_key_name": ["AI_API_KEY_NAME"],
    }
    for src, targets in mapping.items():
        value = data.get(src, "")
        if not value:
            continue
        for target in targets:
            if not os.environ.get(target):
                os.environ[target] = value

    # Anthropic only when the key is clearly an Anthropic token.
    if data.get("api_key") and not os.environ.get("ANTHROPIC_API_KEY"):
        key = data["api_key"]
        if key.startswith("sk-ant-"):
            os.environ["ANTHROPIC_API_KEY"] = key

    return str(path)


def _api_key() -> str:
    return (
        os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AI_API_KEY")
        or ""
    )


def _azure_endpoint() -> str:
    return (
        os.environ.get("AZURE_OPENAI_ENDPOINT")
        or os.environ.get("AI_AZURE_OPENAI_ENDPOINT")
        or ""
    ).strip()


def normalize_azure_endpoint(endpoint: str) -> tuple[str, bool]:
    """Return (endpoint_for_client, use_openai_v1_client).

    Azure AI Foundry often exposes …/openai/v1 — use OpenAI(base_url=…).
    Classic Azure OpenAI uses https://{resource}.openai.azure.com/ with AzureOpenAI().
    """
    ep = endpoint.strip().rstrip("/")
    if ep.endswith("/openai/v1"):
        return f"{ep}/", True
    # AzureOpenAI SDK builds …/openai/deployments/… — strip stray /openai/v1 segments.
    for suffix in ("/openai/v1", "/openai"):
        if ep.endswith(suffix):
            ep = ep[: -len(suffix)]
    return ep.rstrip("/") + "/", False


def _is_anthropic_api_key(key: str) -> bool:
    return key.startswith("sk-ant-")


def _anthropic_config(source: str) -> BackendConfig | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or not _is_anthropic_api_key(key):
        return None
    return BackendConfig(
        name="anthropic",
        api_key=key,
        model=os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        credential_source=source,
    )


def _azure_config(source: str) -> BackendConfig | None:
    raw_endpoint = _azure_endpoint()
    key = _api_key()
    if not raw_endpoint or not key:
        return None
    client_endpoint, use_v1 = normalize_azure_endpoint(raw_endpoint)
    model = (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        or os.environ.get("OPENAI_MODEL")
        or ""
    )
    if not model:
        model = DEFAULT_OPENAI_MODEL
    return BackendConfig(
        name="azure_openai",
        api_key=key,
        model=model,
        azure_endpoint=client_endpoint,
        azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION),
        project_endpoint=os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "")
        or os.environ.get("AI_PROJECT_ENDPOINT", ""),
        credential_source=source,
        azure_use_v1_base_url=use_v1,
    )


def _openai_config(source: str) -> BackendConfig | None:
    key = _api_key()
    if not key or _azure_endpoint():
        return None
    return BackendConfig(
        name="openai",
        api_key=key,
        model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        credential_source=source,
    )


def resolve_backend() -> BackendConfig:
    """Pick LLM backend from env (and optional secret file). Exits if none found."""
    forced = os.environ.get("CONTENT_PIPELINE_LLM_BACKEND", "").strip().lower()
    secret_path: str | None = None

    def try_resolve() -> BackendConfig | None:
        if forced == "anthropic":
            cfg = _anthropic_config("env(forced)")
            return cfg
        if forced == "azure_openai":
            cfg = _azure_config("env(forced)")
            return cfg
        if forced == "openai":
            cfg = _openai_config("env(forced)")
            return cfg

        anthropic = _anthropic_config("env")
        azure = _azure_config("env")
        openai = _openai_config("env")
        # Real Anthropic key wins; otherwise Azure Foundry when endpoint is configured.
        if anthropic:
            return anthropic
        if azure:
            return azure
        return openai

    cfg = try_resolve()
    if cfg:
        return cfg

    if forced:
        from env_help import exit_missing_llm_credentials

        exit_missing_llm_credentials(
            reason=f"CONTENT_PIPELINE_LLM_BACKEND={forced} but required credentials are unset",
        )

    secret_path = _merge_secret_file_into_env()
    cfg = try_resolve()
    if cfg:
        return replace(cfg, credential_source=f"file:{secret_path}")

    from env_help import exit_missing_llm_credentials

    exit_missing_llm_credentials(secret_path)


def build_user_text(source_md: str, spec: str, canonical_url: str) -> str:
    return (
        f"SOURCE ARTICLE (canonical URL: {canonical_url}):\n\n"
        f"---BEGIN SOURCE---\n{source_md}\n---END SOURCE---\n\n"
        f"VARIANT INSTRUCTIONS:\n\n{spec}"
    )


def build_anthropic_messages(source_md: str, spec: str, canonical_url: str) -> tuple[list[dict], str]:
    user_cached: dict = {
        "type": "text",
        "text": (
            f"SOURCE ARTICLE (canonical URL: {canonical_url}):\n\n"
            f"---BEGIN SOURCE---\n{source_md}\n---END SOURCE---\n\n"
            "Generate the variant described in the next message."
        ),
        "cache_control": {"type": CACHE_TYPE},
    }
    user_task: dict = {
        "type": "text",
        "text": f"VARIANT INSTRUCTIONS:\n\n{spec}",
    }
    return [{"role": "user", "content": [user_cached, user_task]}], SYSTEM_PROMPT


def _complete_anthropic(cfg: BackendConfig, source_md: str, spec: str, canonical_url: str) -> str:
    import anthropic
    from env_help import print_auth_failure_help

    client = anthropic.Anthropic(api_key=cfg.api_key)
    messages, system = build_anthropic_messages(source_md, spec, canonical_url)
    try:
        response = client.messages.create(
            model=cfg.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
    except anthropic.AuthenticationError:
        print_auth_failure_help("anthropic")
        raise
    return response.content[0].text.strip()


def _complete_openai_compat(cfg: BackendConfig, source_md: str, spec: str, canonical_url: str) -> str:
    try:
        from openai import AuthenticationError, AzureOpenAI, NotFoundError, OpenAI
    except ImportError as exc:
        print(
            "error: openai package required for azure_openai/openai backends.\n"
            "  cd agents/content-pipeline && uv sync",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    from env_help import print_auth_failure_help, print_azure_not_found_help

    if cfg.name == "azure_openai" and cfg.azure_use_v1_base_url:
        client: Any = OpenAI(
            base_url=cfg.azure_endpoint,
            api_key=cfg.api_key,
        )
    elif cfg.name == "azure_openai":
        client = AzureOpenAI(
            azure_endpoint=cfg.azure_endpoint,
            api_key=cfg.api_key,
            api_version=cfg.azure_api_version,
        )
    else:
        client = OpenAI(api_key=cfg.api_key)

    try:
        response = client.chat.completions.create(
            model=cfg.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_text(source_md, spec, canonical_url)},
            ],
        )
    except AuthenticationError:
        print_auth_failure_help(cfg.name)
        raise
    except NotFoundError:
        if cfg.name == "azure_openai":
            print_azure_not_found_help(cfg)
        raise
    return (response.choices[0].message.content or "").strip()


def complete(
    source_md: str,
    spec: str,
    canonical_url: str,
    backend: BackendConfig | None = None,
) -> str:
    """Run one variant generation call using the resolved backend."""
    cfg = backend or resolve_backend()
    if cfg.name == "anthropic":
        return _complete_anthropic(cfg, source_md, spec, canonical_url)
    return _complete_openai_compat(cfg, source_md, spec, canonical_url)


def describe_backend(cfg: BackendConfig) -> str:
    parts = [f"{cfg.name} (model={cfg.model}, creds={cfg.credential_source})"]
    if cfg.name == "azure_openai" and cfg.azure_endpoint:
        mode = "openai-v1-base-url" if cfg.azure_use_v1_base_url else "azure-sdk"
        parts.append(f"endpoint={cfg.azure_endpoint} mode={mode}")
    return " ".join(parts)
