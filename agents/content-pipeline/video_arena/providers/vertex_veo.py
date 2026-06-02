"""Google Vertex AI — Veo 3.1 (GCP credits)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from video_arena.providers import register
from video_arena.providers.base import ArenaProvider, ProviderResult

DEFAULT_MODEL = "veo-3.1-fast-generate-001"
POLL_INTERVAL_S = 15
MAX_WAIT_S = 1200


@register
class VertexVeoProvider(ArenaProvider):
    provider_id = "vertex_veo"
    display_name = "Vertex AI · Veo 3.1 Fast"
    default_model = DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))

    def missing_config_help(self) -> str:
        return (
            "export GOOGLE_CLOUD_PROJECT=your-gcp-project\n"
            "export GOOGLE_CLOUD_LOCATION=us-central1\n"
            "gcloud auth application-default login\n"
            "Enable Vertex AI API + Veo access on the project (uses GCP credits)."
        )

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        from google import genai
        from google.genai import types

        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        model = os.environ.get("VERTEX_VEO_MODEL", DEFAULT_MODEL)

        client = genai.Client(vertexai=True, project=project, location=location)
        config = types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=int(os.environ.get("VERTEX_VEO_SECONDS", "6")),
            number_of_videos=1,
        )
        kwargs: dict = {"model": model, "prompt": prompt, "config": config}
        if reference_image and reference_image.is_file():
            kwargs["image"] = types.Image.from_file(location=str(reference_image))

        operation = client.models.generate_videos(**kwargs)
        deadline = time.time() + MAX_WAIT_S
        while not operation.done and time.time() < deadline:
            time.sleep(POLL_INTERVAL_S)
            operation = client.operations.get(operation)

        if not operation.done:
            return ProviderResult(
                provider_id=self.provider_id,
                model=model,
                status="failed",
                message="Veo operation timed out",
            )

        generated = operation.response.generated_videos[0]
        video_obj = generated.video
        dest = out_dir / "video.mp4"
        if hasattr(video_obj, "save"):
            video_obj.save(dest)
        elif hasattr(client.files, "download") and getattr(video_obj, "name", None):
            client.files.download(file=video_obj, path=str(dest))
        else:
            return ProviderResult(
                provider_id=self.provider_id,
                model=model,
                status="failed",
                message="Could not download Veo output — check SDK version",
            )

        return ProviderResult(
            provider_id=self.provider_id,
            model=model,
            status="ok",
            message="Veo generation completed",
            video_path=str(dest),
        )
