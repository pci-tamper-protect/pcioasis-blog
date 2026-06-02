"""Azure AI Foundry — OpenAI Sora 2 video generation."""

from __future__ import annotations

import os
import time
from pathlib import Path

from video_arena.providers import register
from video_arena.providers.base import ArenaProvider, ProviderResult

DEFAULT_MODEL = "sora-2"
POLL_INTERVAL_S = 10
MAX_WAIT_S = 900


@register
class AzureSoraProvider(ArenaProvider):
    provider_id = "azure_sora"
    display_name = "Azure Foundry · Sora 2"
    default_model = DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(
            os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AI_API_KEY")
        ) and bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))

    def missing_config_help(self) -> str:
        return (
            "eval \"$(./deploy/secrets/export-macos-keychain.sh)\"\n"
            "export AZURE_OPENAI_DEPLOYMENT=sora-2   # or your Sora deployment name\n"
            "Enable Sora 2 on the Foundry deployment (preview/GA per region)."
        )

    def _client(self):
        from openai import OpenAI

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        if endpoint.endswith("/openai/v1"):
            return OpenAI(
                base_url=f"{endpoint}/",
                api_key=os.environ.get("AZURE_OPENAI_API_KEY")
                or os.environ.get("AI_API_KEY"),
            )
        return OpenAI(
            azure_endpoint=endpoint,
            api_key=os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AI_API_KEY"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        client = self._client()
        model = os.environ.get("AZURE_SORA_MODEL") or os.environ.get(
            "AZURE_OPENAI_DEPLOYMENT", DEFAULT_MODEL
        )

        create_kwargs: dict = {
            "model": model,
            "prompt": prompt,
            "size": "720x1280",
            "seconds": os.environ.get("AZURE_SORA_SECONDS", "8"),
        }
        if reference_image and reference_image.is_file():
            with reference_image.open("rb") as fh:
                create_kwargs["input_reference"] = fh
                job = client.videos.create(**create_kwargs)
        else:
            job = client.videos.create(**create_kwargs)
        job_id = getattr(job, "id", None) or str(job)
        deadline = time.time() + MAX_WAIT_S
        status = job
        while time.time() < deadline:
            status = client.videos.retrieve(job_id)
            state = getattr(status, "status", None) or getattr(status, "state", "unknown")
            if state in ("completed", "succeeded", "ready"):
                break
            if state in ("failed", "error", "cancelled"):
                return ProviderResult(
                    provider_id=self.provider_id,
                    model=model,
                    status="failed",
                    message=f"Sora job {job_id} ended with status={state}",
                    extra={"job_id": job_id},
                )
            time.sleep(POLL_INTERVAL_S)

        dest = out_dir / "video.mp4"
        content = client.videos.download_content(job_id)
        if hasattr(content, "write_to_file"):
            content.write_to_file(dest)
        elif hasattr(content, "read"):
            dest.write_bytes(content.read())
        else:
            dest.write_bytes(bytes(content))

        return ProviderResult(
            provider_id=self.provider_id,
            model=model,
            status="ok",
            message=f"Sora job {job_id} completed",
            video_path=str(dest),
            extra={"job_id": job_id},
        )
