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

# Output format contract used by downstream publish agents:
#
#   Blog variants (planetkesten, kbroughton):
#     First line: META_DESCRIPTION: <≤155 chars>
#     Then a blank line, then the Markdown body.
#
#   LinkedIn:
#     First line: META_DESCRIPTION: <≤155 chars>
#     Then the plain-text body.
#
#   Clapper:
#     HOOK: <≤8 words>
#     TALK: <bullet 1>
#     ...
#     TALK: <bullet N>
#     <blank line>
#     CAPTION: <caption text ending with canonical URL>
#
#   YouTube Shorts:
#     CAPTION: <≤100 chars + hashtags + [CLAPPER_URL]>
#     OVERLAY: <≤6 words>
#     OVERLAY: <≤8 words>
#
#   Mastodon: CW: on first line (existing convention).
#   All others: plain text with canonical URL on last line.

PLATFORM_SPECS = {
    "planetkesten": dedent(
        """\
        Write a blog-length article (600–900 words) adapted for a GENERAL audience at planetkesten.com.
        - Assume zero background in PCI, payments, or infosec
        - Lead with a relatable real-world hook (e.g. "ever wondered how your credit card is protected?")
        - Avoid jargon; when technical terms are unavoidable, define them inline
        - Friendly, curious tone — like explaining to a smart friend, not a colleague
        - Mobile-friendly: keep paragraphs to 2–3 sentences max; use subheadings every 150–200 words
        - Preserve key takeaways and diagrams (reference them as "[diagram N]")
        REQUIRED output format (agents parse this):
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars, suitable for og:description>
          Line 2: blank
          Lines 3+: valid Markdown with an H1 title, introduction, and 3–5 sections
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
        - Mobile-friendly: short paragraphs (2–3 sentences), code blocks for anything executable
        REQUIRED output format (agents parse this):
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars, suitable for og:description>
          Line 2: blank
          Lines 3+: valid Markdown with an H1 title and structured sections
        """
    ),
    "linkedin": dedent(
        """\
        Write a SHORT LinkedIn post in the style of Brian Krebs on krebsonsecurity.com.
        Model: 2-3 sentence hook describing what happened and why it matters, then a
        "From the post:" pull quote (the single most striking sentence from the source),
        then the canonical URL on its own line (LinkedIn auto-generates the card).
        Total length: 100-180 words MAX — the link card carries the rest.
        Rules:
        - Open with the most alarming or surprising fact, not background
        - Readers are security professionals and executives — no hand-holding
        - First-person or third-person, not promotional
        - "From the post:" label is literal — use those exact words before the quote
        - Canonical URL goes last, alone on its own line — NO other URLs in the body
        - 2-3 hashtags ONLY, inline in the hook paragraph (not a wall at the end)
        - Do NOT write a long essay; brevity is the entire point of this format
        REQUIRED output format (agents parse this):
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars, suitable for og:description>
          Line 2: blank
          Lines 3+: the short post body ending with the canonical URL on its own line
        """
    ),
    "bluesky": dedent(
        f"""\
        Write a Bluesky post — MAXIMUM {BLUESKY_LIMIT} characters including spaces.
        - Hook in first sentence (≤10 words), context in second, call-to-action in third
        - End with the canonical URL as a plain link on its own line
        - Include 2–3 relevant hashtags inline (not at the end)
        - Tone: sharp and opinionated; infosec community audience
        - Mobile-first: reads well as a single glance on a small screen
        - Output: ONLY the post text, no extra commentary
        """
    ),
    "mastodon": dedent(
        f"""\
        Write a Mastodon post for {MASTODON_ACCOUNT} on infosec.exchange — MAXIMUM {MASTODON_LIMIT} characters.
        - First line MUST be: CW: <one-line content warning summarising the topic>
        - Blank line after CW, then the post body
        - Assume infosec-savvy readers; technical depth welcome
        - Mobile-friendly: short sentences, emoji sparingly for visual anchoring
        - Mention any relevant #infosec, #PCI, or topic hashtags
        - End with the canonical URL
        - Output: ONLY the post text including the CW line (agents check for CW: prefix)
        """
    ),
    "pixelfed": dedent(
        """\
        Write an image post caption for Pixelfed (Instagram-style, max 2200 chars).
        - Opens with a compelling visual description of the key diagram or concept image
        - 2–4 short paragraphs; mobile-first — max 2 sentences per paragraph
        - Emoji at the start of each paragraph for thumb-scroll scannability
        - Include the canonical URL before the hashtags
        - Ends with 10–15 relevant hashtags on their own line
        - Output: ONLY the caption text
        """
    ),
    "clapper": dedent(
        f"""\
        Write a Clapper short-form video caption/script (max {CLAPPER_LIMIT} chars total).
        Clapper is a US-first, Texas-origin short-video platform. Audience: curious adults, not deep-tech.
        REQUIRED output format (agents parse each prefixed line):
          HOOK: <on-screen text overlay, ≤8 words, punchy>
          TALK: <talking point 1 the creator reads to camera>
          TALK: <talking point 2>
          ... (3–5 TALK lines total)
          <blank line>
          CAPTION: <caption for the post itself; conversational, hashtags welcome, ends with canonical URL>
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
        Clapper is the primary platform; TikTok is a secondary cross-reference.
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
        - Mobile-first: 1–2 sentence paragraphs, line breaks for breathing room
        - Bilingual: body in English, hashtags in both English and Chinese
        - Reference the Clapper video with placeholder [CLAPPER_URL]
        - End with 5–8 hashtags mixing English and Chinese
        - Output: ONLY the caption text
        """
    ),
    "youtube_shorts": dedent(
        """\
        Write a YouTube Shorts caption and on-screen text script.
        YouTube Shorts reposts the same short-form video produced for Clapper.
        REQUIRED output format (agents parse each prefixed line):
          CAPTION: <≤100 chars + 2–3 hashtags + [CLAPPER_URL]>
          OVERLAY: <on-screen hook text, ≤6 words>
          OVERLAY: <on-screen payoff text, ≤8 words>
        Output: exactly those three labelled lines, nothing else.
        """
    ),
    "reels_xref": dedent(
        """\
        Write an Instagram Reels caption (max 2200 chars) for a cross-posted Clapper video.
        Instagram Reels is a secondary platform; Pixelfed is the primary image/video platform.
        - Opens with a visual hook or bold statement (Reels audiences scroll fast on mobile)
        - Mobile-first: 1–2 sentences per paragraph, emoji at start of each
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
        Formatting rules (agents and video tools parse these markers):
          - Prefix each section heading with ## and include a duration hint: ## INTRO [0:00–0:30]
          - Diagram cues in square brackets: [show diagram 1 — TLS handshake]
          - Write exactly as spoken: contractions, short sentences, rhetorical questions
          - Mark pauses as [PAUSE] and emphasis as *word*
          - Keep sentences ≤15 words — reads well as on-screen captions on mobile
        Output: Markdown with the structure above
        """
    ),
    "youtube_description": dedent(
        """\
        Write a YouTube video description optimised for SEO and mobile (max 5000 chars).
        Sections (separated by blank lines):
          1. Hook paragraph (2–3 short sentences; first 125 chars show without "Show more" on mobile)
          2. What you'll learn (bullet list, 4–6 items)
          3. Chapters — output the literal text: CHAPTERS_PLACEHOLDER
          4. Links: canonical blog post URL, related posts (placeholder [RELATED_URL])
          5. About the channel (2 sentences)
          6. Hashtags: 8–10 relevant tags (YouTube uses first 3 as video hashtags)
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
