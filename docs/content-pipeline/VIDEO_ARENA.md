# Video arena — multi-provider short-form shootout

Phase 1 generates **text metadata** (`clapper.txt`, `youtube-shorts.txt`, etc.). Phase 3a (this doc) generates **actual MP4 candidates** from five APIs (two on Azure Foundry), then a **human review** step picks one clip for Clapper / Shorts.

Text-to-video quality is inconsistent; treat this as an **arena**, not a single vendor bet.

**Credential setup (API keys, config files, export scripts, local audio tools):** [`deploy/VIDEO_GENERATORS.md`](../../deploy/VIDEO_GENERATORS.md)

---

## Providers (mapped to your credits)

| Slot | Provider | Model | Why this slot | Billing home | Short-form fit |
|------|----------|-------|---------------|--------------|----------------|
| **1a** | **Azure AI Foundry** | **Sora 2** (`sora-2`) | Primary Foundry pick: native audio, image anchor, remix | Azure subscription / Foundry deployment | Clapper / Shorts vertical |
| **1b** | **Azure AI Foundry** | **Sora (v1)** (`sora`) | Second Foundry contender on same endpoint/key — text-only baseline, often wider regional availability than Sora 2 | Same Foundry resource (separate deployment) | A/B vs Sora 2 on identical prompt |
| **2** | **Google Vertex AI** | **Veo 3.1 Fast** (`veo-3.1-fast-generate-001`) | GCP $10k credits; reference images from post diagrams; `9:16` | GCP project billing | Image→video from slide/diagram |
| **3** | **AWS Bedrock** | **Luma Ray 2** (`luma.ray-v2:0`) | $25k Bedrock; async S3 output; 5s/9s `720p` | AWS account (`us-west-2`) | Fast iteration, no Azure lock-in |
| **4** | **Replicate** (comparison lane) | **MiniMax Hailuo 2.3** (`minimax/hailuo-2.3`) | Pay-per-run (~$0.50/6s); no cloud commit; A/B vs big three | Replicate API key | Cheap baseline / second opinion |

**Azure dual deployment:** deploy both `sora` and `sora-2` on the same Foundry OpenAI resource. The arena uses one endpoint/key; Sora 2 reads `AZURE_SORA_MODEL` / `AZURE_OPENAI_DEPLOYMENT`; Sora v1 reads `AZURE_SORA_V1_DEPLOYMENT` (defaults to `sora`). Sora v1 ignores reference images (text→video only on Foundry today).

**Not in the arena (by design):**

- **Amazon Nova Reel** — Legacy on Bedrock; prefer **Luma Ray 2**.
- **“Nano banana”** — If you meant a Gemini image model, that is **not** video; use **Veo** on Vertex for GCP video credits.

---

## Standard arena brief (one prompt per post)

Built from `_variants/clapper.txt` (`HOOK`, `TALK`, `CAPTION`) + optional hero PNG from the post folder.

**Target output:** 5–8s, **9:16**, talking-head or diagram motion, **no on-screen logos**, factual tone (infosec explainer).

**Prompt skeleton:**

```text
Vertical 9:16 short-form explainer, 6 seconds, realistic lighting.
Scene: [one concrete visual from HOOK/TALK].
Camera: slow push-in, stable, no whip pans.
Subject: [diagram / hands-on-laptop / abstract TLS lock — pick one].
Style: documentary tech, not Hollywood, not cartoon.
Audio: subtle room tone only if the API supports native audio.
Avoid: text overlays, watermarks, distorted faces, extra fingers.
```

Each provider adapter adds vendor-specific parameters (resolution, duration, reference image). **Sora v1** runs the same text prompt without the diagram anchor.

---

## Credentials

| Provider | Env vars |
|----------|----------|
| Azure Sora 2 | `eval "$(./deploy/secrets/export-sora.sh)"` → `AZURE_SORA_ENDPOINT`, `AZURE_SORA_API_KEY`, `AZURE_SORA_DEPLOYMENT=sora-2` |
| Azure Sora v1 | Same as Sora 2 endpoint/key + `AZURE_SORA_V1_DEPLOYMENT=sora` (if deployed on that resource) |
| Vertex Veo | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=us-central1`, ADC (`gcloud auth application-default login`) |
| Bedrock Luma | `AWS_REGION=us-west-2`, AWS creds with `bedrock:InvokeModel` + S3 write |
| Replicate | `REPLICATE_API_TOKEN` |

Store secrets via existing `deploy/secrets/` patterns; never commit keys.

---

## Output layout

```text
content/posts/<section>/<slug>/_variants/video-arena/
  manifest.json           # run id, prompts, per-provider status
  prompt.txt              # shared text prompt sent to all providers
  review.html             # human comparison UI (open locally)
  azure_sora/
    job.json
    video.mp4             # or SKIPPED.md
    critique.md           # LLM text critique from prompt + metadata
  azure_sora_v1/
    ...
  vertex_veo/
    thumbnails/
      first_non_black.jpg   # first frame with luma above black threshold
      max_contrast.jpg      # ffmpeg thumbnail filter (sharpest/contrasty)
      scene_01.jpg …        # up to 4 scene-cut frames
    thumbnails.json       # candidate list + selected id
    poster.jpg              # copy of chosen thumbnail (after you pick)
    THUMBNAIL.txt           # selected candidate id
    ...
  bedrock_luma/
    ...
  replicate_hailuo/
    ...
  WINNER.txt              # human fills: provider id + notes (post-review)
```

---

## Human review workflow

1. Run arena (generates up to five MP4s — may take 5–15 min each):

   ```bash
   uv run --project agents/content-pipeline \
     python agents/content-pipeline/generate_video_arena.py \
     content/posts/zkTLS/zktls-proof-of-provenance
   ```

2. Open `review.html` in a browser **or** use the preview server arena tab:

   ```bash
   uv run --project agents/content-pipeline \
     python agents/content-pipeline/preview_server.py POST_DIR
   # http://<LAN-IP>:5050/arena  — same page, streams MP4s for phone review
   ```

3. **Pick a splash thumbnail** per provider (avoids blank Veo lead-in frames):
   - **First non-black** — skips black/fade-in at t=0
   - **Highest contrast** — ffmpeg `thumbnail` filter across the clip
   - **Scene change** — up to 4 frames where `scene` score exceeds threshold
   - In **preview_server** (`/arena`), click a tile to save `poster.jpg` + `THUMBNAIL.txt`
   - Static `review.html` on disk: use preview server to persist, or copy manually

4. Score each candidate (1–5): **motion quality**, **prompt adherence**, **artifacts**, **usable for Clapper without re-edit**.

5. Write winner to `WINNER.txt` (e.g. `vertex_veo`).

6. Copy winner → `_variants/clapper/clip.mp4` and copy `poster.jpg` → `_variants/images/clapper-thumbnail.png` if needed.

7. Proceed with publish PR (Phase 4).

**Optional:** Re-run a single provider after tweaking `prompt.txt`:

```bash
uv run --project agents/content-pipeline \
  python agents/content-pipeline/generate_video_arena.py POST_DIR --only vertex_veo
```

---

## Cost rough-order (per 6s 720p clip)

| Provider | Order of magnitude |
|----------|-------------------|
| Replicate Hailuo 2.3 | ~$0.50–1.00 / clip |
| Bedrock Luma Ray 2 | ~$0.50–1.60 / clip (per-second on Bedrock) |
| Vertex Veo 3.1 Fast | Billed to GCP credits (check Vertex pricing page) |
| Azure Sora 2 | Per-second on Foundry (check deployment meter) |
| Azure Sora v1 | Per-second on Foundry (same resource; compare head-to-head) |

Run arena **once per post** at review-PR time, not on every `index.md` typo.

---

## Implementation status

| Piece | Status |
|-------|--------|
| `VIDEO_ARENA.md` | This doc |
| `generate_video_arena.py` + `video_arena/` package | Built — providers call APIs when creds present |
| `review.html` generator | Built |
| `preview_server` `/arena` tab | Built — serves MP4s for mobile review |
| ffmpeg assembly (narration + slides) | Phase 3b — separate from T2V arena |

---

## References

- [Azure Sora (v1) on Foundry](https://ai.azure.com/catalog/models/sora)
- [Azure Sora 2 on Foundry](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/video-generation)
- [Vertex Veo text-to-video](https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-text)
- [Bedrock Luma Ray 2](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-luma.html)
- [Replicate minimax/hailuo-2.3](https://replicate.com/minimax/hailuo-2.3)
