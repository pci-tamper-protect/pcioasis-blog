"""Shared Azure AI Foundry / OpenAI video job helpers (Sora v1 + Sora 2)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from video_arena.providers.base import ProviderResult

POLL_INTERVAL_S = 10
MAX_WAIT_S = 900


def azure_video_client():
    from openai import OpenAI

    endpoint = os.environ.get("AZURE_SORA_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_SORA_API_KEY") or os.environ.get(
        "AZURE_OPENAI_API_KEY"
    )
    if not endpoint or not api_key:
        raise RuntimeError(
            "Sora credentials missing. Run: eval \"$(./deploy/secrets/export-sora.sh)\""
        )
    if endpoint.endswith("/openai/v1"):
        return OpenAI(base_url=f"{endpoint}/", api_key=api_key)
    return OpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )


def azure_sora_env_configured() -> bool:
    """True when dedicated Sora Foundry vars are set (not chat LLM fallback)."""
    return bool(
        os.environ.get("AZURE_SORA_ENDPOINT")
        and (
            os.environ.get("AZURE_SORA_API_KEY")
            or os.environ.get("AZURE_OPENAI_API_KEY")
        )
    )


def azure_video_configured() -> bool:
    """Configured for Sora T2V — prefers AZURE_SORA_* after credential bootstrap."""
    if azure_sora_env_configured():
        return True
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    key = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AI_API_KEY")
    return bool(key) and bool(endpoint)


def azure_video_missing_config_help(*, model_hint: str) -> str:
    return (
        "# Sora uses a separate Foundry resource (often another subscription):\n"
        "eval \"$(./deploy/secrets/export-sora.sh)\"\n"
        "# or from GCP:\n"
        "# gcloud secrets versions access latest --secret=azure_ai_foundry_sora2 --project=pcioasis-blog > /tmp/sora.json\n"
        f"export AZURE_SORA_DEPLOYMENT={model_hint}   # portal deployment name\n"
        "Chat LLM creds from export-macos-keychain.sh are NOT used when AZURE_SORA_* is set."
    )


def _sora_deployment_404_message(model: str, exc: Exception) -> str:
    ep = os.environ.get("AZURE_SORA_ENDPOINT", "(unset)")
    return (
        f"Sora deployment '{model}' not found on {ep}. "
        "Chat LLM creds (AZURE_OPENAI_*) are not used for video — run "
        'eval "$(./deploy/secrets/export-sora.sh)" and restart preview_server.'
    )


def _create_sora_video(client: Any, create_kwargs: dict[str, Any]) -> Any:
    model = str(create_kwargs.get("model", "sora-2"))
    try:
        return client.videos.create(**create_kwargs)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "deployment" in msg.lower() and "does not exist" in msg.lower():
            raise RuntimeError(_sora_deployment_404_message(model, exc)) from exc
        raise


def run_azure_sora_job(
    *,
    provider_id: str,
    model: str,
    prompt: str,
    out_dir: Path,
    size: str,
    seconds: str,
    reference_image: Path | None = None,
    allow_reference_image: bool = True,
) -> ProviderResult:
    """Poll Azure Foundry video generation until complete or timeout."""
    try:
        client = azure_video_client()
    except RuntimeError as exc:
        return ProviderResult(
            provider_id=provider_id,
            model=model,
            status="failed",
            message=str(exc),
        )
    create_kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "seconds": seconds,
    }
    ref_note: str | None = None
    try:
        if reference_image and reference_image.is_file():
            if allow_reference_image:
                with reference_image.open("rb") as fh:
                    create_kwargs["input_reference"] = fh
                    job = _create_sora_video(client, create_kwargs)
            else:
                ref_note = (
                    f"reference image ignored ({reference_image.name}); model is text-only"
                )
                job = _create_sora_video(client, create_kwargs)
        else:
            job = _create_sora_video(client, create_kwargs)
    except RuntimeError as exc:
        return ProviderResult(
            provider_id=provider_id,
            model=model,
            status="failed",
            message=str(exc),
        )

    job_id = getattr(job, "id", None) or str(job)
    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        status = client.videos.retrieve(job_id)
        state = getattr(status, "status", None) or getattr(status, "state", "unknown")
        if state in ("completed", "succeeded", "ready"):
            break
        if state in ("failed", "error", "cancelled"):
            return ProviderResult(
                provider_id=provider_id,
                model=model,
                status="failed",
                message=f"Sora job {job_id} ended with status={state}",
                extra={"job_id": job_id, "reference_note": ref_note},
            )
        time.sleep(POLL_INTERVAL_S)
    else:
        return ProviderResult(
            provider_id=provider_id,
            model=model,
            status="failed",
            message=f"Sora job {job_id} timed out after {MAX_WAIT_S}s",
            extra={"job_id": job_id, "reference_note": ref_note},
        )

    dest = out_dir / "video.mp4"
    content = client.videos.download_content(job_id)
    if hasattr(content, "write_to_file"):
        content.write_to_file(dest)
    elif hasattr(content, "read"):
        dest.write_bytes(content.read())
    else:
        dest.write_bytes(bytes(content))

    message = f"Sora job {job_id} completed"
    if ref_note:
        message = f"{message} ({ref_note})"

    return ProviderResult(
        provider_id=provider_id,
        model=model,
        status="ok",
        message=message,
        video_path=str(dest),
        extra={"job_id": job_id, "reference_note": ref_note},
    )
