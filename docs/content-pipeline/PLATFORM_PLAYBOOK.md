# Platform content playbook

How the content pipeline shapes each variant. Specs live in `agents/content-pipeline/platform_specs.py`; regenerate with `generate_variants.py`.

**Principle:** Optimize **format and feed mechanics** per channel. Do not clone another writer's voice — LinkedIn uses a Brian Krebs–style *link-post structure* only.

---

## LinkedIn

**Format model:** Short text + Open Graph link card (article carries depth).

| Practice | Why |
|----------|-----|
| 100–180 words above the card | Mobile "see more" cuts ~140–210 chars; card does the rest |
| Hook → `From the post:` → one quote → URL alone | Krebs-style link posts; one URL triggers preview |
| 2–3 inline `#CamelCase` hashtags in hook | Avoid hashtag walls; algorithm favors dwell + comments |
| Specific closing question | Comments in first 60–90 min boost distribution |
| **Avoid** long essays, H2 headers, multiple URLs | Common LLM failure mode |

Sources: [Neal Schaffer 2026](https://nealschaffer.com/linkedin-post/), [Share Preview OG](https://www.share-preview.com/blog/linkedin-link-preview)

---

## Bluesky

| Practice | Why |
|----------|-----|
| **150–220 characters** (hard cap 300) | Engagement sweet spot on AT Protocol feeds |
| Hook in first sentence; URL on last line | Front-loaded scans on mobile |
| 0–2 hashtags; rewrite for Bluesky | Verbatim LinkedIn cross-posts underperform |
| Conversational infosec tone | Reply culture > broadcast |

Sources: [Monolit Bluesky length 2026](https://monolit.sh/blog/how-long-should-bluesky-post-be-2026-data-backed-answer-founders), [BluePilot growth guide](https://getbluepilot.com/blog/how-to-grow-on-bluesky)

---

## Mastodon (infosec.exchange)

| Practice | Why |
|----------|-----|
| `CW:` first line with **hashtags inside CW** | Hidden-body tags are not searchable ([wiki](https://wiki.infosec.exchange/faq/read_discover/common_hashtags)) |
| `#CamelCase` tags | Screen reader accessibility |
| 2–4 sentences + URL after blank line | Instance expects accurate CWs for sensitive topics |

Sources: [Infosec.Exchange CW FAQ](https://wiki.infosec.exchange/faq/post_share/content_warning_when_to_use)

---

## Pixelfed

| Practice | Why |
|----------|-----|
| Line 1 = image/diagram description | Image-first network |
| 5–8 focused hashtags | Less spammy than Instagram-max dumps |
| Short paragraphs + light emoji leaders | Mobile scanability |

---

## Clapper (primary short video)

| Practice | Why |
|----------|-----|
| `HOOK:` ≤8 words for first 3 seconds | Short-form retention |
| `TALK:` bullets for narration | Parsed by pipeline |
| `CAPTION:` keyword in first 100 chars | Discovery / SEO parallel to TikTok |

---

## TikTok / YouTube Shorts (xref / repost)

| Platform | Practice |
|----------|----------|
| TikTok xref | ≤150 chars; keyword first 40 chars; 3–5 hashtags at end; `[CLAPPER_URL]` |
| YouTube Shorts | `CAPTION:` ≤100 chars + `#Shorts`; `OVERLAY:` lines for on-screen text |

Sources: [TikTok caption SEO 2026](https://monolit.sh/blog/how-long-tiktok-caption-2026-data-backed-answer-founders), [YouTube Shorts description guide](https://ghostshorts.com/blog/how-to-write-youtube-shorts-description-2026)

---

## YouTube long-form

| Piece | Practice |
|-------|----------|
| Description | First **125 chars** = hook + primary keyword (mobile "Show more") |
| Script | Spoken sentences ≤15 words; `## SECTION [timestamp]` |
| Chapters | `MM:SS Title` lines |

---

## Cross-platform hierarchy

1. **blog.pcioasis.com** — canonical source (`index.md`)
2. **Bluesky / Mastodon** — primary micro-social
3. **Clapper** — primary short video
4. **LinkedIn** — professional link card
5. **Twitter, TikTok, Douyin, RedNote, Reels** — xref only (placeholders in variants)

---

## Regenerating after spec changes

```bash
cd ~/projectos/pcioasis-blog
uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_variants.py \
  content/posts/SECTION/SLUG
```

Review in `preview_server.py` before `assemble_pr.py`.
