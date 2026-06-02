#!/usr/bin/env python3
"""Generate platform-specific content variants from a Hugo blog post.

Reads an index.md from pcioasis-blog, calls an LLM (Anthropic, Azure OpenAI, or OpenAI),
and writes audience-targeted variants into a _variants/ subdirectory.

Credentials (first match wins): ANTHROPIC_API_KEY, then Azure OpenAI env pair,
then OPENAI_API_KEY / AI_API_KEY, then AI_SECRET_FILE (/tmp/ai). See ai_backend.py.

Outputs:
  _variants/
    planetkesten.md     # broad/non-technical audience
    kbroughton.md       # highly technical audience
    linkedin.md         # Krebs-style short link post (format, not voice)
    bluesky.txt         # short AT-Protocol post (300 chars)
    mastodon.txt        # Mastodon post with CW header for infosec.exchange
    pixelfed.txt        # image-centric caption for Pixelfed
    clapper.txt         # short-form script for Clapper (primary short-video, US-first)
    twitter-xref.txt    # manual helper: tweet referencing Bluesky post
    tiktok-xref.txt     # manual helper: TikTok referencing Clapper post
    youtube/
      script.md         # narration script with cues
      description.md    # video description with hashtags
      chapters.txt      # timestamp chapter list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from ai_backend import (
    build_anthropic_messages,
    complete,
    describe_backend,
    resolve_backend,
)
from platform_specs import (  # noqa: F401 — re-exported for tests
    BLUESKY_LIMIT,
    CLAPPER_LIMIT,
    MASTODON_ACCOUNT,
    MASTODON_LIMIT,
    PLATFORM_SPECS,
)

# Re-export for tests that import build_messages from this module.
build_messages = build_anthropic_messages


# ---------------------------------------------------------------------------
# Frontmatter parsing (same as sync_blog_posts.py)
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


# Platform prompts: agents/content-pipeline/platform_specs.py
# Human playbook: docs/content-pipeline/PLATFORM_PLAYBOOK.md


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------


def generate_variants(post_dir: Path, dry_run: bool = False) -> None:
    index_file = post_dir / "index.md"
    if not index_file.exists():
        sys.exit(f"No index.md found at {index_file}")

    raw = index_file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)

    slug = meta.get("slug") or post_dir.name
    section = post_dir.parent.name.lower()
    canonical_url = f"https://blog.pcioasis.com/posts/{section}/{slug}/"

    variants_dir = post_dir / "_variants"
    youtube_dir = variants_dir / "youtube"

    tasks: list[tuple[str, Path]] = [
        ("planetkesten", variants_dir / "planetkesten.md"),
        ("kbroughton", variants_dir / "kbroughton.md"),
        ("linkedin", variants_dir / "linkedin.md"),
        ("bluesky", variants_dir / "bluesky.txt"),
        ("mastodon", variants_dir / "mastodon.txt"),
        ("pixelfed", variants_dir / "pixelfed.txt"),
        ("clapper", variants_dir / "clapper.txt"),
        ("tiktok_xref", variants_dir / "tiktok-xref.txt"),
        ("douyin_xref", variants_dir / "douyin-xref.txt"),
        ("rednote_xref", variants_dir / "rednote-xref.txt"),
        ("youtube_shorts", variants_dir / "youtube-shorts.txt"),
        ("reels_xref", variants_dir / "reels-xref.txt"),
        ("twitter_xref", variants_dir / "twitter-xref.txt"),
        ("youtube_script", youtube_dir / "script.md"),
        ("youtube_description", youtube_dir / "description.md"),
        ("youtube_chapters", youtube_dir / "chapters.txt"),
    ]

    source_md = f"# {meta.get('title', '')}\n\n{body}"

    # Optional frontmatter field: platforms: [bluesky, mastodon, ...]
    # If present, only the listed variant keys are generated.
    allowed_platforms: set[str] | None = None
    if "platforms" in meta and isinstance(meta["platforms"], list):
        allowed_platforms = set(meta["platforms"])

    active_tasks = [
        (k, p) for k, p in tasks
        if allowed_platforms is None or k in allowed_platforms
    ]

    if dry_run:
        for variant_key, out_path in active_tasks:
            print(f"  [dry-run] would generate {variant_key} -> {out_path.relative_to(post_dir)}")
        return

    backend = resolve_backend()
    print(f"LLM backend: {describe_backend(backend)}")

    variants_dir.mkdir(exist_ok=True)
    youtube_dir.mkdir(exist_ok=True)

    results: dict[str, str] = {}
    skipped: list[str] = []
    for variant_key, out_path in active_tasks:
        print(f"  Generating {variant_key}...", flush=True)
        spec = PLATFORM_SPECS[variant_key]
        text = complete(source_md, spec, canonical_url, backend=backend)
        if text.strip().startswith("SKIP:"):
            print(f"    -> skipped ({text.strip()})")
            skipped.append(variant_key)
            continue
        results[variant_key] = text
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"    -> {out_path.relative_to(post_dir)}")

    manifest = {
        "slug": slug,
        "canonical": canonical_url,
        "title": meta.get("title", ""),
        "date": str(meta.get("date", "")),
        "llm_backend": backend.name,
        "llm_model": backend.model,
        "variants": {k: str(p.relative_to(post_dir)) for k, p in active_tasks if k not in skipped},
        "skipped": skipped,
    }
    (variants_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nVariants written to {variants_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate platform variants from a Hugo post"
    )
    parser.add_argument(
        "post_dir",
        type=Path,
        help="Path to the Hugo post directory containing index.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be generated without writing files or calling the API",
    )
    args = parser.parse_args()

    print(f"Generating variants for: {args.post_dir}")
    generate_variants(args.post_dir.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
