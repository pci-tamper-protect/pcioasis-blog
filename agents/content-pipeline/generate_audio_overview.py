#!/usr/bin/env python3
"""NotebookLM-style audio overview via Gemini API (GCP Vertex or AI Studio key).

Reads a Hugo post index.md, generates a two-host podcast script, then
multi-speaker TTS WAV. Bills through your GCP project when using Vertex
(same credentials as Veo).

Usage:
    eval "$(./deploy/vertex/export-veo.sh)"
    export GOOGLE_CLOUD_QUOTA_PROJECT=pcioasis-blog
    uv run --project agents/content-pipeline --extra gemini \\
      python agents/content-pipeline/generate_audio_overview.py POST_DIR

    # Script only (no TTS):
    ... --script-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audio_overview.pipeline import run_audio_overview
from gemini_client import gemini_configured, missing_gemini_help


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Gemini audio overview from a blog post"
    )
    parser.add_argument("post_dir", type=Path, help="Hugo post directory")
    parser.add_argument(
        "--minutes",
        type=int,
        default=4,
        help="Target spoken length for the script (default: 4)",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Generate script.txt only; skip TTS",
    )
    args = parser.parse_args()

    if not gemini_configured():
        print(missing_gemini_help(), file=sys.stderr)
        sys.exit(1)

    out = run_audio_overview(
        args.post_dir,
        minutes=args.minutes,
        skip_tts=args.script_only,
    )
    print(f"Audio overview: {out}")
    manifest = out / "manifest.json"
    if manifest.is_file():
        print(manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
