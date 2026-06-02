#!/usr/bin/env python3
"""Run four-provider short video arena for a Hugo post.

Requires text variants (generate_variants.py) first. Writes MP4 candidates and
review.html under _variants/video-arena/.

Usage:
  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/generate_video_arena.py \\
    content/posts/zkTLS/zktls-proof-of-provenance

  # Single provider:
  ... --only replicate_hailuo

See docs/content-pipeline/VIDEO_ARENA.md for credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from video_arena.orchestrator import run_arena


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate short video arena candidates")
    parser.add_argument("post_dir", type=Path, help="Hugo post directory with _variants/")
    parser.add_argument(
        "--only",
        action="append",
        metavar="PROVIDER",
        help="Run one provider: azure_sora, vertex_veo, bedrock_luma, replicate_hailuo",
    )
    parser.add_argument(
        "--skip-critique",
        action="store_true",
        help="Skip LLM text critique files",
    )
    args = parser.parse_args()

    print(f"Video arena: {args.post_dir.resolve()}")
    try:
        arena_dir = run_arena(
            args.post_dir.resolve(),
            only=args.only,
            skip_critique=args.skip_critique,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Done: {arena_dir}")


if __name__ == "__main__":
    main()
