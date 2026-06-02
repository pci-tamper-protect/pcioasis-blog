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
    linkedin.md         # professional B2B tone
    bluesky.txt         # short AT-Protocol post (300 chars)
    mastodon.txt        # Mastodon post with CW header for infosec.exchange
    pixelfed.txt        # image-centric caption for Pixelfed
    clapper.txt         # short-form script for Clapper (TikTok alt, TX-first)
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
from textwrap import dedent
from typing import Any

import yaml

from ai_backend import (
    build_anthropic_messages,
    complete,
    describe_backend,
    resolve_backend,
)

MASTODON_ACCOUNT = "@BHINFOSECURITY@infosec.exchange"
BLUESKY_LIMIT = 300
MASTODON_LIMIT = 500
CLAPPER_LIMIT = 2200  # caption chars; video itself is separate

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


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

PLATFORM_SPECS = {
    "planetkesten": dedent(
        """\
        Write a blog-length article (600–900 words) adapted for a GENERAL audience at planetkesten.com.
        - Assume zero background in PCI, payments, or infosec
        - Lead with a relatable real-world hook (e.g. "ever wondered how your credit card is protected?")
        - Avoid jargon; when technical terms are unavoidable, define them inline
        - Friendly, curious tone — like explaining to a smart friend, not a colleague
        - Preserve key takeaways and diagrams (reference them as "[diagram N]")
        - Output: valid Markdown with an H1 title, introduction, and 3–5 sections
        """
    ),
    "kbroughton": dedent(
        """\
        Write a technical deep-dive (800–1200 words) for kbroughton.github.io targeting senior engineers.
        - Audience has deep infosec/crypto background; skip basics entirely
        - Lead with the hardest technical insight or most surprising finding
        - Include implementation details, threat-model edge cases, or protocol specifics
        - Reference RFCs, CVEs, or specs by number where relevant
        - Dry, precise tone — no filler sentences
        - Output: valid Markdown with an H1 title and structured sections
        """
    ),
    "linkedin": dedent(
        """\
        Write a LinkedIn article post (400–600 words) for a professional/B2B audience.
        - Readers are security managers, CTOs, compliance officers, fintech founders
        - Lead with a business risk or regulatory angle, not a technical one
        - One concrete takeaway actionable for someone running a PCI-compliant product
        - Professional but not stiff; first-person voice is fine
        - End with 3–5 relevant hashtags on a separate line
        - Output: plain text (LinkedIn doesn't render Markdown headings well); use blank lines between paragraphs
        """
    ),
    "bluesky": dedent(
        f"""\
        Write a Bluesky post — MAXIMUM {BLUESKY_LIMIT} characters including spaces.
        - Hook in first sentence, context in second, call-to-action in third
        - End with the canonical URL as a plain link on its own line
        - Include 2–3 relevant hashtags inline (not at the end)
        - Tone: sharp and opinionated; infosec community audience
        - Output: ONLY the post text, no extra commentary
        """
    ),
    "mastodon": dedent(
        f"""\
        Write a Mastodon post for {MASTODON_ACCOUNT} on infosec.exchange — MAXIMUM {MASTODON_LIMIT} characters.
        - First line MUST be: CW: <one-line content warning summarising the topic>
        - Blank line after CW, then the post body
        - Assume infosec-savvy readers; technical depth welcome
        - Mention any relevant #infosec, #PCI, or topic hashtags
        - End with the canonical URL
        - Output: ONLY the post text including the CW line
        """
    ),
    "pixelfed": dedent(
        """\
        Write an image post caption for Pixelfed (Instagram-style, max 2200 chars).
        - Opens with a compelling visual description of the key diagram or concept image
        - 2–4 short paragraphs; mobile-friendly — short sentences
        - Heavy on emoji to aid scannability (but don't overdo it)
        - Ends with 10–15 relevant hashtags on their own line
        - Include the canonical URL before the hashtags
        - Output: ONLY the caption text
        """
    ),
    "clapper": dedent(
        f"""\
        Write a Clapper short-form video caption/script (max {CLAPPER_LIMIT} chars).
        Clapper is a US-first, Texas-origin short-video platform popular with creators
        who value free speech and domestic ownership. Audience: curious adults, not deep-tech.
        - Hook line for on-screen text overlay (≤8 words), prefixed with HOOK:
        - 3–5 talking-point bullets the creator reads to camera, prefixed with TALK:
        - Caption text for the post itself (conversational, hashtags welcome)
        - End with canonical URL
        - Output: HOOK line, then TALK bullets, then a blank line, then the caption
        """
    ),
    "twitter_xref": dedent(
        """\
        Write a SHORT tweet (max 280 chars) that references an existing Bluesky post.
        - Acknowledge you posted the full thread on Bluesky first
        - Frame Twitter as the secondary platform: "full thread on Bluesky 👇"
        - Leave a placeholder [BLUESKY_URL] where the user will paste the Bluesky link
        - DO NOT include a canonical blog URL (the Bluesky post already has it)
        - Output: ONLY the tweet text
        """
    ),
    "tiktok_xref": dedent(
        """\
        Write a SHORT TikTok caption (max 150 chars) that references an existing Clapper post.
        Clapper is the primary platform; TikTok, Douyin, and RedNote are secondary cross-references.
        - Acknowledge the full version is on Clapper first
        - Leave a placeholder [CLAPPER_URL] where the user will paste the Clapper link
        - 2–3 TikTok-friendly hashtags
        - Output: ONLY the caption text
        """
    ),
    "douyin_xref": dedent(
        """\
        Write a Douyin (Chinese TikTok) caption (max 150 chars, UTF-8).
        Douyin is a secondary cross-reference; Clapper is the primary short-form platform.
        - Bilingual: one line in simplified Chinese, one line in English
        - Reference the original Clapper video with placeholder [CLAPPER_URL]
        - 2–3 relevant hashtags in both languages if space allows
        - Output: ONLY the caption text
        """
    ),
    "rednote_xref": dedent(
        """\
        Write a RedNote (小红书 / Xiaohongshu) caption (max 1000 chars).
        RedNote has strong reach with tech-curious and professional audiences.
        Clapper is the primary short-form platform; this is a cross-reference.
        - Engaging lifestyle-adjacent hook (RedNote skews aspirational)
        - Bilingual: body in English, hashtags in both English and Chinese
        - Reference the Clapper video with placeholder [CLAPPER_URL]
        - End with 5–8 hashtags mixing English and Chinese
        - Output: ONLY the caption text
        """
    ),
    "youtube_shorts": dedent(
        """\
        Write a YouTube Shorts caption and on-screen text script (max 100 chars caption).
        YouTube Shorts reposts the same short-form video produced for Clapper.
        - CAPTION: one punchy line (≤100 chars) with 2–3 hashtags, references Clapper [CLAPPER_URL]
        - OVERLAY LINE 1: on-screen hook text (≤6 words)
        - OVERLAY LINE 2: on-screen payoff text (≤8 words)
        - Output: CAPTION line, then OVERLAY LINE 1, then OVERLAY LINE 2
        """
    ),
    "reels_xref": dedent(
        """\
        Write an Instagram Reels caption (max 2200 chars) for a cross-posted Clapper video.
        Instagram Reels is a secondary platform; Pixelfed is the primary image/video platform.
        - Opens with a visual hook or bold statement (Reels audiences scroll fast)
        - 3–4 short sentences; emoji encouraged
        - Reference Clapper original with placeholder [CLAPPER_URL]
        - End with 10–15 hashtags mixing broad (#security) and niche (#zkTLS) terms
        - Output: ONLY the caption text
        """
    ),
    "youtube_script": dedent(
        """\
        Write a narration SCRIPT for a 4–7 minute explainer YouTube video.
        Structure:
          INTRO (30s): hook + what the viewer will learn
          SECTION 1–4 (60–90s each): one concept per section, cued to diagrams
          OUTRO (30s): recap + subscribe CTA + links
        Formatting rules:
          - Prefix each section heading with ## and include a duration hint, e.g. ## INTRO [0:00–0:30]
          - Inline diagram cues in [brackets]: e.g. [show diagram 1 — TLS handshake]
          - Write exactly as spoken: contractions, short sentences, rhetorical questions
          - Mark pauses as [PAUSE] and emphasis as *word*
        Output: Markdown with the structure above
        """
    ),
    "youtube_description": dedent(
        """\
        Write a YouTube video description (max 5000 chars).
        Sections (separated by blank lines):
          1. Hook paragraph (2–3 sentences)
          2. What you'll learn (bullet list, 4–6 items)
          3. Chapters placeholder — output the literal text: CHAPTERS_PLACEHOLDER
          4. Links: canonical blog post URL, related posts (placeholder [RELATED_URL])
          5. About the channel (2 sentences)
          6. Hashtags: 8–10 relevant tags
        Output: plain text; no Markdown heading syntax (YouTube ignores it)
        """
    ),
    "youtube_chapters": dedent(
        """\
        Write a YouTube chapters list matching the narration script sections.
        Format (one chapter per line): MM:SS Title
        Start at 00:00. Estimate realistic durations for a 4–7 minute video.
        Output: ONLY the chapter lines, no extra text
        """
    ),
}


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

    if dry_run:
        for variant_key, out_path in tasks:
            print(f"  [dry-run] would generate {variant_key} -> {out_path.relative_to(post_dir)}")
        return

    backend = resolve_backend()
    print(f"LLM backend: {describe_backend(backend)}")

    variants_dir.mkdir(exist_ok=True)
    youtube_dir.mkdir(exist_ok=True)

    results: dict[str, str] = {}
    for variant_key, out_path in tasks:
        print(f"  Generating {variant_key}...", flush=True)
        spec = PLATFORM_SPECS[variant_key]
        text = complete(source_md, spec, canonical_url, backend=backend)
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
        "variants": {k: str(p.relative_to(post_dir)) for k, p in tasks},
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
