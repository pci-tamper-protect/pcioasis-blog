"""Replicate — MiniMax Hailuo 2.3 (comparison / pay-per-use lane)."""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

from video_arena.providers import register
from video_arena.providers.base import ArenaProvider, ProviderResult

MODEL = "minimax/hailuo-2.3"
POLL_INTERVAL_S = 5
MAX_WAIT_S = 600


@register
class ReplicateHailuoProvider(ArenaProvider):
    provider_id = "replicate_hailuo"
    display_name = "Replicate · MiniMax Hailuo 2.3"
    default_model = MODEL

    def is_configured(self) -> bool:
        return bool(os.environ.get("REPLICATE_API_TOKEN"))

    def missing_config_help(self) -> str:
        return (
            "Set REPLICATE_API_TOKEN (https://replicate.com/account/api-tokens).\n"
            "Optional: `uv sync --project agents/content-pipeline --extra video-arena`"
        )

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        import replicate  # noqa: PLC0415 — optional extra

        out_dir.mkdir(parents=True, exist_ok=True)
        input_args: dict = {
            "prompt": prompt,
            "duration": 6,
            "resolution": "768p",
            "prompt_optimizer": True,
        }
        if reference_image and reference_image.is_file():
            with reference_image.open("rb") as fh:
                input_args["first_frame_image"] = fh
                output = replicate.run(MODEL, input=input_args)
        else:
            output = replicate.run(MODEL, input=input_args)
        video_url = _extract_url(output)
        if not video_url:
            return ProviderResult(
                provider_id=self.provider_id,
                model=MODEL,
                status="failed",
                message=f"Unexpected Replicate output shape: {output!r}",
            )

        dest = out_dir / "video.mp4"
        urllib.request.urlretrieve(video_url, dest)  # noqa: S310 — trusted Replicate CDN URL
        return ProviderResult(
            provider_id=self.provider_id,
            model=MODEL,
            status="ok",
            message="Downloaded from Replicate",
            video_path=str(dest),
            extra={"source_url": video_url},
        )


def _extract_url(output: object) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        return first if isinstance(first, str) else getattr(first, "url", None)
    return getattr(output, "url", None)
