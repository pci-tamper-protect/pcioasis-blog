# Multi-Platform Content Distribution Pipeline

**Source of truth:** `pcioasis-blog` (Hugo, `~/projectos/pcioasis-blog`)
**Last updated:** 2026-06-02

## Goal

Author once in `pcioasis-blog`. Automatically generate audience-targeted variants for every platform. Human reviews all content in a PR before anything publishes.

---

## Publishing hierarchy

```
pcioasis-blog/content/posts/<section>/<slug>/index.md
    │
    ├── blog.pcioasis.com          (Hugo/GitHub Pages — canonical SEO source)
    ├── planetkesten.com/blog      (React SPA + Cloudflare Worker — broadest audience)
    └── kbroughton.github.io       (Hugo — most technical audience)
```

---

## Platform coverage

| Phase | Platform | Role | Ethical? |
|---|---|---|---|
| 1 | **pcioasis-blog** | Source of truth, PR review gate | ✅ |
| 2 | **planetkesten.com** | Blog syndication, broad audience | ✅ |
| 2 | **kbroughton.github.io** | Blog syndication, technical audience | ✅ |
| 4 | **Bluesky** | Micro-social primary | ✅ primary |
| 4 | **Mastodon** (infosec.exchange/@BHINFOSECURITY) | Micro-social primary | ✅ primary |
| 4 | **Pixelfed** | Image/visual primary | ✅ primary |
| 4 | **Clapper** | Short-form video **primary** (US/TX-origin) | ✅ primary |
| 4 | **LinkedIn** | Professional/B2B | ✅ |
| 4 | **PeerTube** (tilvids.com) | Long-form video primary | ✅ primary |
| 5 | **Twitter/X** | Xref from Bluesky (manual) | ⚠️ xref only |
| 5 | **TikTok** | Xref from Clapper | ⚠️ xref only |
| 5 | **Douyin** | Xref from Clapper (bilingual) | ⚠️ xref only |
| 5 | **RedNote (小红书)** | Xref from Clapper | ⚠️ xref only |
| 5 | **YouTube Shorts** | Reposts Clapper video | ⚠️ xref only |
| 5 | **Instagram Reels** | Reposts Clapper video | ⚠️ xref only |
| 5 | **YouTube** | Long-form narrated video | ⚠️ secondary |
| 5 | **Facebook** | Xref from Mastodon | ⚠️ xref only |
| 5 | **Instagram** | Xref from Pixelfed | ⚠️ xref only |

**Publishing order:** Clapper (short-form) → Bluesky + Mastodon + Pixelfed + LinkedIn → 24h wait → all dominant-platform xrefs

---

## Repository layout

```
pcioasis-blog/
├── content/posts/<section>/<slug>/
│   ├── index.md                  ← source article
│   └── _variants/                ← generated; gitignored on main, committed only on content/*-variants branches
│       ├── manifest.json
│       ├── planetkesten.md
│       ├── kbroughton.md
│       ├── linkedin.md
│       ├── bluesky.txt
│       ├── mastodon.txt
│       ├── pixelfed.txt
│       ├── clapper.txt           ← primary short-form
│       ├── tiktok-xref.txt
│       ├── douyin-xref.txt
│       ├── rednote-xref.txt
│       ├── youtube-shorts.txt
│       ├── reels-xref.txt
│       ├── twitter-xref.txt
│       └── youtube/
│           ├── script.md
│           ├── description.md
│           └── chapters.txt
│
├── agents/content-pipeline/      ← pipeline lives here (content-repo-local)
│   ├── generate_variants.py      ← Phase 1: Claude API → all text variants
│   ├── preview_server.py         ← Phase 1: mobile-friendly local preview
│   ├── assemble_pr.py            ← Phase 1: commit variants + open review PR
│   ├── pyproject.toml / uv.lock
│   ├── ai_backend.py / env_help.py
│   └── tests/
│       └── test_generate_variants.py
│
└── .github/workflows/
    ├── deploy.yml                ← Hugo → GitHub Pages
    ├── sync-to-planetkesten.yml  ← sync to planet-kesten-site (uses pcioasis-ops script)
    └── generate-content-variants.yml  ← Phase 1: trigger on index.md push
```

General-purpose infra agents (SDLC indexer, MCP server) remain in `pcioasis-ops`.

---

## Phases

### Phase 1 — Text variant generation ✅ BUILT

**Status:** Complete. 45/45 tests passing.

**What it does:**
- `generate_variants.py` reads `index.md`, calls Claude API (claude-opus-4-7 with prompt caching), writes 16 platform variants into `_variants/`
- `preview_server.py` serves mobile-friendly HTML mockups at `http://<LAN-IP>:5050/` for Android review
- `assemble_pr.py` creates a `content/<slug>-variants` branch and opens a review PR with publish checklist
- `.github/workflows/generate-content-variants.yml` triggers on `content/posts/**/index.md` push to main

**Run locally:**
```bash
cd ~/projectos/pcioasis-blog
uv sync --project agents/content-pipeline
export ANTHROPIC_API_KEY="…"
uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_variants.py \
  content/posts/zkTLS/zktls-proof-of-provenance
uv run --project agents/content-pipeline \
  python agents/content-pipeline/preview_server.py \
  content/posts/zkTLS/zktls-proof-of-provenance
# open http://<your-IP>:5050/ on Android
uv run --project agents/content-pipeline \
  python agents/content-pipeline/assemble_pr.py \
  content/posts/zkTLS/zktls-proof-of-provenance
```

**Required secrets (CI):** `ANTHROPIC_API_KEY`, `PLANETKESTEN_PAT`

**Local / Azure:** `deploy/secrets/` bootstrap → `eval "$(./deploy/secrets/export-macos-keychain.sh)"` and `AZURE_OPENAI_DEPLOYMENT`. Generator picks Anthropic (`sk-ant-…`) → Azure OpenAI → OpenAI. See `deploy/secrets/README.md`.

---

### Phase 2 — Image pipeline 🔲 TODO

Generate platform-sized image crops from diagrams in the post.

- Input: draw.io PNGs in `content/posts/<section>/<slug>/`
- Output per platform:
  - `_variants/images/og-1200x630.png` — Open Graph / LinkedIn card
  - `_variants/images/square-1080x1080.png` — Instagram / Pixelfed
  - `_variants/images/portrait-1080x1920.png` — Stories / Reels / Shorts
  - `_variants/images/clapper-thumbnail.png` — Clapper cover
- Tools: Pillow for crop + padding; draw.io CLI or export from existing PNGs

---

### Phase 3a — Short video arena (text-to-video shootout) 🔲 IN PROGRESS

Compare **five** cloud APIs (two on Azure Foundry); human picks the best clip for Clapper / Shorts.

| Slot | Provider | Model |
|------|----------|-------|
| 1a | Azure AI Foundry | Sora 2 |
| 1b | Azure AI Foundry | Sora (v1) |
| 2 | Google Vertex AI | Veo 3.1 Fast |
| 3 | AWS Bedrock | Luma Ray 2 |
| 4 | Replicate | MiniMax Hailuo 2.3 |

- Input: `_variants/clapper.txt` + optional diagram PNG in post folder
- Tool: `generate_video_arena.py` → `_variants/video-arena/{provider}/video.mp4` + `review.html`
- Preview: `preview_server.py` → `http://<LAN-IP>:5050/arena` (mobile review alongside text variants)
- Human: score in browser, write `WINNER.txt`, copy to `_variants/clapper/clip.mp4`
- Docs: `docs/content-pipeline/VIDEO_ARENA.md`

### Phase 3b — Long-form video (slides + narration) 🔲 TODO

Narrated YouTube video from HTML slides (separate from T2V arena).

- Input: `_variants/youtube/script.md`, `_variants/youtube/chapters.txt`, HTML animation frames
- Steps:
  1. ElevenLabs (or local Coqui/Kokoro) generates narration MP3 from script
  2. Playwright records HTML animation slides as MP4 segments
  3. ffmpeg assembles: slides + narration + text overlays → final MP4
- Output: `_variants/youtube/video.mp4`

---

### Phase 4 — Ethical-first publish agents 🔲 TODO

Automated publishing to ethical/primary platforms after PR merge.

- Trigger: workflow `publish-ethical-first.yml` (manual dispatch or PR merge)
- Agents:
  - `publish_bluesky.py` — AT Protocol API, posts thread from `bluesky.txt`
  - `publish_mastodon.py` — Mastodon API (infosec.exchange), posts `mastodon.txt`
  - `publish_pixelfed.py` — Pixelfed API, posts image + `pixelfed.txt`
  - `publish_clapper.py` — Clapper API (TBD), uploads short clip + `clapper.txt`
  - `publish_linkedin.py` — LinkedIn API, posts `linkedin.md`
  - `publish_peertube.py` — PeerTube API (tilvids.com), uploads long-form video

---

### Phase 5 — Cross-reference agents 🔲 TODO

After ethical-first platforms are live (≥24h), post xrefs to dominant platforms.

- Agents:
  - `xref_twitter.py` — posts `twitter-xref.txt` (manual review gate recommended)
  - `xref_tiktok.py` — posts `tiktok-xref.txt` with Clapper URL
  - `xref_douyin.py` — posts `douyin-xref.txt` (bilingual)
  - `xref_rednote.py` — posts `rednote-xref.txt`
  - `xref_youtube_shorts.py` — uploads Clapper clip to YouTube Shorts
  - `xref_reels.py` — uploads Clapper clip to Instagram Reels
  - `xref_facebook.py` — posts xref from Mastodon post
  - `xref_instagram.py` — posts xref from Pixelfed post

---

## Secrets needed

| Secret | Where | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | pcioasis-blog repo | Phase 1 variant generation |
| `PLANETKESTEN_PAT` | pcioasis-blog repo | PR creation, planet-kesten-site checkout |
| `ELEVENLABS_API_KEY` | pcioasis-blog repo | Phase 3 narration |
| `BLUESKY_IDENTIFIER` + `BLUESKY_APP_PASSWORD` | pcioasis-blog repo | Phase 4 |
| `MASTODON_ACCESS_TOKEN` | pcioasis-blog repo | Phase 4 |
| `PIXELFED_ACCESS_TOKEN` | pcioasis-blog repo | Phase 4 |
| `LINKEDIN_ACCESS_TOKEN` | pcioasis-blog repo | Phase 4 |
| `PEERTUBE_TOKEN` | pcioasis-blog repo | Phase 4 |
| `YOUTUBE_OAUTH_CLIENT_ID` | pcioasis-blog repo | Phase 6 cross-linking |
| `YOUTUBE_OAUTH_CLIENT_SECRET` | pcioasis-blog repo | Phase 6 cross-linking |
| `YOUTUBE_OAUTH_REFRESH_TOKEN` | pcioasis-blog repo | Phase 6 cross-linking |

---

### Phase 6 — Post-deploy cross-linking agent 🔲 TODO (separate PR)

After both the blog post and the long-form YouTube video are live and have public URLs, stitch them together automatically.

**Trigger:** workflow `crosslink-post-deploy.yml` — manual dispatch with inputs:
- `slug` (e.g. `zktls-proof-of-provenance`)
- `youtube_video_id` (e.g. `dQw4w9WgXcQ`)

**State contract:** Phase 4/5 publish agents write URLs back into `_variants/manifest.json`:
```json
{
  "published": {
    "youtube_video_id": "...",
    "bluesky_post_url": "https://bsky.app/profile/.../post/...",
    "linkedin_post_url": "...",
    ...
  }
}
```
The cross-linker reads this manifest — no separate state store needed.

**Agent: `crosslink.py`**

Steps (all idempotent — safe to re-run):

1. **YouTube → blog**: POST a pinned YouTube comment via YouTube Data API v3:
   > "Full write-up + diagrams: <canonical_url> #PCI #zkTLS"

2. **Blog → YouTube**: Open a PR that patches `index.md` to append a Hugo shortcode:
   ```
   {{< youtube VIDEO_ID >}}
   ```
   Branch: `content/<slug>-crosslink`, PR title: "Add YouTube embed to <slug>"

3. **Bluesky reply**: Post a reply to the original Bluesky post:
   > "🎥 Video is live: <youtube_url>"

4. **LinkedIn update** (optional): If LinkedIn API supports post edits, append video link; otherwise skip (LinkedIn posts are not easily editable after 24h).

**APIs needed:**

| Action | API | Auth |
|---|---|---|
| Post YouTube comment | YouTube Data API v3 `commentThreads.insert` | OAuth 2.0, `youtube.force-ssl` scope |
| Create GitHub PR | GitHub REST / `gh` CLI | `PLANETKESTEN_PAT` (existing) |
| Bluesky reply | AT Protocol `com.atproto.repo.createRecord` | existing `BLUESKY_APP_PASSWORD` |

**New secrets needed:**

| Secret | Where |
|---|---|
| `YOUTUBE_OAUTH_CLIENT_ID` | pcioasis-blog repo |
| `YOUTUBE_OAUTH_CLIENT_SECRET` | pcioasis-blog repo |
| `YOUTUBE_OAUTH_REFRESH_TOKEN` | pcioasis-blog repo |

**Design notes:**
- YouTube comment is the highest-value action (permanent, on-platform, drives blog traffic)
- Blog PR preserves human review gate for `index.md` changes
- Agent must verify the YouTube video is actually public before posting (handle `processingStatus != "succeeded"`)
- Bluesky threading: need to record the root post's `uri` + `cid` in manifest during Phase 4

---

## Open decisions

- [ ] Clapper API availability — may need to be manual upload with generated script
- [ ] PeerTube instance: using tilvids.com (educational/tech reach)
- [ ] kbroughton.github.io Hugo sync: add Hugo-format output mode to `sync_blog_posts.py` in pcioasis-ops, or add a second sync agent here?
- [ ] `sync_blog_posts.py` currently lives in pcioasis-ops; move to pcioasis-blog for consistency?
- [ ] Phase 6: YouTube OAuth refresh token must be pre-authorized interactively; decide where to store and rotate it (GCP Secret Manager vs GitHub secret)
- [ ] Phase 6: LinkedIn post edits are blocked after 24h — accept skip or find workaround
- [ ] Phase 6: Bluesky root post `uri`+`cid` must be persisted in manifest during Phase 4 publish step (add to `publish_bluesky.py` contract)
