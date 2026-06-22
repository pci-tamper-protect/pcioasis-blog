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

    endpoint = (
        os.environ.get("AZURE_SORA_ENDPOINT")
        or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    ).rstrip("/")
    api_key = (
        os.environ.get("AZURE_SORA_API_KEY")
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("AI_API_KEY")
    )
    if endpoint.endswith("/openai/v1"):
        return OpenAI(base_url=f"{endpoint}/", api_key=api_key)
    return OpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )


def azure_video_configured() -> bool:
    endpoint = os.environ.get("AZURE_SORA_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT")
    key = (
        os.environ.get("AZURE_SORA_API_KEY")
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("AI_API_KEY")
    )
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
    client = azure_video_client()
    create_kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "seconds": seconds,
    }
    ref_note: str | None = None
    if reference_image and reference_image.is_file():
        if allow_reference_image:
            with reference_image.open("rb") as fh:
                create_kwargs["input_reference"] = fh
                job = client.videos.create(**create_kwargs)
        else:
            ref_note = f"reference image ignored ({reference_image.name}); model is text-only"
            job = client.videos.create(**create_kwargs)
    else:
        job = client.videos.create(**create_kwargs)

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
