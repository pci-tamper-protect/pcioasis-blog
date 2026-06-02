"""Azure AI Foundry — original OpenAI Sora (v1) video generation."""

from __future__ import annotations

import os
from pathlib import Path

from video_arena.providers import register
from video_arena.providers.azure_video_common import (
    azure_video_configured,
    azure_video_missing_config_help,
    run_azure_sora_job,
)
from video_arena.providers.base import ArenaProvider, ProviderResult

DEFAULT_MODEL = "sora"


@register
class AzureSoraV1Provider(ArenaProvider):
    provider_id = "azure_sora_v1"
    display_name = "Azure Foundry · Sora (v1)"
    default_model = DEFAULT_MODEL

    def is_configured(self) -> bool:
        return azure_video_configured()

    def missing_config_help(self) -> str:
        return (
            azure_video_missing_config_help(model_hint="sora")
            + "\n# Optional second deployment on the same Foundry resource:\n"
            "export AZURE_SORA_V1_DEPLOYMENT=sora   # separate from AZURE_SORA_MODEL / sora-2"
        )

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        model = (
            os.environ.get("AZURE_SORA_V1_DEPLOYMENT")
            or os.environ.get("AZURE_SORA_V1_MODEL")
            or DEFAULT_MODEL
        )
        return run_azure_sora_job(
            provider_id=self.provider_id,
            model=model,
            prompt=prompt,
            out_dir=out_dir,
            size=os.environ.get("AZURE_SORA_V1_SIZE", "720x1280"),
            seconds=os.environ.get("AZURE_SORA_V1_SECONDS", "8"),
            reference_image=reference_image,
            # Sora v1 on Foundry is text→video; image anchor is Sora 2 only today.
            allow_reference_image=False,
        )
