"""AWS Bedrock — Luma Ray 2 (async invoke → S3 or local poll)."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from video_arena.providers import register
from video_arena.providers.base import ArenaProvider, ProviderResult

MODEL_ID = "luma.ray-v2:0"
POLL_INTERVAL_S = 15
MAX_WAIT_S = 900


@register
class BedrockLumaProvider(ArenaProvider):
    provider_id = "bedrock_luma"
    display_name = "AWS Bedrock · Luma Ray 2"
    default_model = MODEL_ID

    def is_configured(self) -> bool:
        return bool(os.environ.get("VIDEO_ARENA_S3_OUTPUT_URI"))

    def missing_config_help(self) -> str:
        return (
            "export AWS_REGION=us-west-2\n"
            "export VIDEO_ARENA_S3_OUTPUT_URI=s3://your-bucket/video-arena/\n"
            "AWS credentials via profile or env (Bedrock InvokeModel in us-west-2).\n"
            "After job completes, sync MP4 locally or set VIDEO_ARENA_S3_DOWNLOAD=1."
        )

    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        import boto3

        region = os.environ.get("AWS_REGION", "us-west-2")
        bedrock = boto3.client("bedrock-runtime", region_name=region)
        s3_out = os.environ["VIDEO_ARENA_S3_OUTPUT_URI"].rstrip("/") + "/"

        model_input: dict = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "duration": os.environ.get("BEDROCK_LUMA_DURATION", "5s"),
            "resolution": os.environ.get("BEDROCK_LUMA_RESOLUTION", "720p"),
        }
        if reference_image and reference_image.is_file():
            # Luma on Bedrock accepts image URL; upload to S3 separately in production.
            model_input["image_url"] = os.environ.get("VIDEO_ARENA_REFERENCE_IMAGE_URL", "")

        resp = bedrock.start_async_invoke(
            modelId=MODEL_ID,
            modelInput=model_input,
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": s3_out}},
        )
        invocation_arn = resp["invocationArn"]
        deadline = time.time() + MAX_WAIT_S
        status = "InProgress"
        while time.time() < deadline and status == "InProgress":
            time.sleep(POLL_INTERVAL_S)
            poll = bedrock.get_async_invoke(invocationArn=invocation_arn)
            status = poll.get("status", "InProgress")

        if status != "Completed":
            return ProviderResult(
                provider_id=self.provider_id,
                model=MODEL_ID,
                status="failed",
                message=f"Bedrock async invoke {status}: {invocation_arn}",
                extra={"invocation_arn": invocation_arn},
            )

        dest = out_dir / "video.mp4"
        if os.environ.get("VIDEO_ARENA_S3_DOWNLOAD") == "1":
            s3 = boto3.client("s3")
            # Caller should set VIDEO_ARENA_S3_OUTPUT_KEY to the object key from job output
            key = os.environ.get("VIDEO_ARENA_S3_OUTPUT_KEY", "")
            bucket = s3_out.replace("s3://", "").split("/")[0]
            s3.download_file(bucket, key, str(dest))
        else:
            (out_dir / "DOWNLOAD.md").write_text(
                f"Job completed. Output at {s3_out}\n"
                f"invocation_arn={invocation_arn}\n"
                "Set VIDEO_ARENA_S3_DOWNLOAD=1 and VIDEO_ARENA_S3_OUTPUT_KEY to fetch MP4.\n",
                encoding="utf-8",
            )
            return ProviderResult(
                provider_id=self.provider_id,
                model=MODEL_ID,
                status="ok",
                message=f"Completed — MP4 at {s3_out} (see DOWNLOAD.md)",
                extra={"invocation_arn": invocation_arn, "s3_uri": s3_out},
            )

        return ProviderResult(
            provider_id=self.provider_id,
            model=MODEL_ID,
            status="ok",
            message="Downloaded from S3",
            video_path=str(dest),
            extra={"invocation_arn": invocation_arn},
        )
