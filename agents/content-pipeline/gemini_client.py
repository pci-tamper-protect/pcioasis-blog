"""Shared Gemini client — Vertex AI (GCP billing) or Google AI Studio API key."""

from __future__ import annotations

import os
from typing import Literal

Backend = Literal["vertex", "api_key"]


def gemini_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )


def missing_gemini_help() -> str:
    return (
        "# Vertex (bills to GCP project — same as Veo):\n"
        'eval "$(./deploy/vertex/export-veo.sh)"\n'
        "gcloud auth application-default login\n"
        "\n"
        "# Or Google AI Studio API key:\n"
        "export GEMINI_API_KEY=...\n"
    )


def make_gemini_client() -> "tuple[genai.Client, Backend]":
    """Return (client, backend). Prefers Vertex when GOOGLE_CLOUD_PROJECT is set."""
    from google import genai

    project = (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if project:
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        return (
            genai.Client(vertexai=True, project=project, location=location),
            "vertex",
        )

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key), "api_key"

    raise RuntimeError(missing_gemini_help())
