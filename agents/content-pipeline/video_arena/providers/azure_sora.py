"""Azure AI Foundry — OpenAI Sora 2 video generation."""

from __future__ import annotations

import os
from pathlib import Path

from video_arena.providers import register
from video_arena.credential_bootstrap import ensure_sora_env
from video_arena.providers.azure_video_common import (
    azure_sora_env_configured,
    azure_video_missing_config_help,
    run_azure_sora_job,
)
from video_arena.providers.base import ArenaProvider, ProviderResult

DEFAULT_MODEL = "sora-2"


@register
class AzureSoraProvider(ArenaProvider):
    provider_id = "azure_sora"
    display_name = "Azure Foundry · Sora 2"
    default_model = DEFAULT_MODEL

    def is_configured(self) -> bool:
        ensure_sora_env()
        return azure_sora_env_configured()

    def missing_config_help(self) -> str:
        return azure_video_missing_config_help(model_hint="sora-2")

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        ensure_sora_env()
        model = (
            os.environ.get("AZURE_SORA_MODEL")
            or os.environ.get("AZURE_SORA_DEPLOYMENT")
            or DEFAULT_MODEL
        )
        return run_azure_sora_job(
            provider_id=self.provider_id,
            model=model,
            prompt=prompt,
            out_dir=out_dir,
            size=os.environ.get("AZURE_SORA_SIZE", "720x1280"),
            seconds=os.environ.get("AZURE_SORA_SECONDS", "8"),
            reference_image=reference_image,
            allow_reference_image=True,
        )
