"""Per-platform generation specs for the content pipeline.

Each spec defines FORMAT and distribution mechanics for one output file — not a
writer's voice. Follow output contracts exactly; downstream agents parse prefixes.

Research notes: docs/content-pipeline/PLATFORM_PLAYBOOK.md
"""

from __future__ import annotations

from textwrap import dedent

MASTODON_ACCOUNT = "@BHINFOSECURITY@infosec.exchange"
BLUESKY_LIMIT = 300
BLUESKY_TARGET_MIN = 150
BLUESKY_TARGET_MAX = 220
MASTODON_LIMIT = 500
CLAPPER_LIMIT = 2200
TIKTOK_XREF_LIMIT = 150
TWITTER_LIMIT = 280
YOUTUBE_SHORTS_CAPTION_LIMIT = 100

# Shared rules prepended to every variant prompt (voice stays author's; format varies).
_PLATFORM_PREAMBLE = dedent(
    """\
    You are adapting ONE source blog post for a specific distribution channel.
    - Optimize for that platform's feed mechanics (length, hooks, hashtags, link cards).
    - Do NOT imitate another author's voice or prose style — only structural format when cited.
    - Do NOT paste the full article; compress to what performs on that platform.
    - Use facts from the source only; do not invent incidents or quotes.
    """
)

PLATFORM_SPECS: dict[str, str] = {
    "planetkesten": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: planetkesten.com blog (general-interest personal blog).

        Audience: smart non-specialists; zero assumed PCI/payments background.
        SKIP only dry PCI audit checklists with no human story — output exactly:
          SKIP: topic is too PCI/compliance-specific for planetkesten.com
        When in doubt, write the variant.

        Performance patterns:
        - Lead with a relatable hook ("this affects real people")
        - Mobile: 2–3 sentences per paragraph; subheadings every 150–200 words
        - Define jargon inline once; friendly curious tone

        Length: 600–900 words.

        REQUIRED output format:
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars, og:description>
          Line 2: blank
          Lines 3+: Markdown with H1 title, intro, 3–5 sections
        """
    ),
    "kbroughton": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: kbroughton.github.io (senior engineer / security research blog).

        SKIP only pure PCI procedural checklists with no technical mechanism — output exactly:
          SKIP: topic is too compliance-procedural for kbroughton.github.io
        When in doubt, write the variant.

        Performance patterns:
        - Lead with the sharpest technical insight or surprising finding
        - RFC/CVE/spec references by number; implementation and threat-model detail
        - Dry precise tone; short paragraphs; code blocks where relevant
        - Mobile-friendly: short paragraphs (2–3 sentences), code blocks for anything executable

        Length: 800–1200 words.

        REQUIRED output format:
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars>
          Line 2: blank
          Lines 3+: Markdown with H1 and structured sections
        """
    ),
    "linkedin": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: LinkedIn feed (security professionals + executives).

        STRUCTURAL FORMAT (Brian Krebs–style link post — FORMAT ONLY, not his voice):
        LinkedIn shows ~140–210 characters before "see more"; the link preview card carries
        the article. Write SHORT text above the card, not a long essay.

        Required skeleton (100–180 words total for body after META_DESCRIPTION):
          1) Hook paragraph (2–3 sentences): what happened + why it matters NOW.
             Open on the most alarming/surprising fact. Not background history.
          2) Literal line: From the post:
          3) One pull-quote sentence — the single most striking line from the source (in quotes).
          4) Blank line, then canonical URL ALONE on its own line (triggers OG link card).
             No other URLs in the body. You may omit the raw URL from the hook if the card suffices.

        Distribution rules (2026):
        - 2–3 hashtags inline in the hook paragraph (#CamelCase), not a hashtag wall at the end
        - Short paragraphs with blank lines (mobile dwell time); no markdown H2/H3 in body
        - First-person or third-person newsroom tone; never promotional ("excited to share")
        - End with a specific question to invite comments (not "Thoughts?")
        - Do NOT summarize the whole article — the card + blog do that

        FORBIDDEN (common LLM mistakes):
        - Long executive essays, bullet lists of "business impact", emoji section headers
        - Multiple URLs, "link in comments", or pasted blog paragraphs
        - More than 180 words in the post body

        REQUIRED output format:
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars>
          Line 2: blank
          Lines 3+: LinkedIn body per skeleton above; canonical URL last line alone
        """
    ),
    "bluesky": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: Bluesky (@at-protocol microblog).

        Hard limit: {BLUESKY_LIMIT} characters including spaces and URL.
        Engagement sweet spot: {BLUESKY_TARGET_MIN}–{BLUESKY_TARGET_MAX} characters — aim there.

        Performance patterns (2026):
        - Front-load hook in first sentence (≤12 words); no throat-clearing
        - One sharp opinion or fact + one "so what" line; URL on its own last line
        - 0–2 hashtags inline (#CamelCase); never 5+ hashtag dumps
        - Conversational infosec peer tone — NOT a trimmed LinkedIn essay
        - Do not cross-post verbatim from LinkedIn/Twitter; rewrite for Bluesky norms
        - If the idea needs >{BLUESKY_LIMIT} chars, compress — do not mention threading unless
          the user will thread manually (this generator outputs a single post only)

        Output: ONLY the post text, no commentary.
        """
    ),
    "mastodon": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: Mastodon {MASTODON_ACCOUNT} on infosec.exchange.

        Hard limit: {MASTODON_LIMIT} characters total.

        Instance rules (infosec.exchange wiki):
        - Line 1 MUST be: CW: <accurate one-line content warning for the topic>
        - Put ALL discoverable hashtags inside the CW line (hashtags in hidden body are NOT searchable)
        - Use #CamelCase for multi-word tags (#ThreatIntel not #threatintel)
        - Blank line after CW, then 2–4 short sentences of technical substance
        - End with canonical URL on its own line

        Performance patterns:
        - Assume infosec-savvy readers; precise terms OK
        - Prefer 1–3 relevant tags (#infosec #DFIR #PCI etc.) in the CW line only
        - Mobile-friendly short sentences; emoji sparingly (0–2 max)

        Output: ONLY the post text including CW: prefix.
        """
    ),
    "pixelfed": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: Pixelfed (fediverse image post — Instagram-like).

        Performance patterns:
        - Line 1: visual alt-text style description of the hero diagram/image (what viewers see)
        - 2–3 short paragraphs (≤2 sentences each); emoji at paragraph start for scanability
        - Mobile-friendly: thumb-scroll scannability with short paragraphs and line breaks
        - Canonical URL before the hashtag block
        - 5–8 focused hashtags on final line (#CamelCase mix of broad + niche)
        - Do not write a blog excerpt; caption complements the image

        Max ~2200 characters.

        Output: ONLY the caption text.
        """
    ),
    "clapper": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: Clapper short-form video (US-first; primary short-video platform).

        Max {CLAPPER_LIMIT} characters in CAPTION. Video hook is the first 3 seconds on screen.

        Performance patterns:
        - HOOK overlay ≤8 words — pattern interrupt, not a title card
        - 3–5 TALK bullets: spoken lines, simple words, one idea each (curious adults, not PhDs)
        - CAPTION: keyword in first 100 chars; conversational; 3–5 hashtags; ends with canonical URL

        REQUIRED output format (agents parse prefixes):
          HOOK: <≤8 words on-screen>
          TALK: <point 1>
          TALK: <point 2>
          ... (3–5 TALK lines)
          <blank line>
          CAPTION: <caption text>
        """
    ),
    "twitter_xref": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: Twitter/X cross-reference (secondary to Bluesky).

        Max {TWITTER_LIMIT} characters.

        Performance patterns:
        - Bluesky is primary: "full thread on Bluesky" or similar
        - One-line hook + placeholder [BLUESKY_URL] — NO canonical blog URL here
        - Optional single question to drive replies
        - 0–1 hashtag max (Twitter hashtags weak in 2026)

        Output: ONLY the tweet text.
        """
    ),
    "tiktok_xref": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: TikTok caption (secondary cross-ref to Clapper primary video).

        Max {TIKTOK_XREF_LIMIT} characters.

        Performance patterns:
        - Primary keyword in first 40 characters (TikTok SEO weights opening)
        - "Full video on Clapper" + placeholder [CLAPPER_URL]
        - 3–5 hashtags at END: 1 broad + 1 niche + 1 topic (#cybersecurity style)
        - Caption hook must work before play (many users read caption first)

        Output: ONLY the caption text.
        """
    ),
    "douyin_xref": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: Douyin 抖音 (secondary cross-ref to Clapper).

        Max ~150 characters UTF-8.

        Performance patterns:
        - Line 1: simplified Chinese hook; Line 2: English gloss
        - [CLAPPER_URL] placeholder; 2–3 hashtags if space (CN + EN)

        Output: ONLY the caption text.
        """
    ),
    "rednote_xref": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: RedNote 小红书 (secondary cross-ref to Clapper).

        Max ~1000 characters.

        Performance patterns:
        - Lifestyle-adjacent hook (aspirational framing) even for tech topics
        - 1–2 sentences per paragraph; generous line breaks for mobile
        - English body; hashtags mix English + Chinese on last lines
        - [CLAPPER_URL] placeholder

        Output: ONLY the caption text.
        """
    ),
    "youtube_shorts": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: YouTube Shorts (reposts Clapper video).

        Performance patterns:
        - CAPTION ≤{YOUTUBE_SHORTS_CAPTION_LIMIT} chars: keyword-first sentence + 2–3 hashtags + [CLAPPER_URL]
        - Include #Shorts among hashtags
        - OVERLAY lines = on-screen text for first 3 seconds (≤6 and ≤8 words)
        - Do not write multi-paragraph descriptions (Shorts descriptions are collapsed)

        REQUIRED output format:
          CAPTION: <text>
          OVERLAY: <≤6 words>
          OVERLAY: <≤8 words>
        Output: exactly those three labelled lines.
        """
    ),
    "reels_xref": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: Instagram Reels (secondary; Pixelfed is primary image/video fediverse).

        Max ~2200 characters.

        Performance patterns:
        - Bold visual hook line 1 (scroll-stopper)
        - 1–2 sentences per paragraph; emoji paragraph leaders
        - Mobile-first: short paragraphs for fast Reels scroll feeds
        - [CLAPPER_URL] placeholder; 8–12 hashtags (broad #cybersecurity + niche)

        Output: ONLY the caption text.
        """
    ),
    "youtube_script": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: YouTube long-form narration (4–7 minutes).

        Performance patterns:
        - Retention: hook in first 15 seconds; pattern breaks every 60–90s
        - Spoken sentences ≤15 words; [PAUSE] and *emphasis* markers
        - Diagram cues: [show diagram N — label]

        Structure:
          ## INTRO [0:00–0:30]
          ## SECTION … [timestamps]
          ## OUTRO […]

        Output: Markdown script only.
        """
    ),
    "youtube_description": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: YouTube video description (SEO + mobile).

        Performance patterns:
        - First 125 characters = hook + primary keyword (visible before "Show more" on mobile)
        - Bulleted "What you'll learn" (4–6 items)
        - Literal line: CHAPTERS_PLACEHOLDER
        - Links section with canonical blog URL
        - 8–10 hashtags; YouTube weights first 3 for video tags
        - Plain text only (no ## headings — YouTube ignores them)

        Max 5000 characters.

        Output: plain text description.
        """
    ),
    "youtube_chapters": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: YouTube chapter timestamps.

        Format: MM:SS Title (one per line, start 00:00).
        Match youtube_script sections; realistic durations for 4–7 min video.

        Output: ONLY chapter lines.
        """
    ),
    "facebook": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: Facebook (community/civic feed post).

        First 2–3 lines are visible before "see more" (~300 chars) — write them as a
        standalone hook. Optimal body: 80–250 words; link card auto-attaches.

        Performance patterns (2026):
        - Concrete local impact > abstract policy; name the place and the people
        - Conversational, community tone; end with a question to drive comments
        - 1–2 hashtags MAX inline; no hashtag dumps (minimal algorithmic weight in 2026)
        - One canonical URL alone on its own last line (triggers link preview card)
        - Share-worthy framing: "Here's what this means for [place]"

        REQUIRED output format:
          Line 1: META_DESCRIPTION: <one sentence, ≤155 chars>
          Line 2: blank
          Lines 3+: Facebook post body (80–250 words); canonical URL on last line alone
        """
    ),
    "threads": _PLATFORM_PREAMBLE
    + dedent(
        f"""\
        CHANNEL: Threads (Meta text platform; Instagram-connected audience).

        Hard limit: 500 characters per post. This generator outputs a single post.

        Performance patterns (2026):
        - No hashtags (Threads deprioritizes them; no hashtag search as of 2026)
        - Casual, first-person or conversational tone; warmer than Bluesky
        - Front-load the hook; end with a question or conversation invite
        - URL on its own line triggers link preview — no need to describe the link
        - Cross-audience: Instagram followers see Threads; write for general audience

        Output: ONLY the post text (≤500 chars).
        """
    ),
    "snapchat": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: Snapchat Spotlight (short vertical video, 5–60 sec).

        Hard limit: 140 characters for caption. NO external URLs (Spotlight blocks them).
        Audience: 13–34, trend-driven, fast consumption.

        Performance patterns (2026):
        - HOOK: on-screen text in first 2 seconds — ≤6 words, curiosity-gap or punchy claim
        - TALK: 3–4 spoken lines, ≤8 words each, plain language
        - Caption: keyword-first, 1–2 emoji, 2–3 hashtags from Snapchat trending topics
        - No links; close with brand or account name

        REQUIRED output format (agents parse prefixes):
          HOOK: <≤6 words on-screen>
          TALK: <point 1>
          TALK: <point 2>
          TALK: <point 3>
          CAPTION: <≤140 chars, no URL>
        """
    ),
    "tiktok": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: TikTok (primary short-form video, 30–60 seconds).

        Performance patterns (2026):
        - Hook: first 3 seconds on screen must open a curiosity gap or pattern interrupt
        - Spoken script: conversational, ≤12 words per sentence, present tense
        - Build to a payoff: reveal or "wait for it" structure outperforms lectures
        - CTA: follow for part 2 or open a question to comments
        - Caption: 150 chars max; primary keyword in first 40 chars
        - Use 3–5 topic-specific hashtags (1 broad + 2 niche + 1 trending); skip #fyp in 2026

        REQUIRED output format (agents parse prefixes):
          HOOK: <≤8 words on-screen text>
          SCRIPT: <full spoken narration — one sentence per line, 30–60 sec worth>
          CTA: <call to action, 1 line>
          CAPTION: <≤150 chars>
        """
    ),
    "capcut": _PLATFORM_PREAMBLE
    + dedent(
        """\
        CHANNEL: CapCut long2short edit script (AI clip extraction from long-form source).

        Identify 3–5 shareable 15–30 second clip segments. For each clip provide a
        structured block using the prefixes below so CapCut's API or a human editor
        can ingest it directly.

        REQUIRED output format:
          CLIP 1: <topic label>
          HOOK: <≤8 words on-screen overlay for first 2 sec>
          SPOKEN: <key lines from source — one sentence per line, 15–30 sec worth>
          OVERLAY: <on-screen text caption line 1>
          OVERLAY: <on-screen text caption line 2>
          TRANSITION: <cut | smash cut | fade>

          CLIP 2: ...
          (3–5 clips total)

          SHARED_CAPTION: <≤150 chars caption for all clips when cross-posted>
        """
    ),
}
