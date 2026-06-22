#!/usr/bin/env python3
"""Re-extract thumbnail candidates and refresh review.html for an existing arena.

Usage (from repo root):
  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/regenerate_arena_thumbnails.py \\
    content/posts/llm-security/meta-instagram-ai-excessive-agency
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from video_arena.review import load_arena_manifest, write_review_html
from video_arena.thumbnails import regenerate_arena_thumbnails


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate video-arena thumbnail candidates and review.html",
    )
    parser.add_argument(
        "post_dir",
        type=Path,
        help="Hugo post directory (contains _variants/video-arena/)",
    )
    args = parser.parse_args()

    post_dir = args.post_dir.resolve()
    arena_dir = post_dir / "_variants" / "video-arena"
    if not arena_dir.is_dir():
        print(f"error: missing {arena_dir}", file=sys.stderr)
        raise SystemExit(1)

    manifest = load_arena_manifest(arena_dir)
    if not manifest:
        print(f"error: missing {arena_dir / 'manifest.json'}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Regenerating thumbnails: {arena_dir}")
    regenerate_arena_thumbnails(arena_dir)
    review_path = write_review_html(arena_dir, manifest)
    print(f"Done: {review_path}")
    for sub in sorted(arena_dir.iterdir()):
        if not sub.is_dir():
            continue
        thumb_json = sub / "thumbnails.json"
        if not thumb_json.is_file():
            continue
        import json

        data = json.loads(thumb_json.read_text(encoding="utf-8"))
        n = len(data.get("candidates", []))
        err = data.get("error")
        print(f"  {sub.name}: {n} candidates" + (f" ({err})" if err else ""))


if __name__ == "__main__":
    main()
