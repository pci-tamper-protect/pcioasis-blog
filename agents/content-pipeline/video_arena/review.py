"""Generate static HTML comparison page for human video arena review."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable

from video_arena.prompt_store import load_prompt_text
from video_arena.thumbnails import load_thumbnails


def _video_src(provider_id: str, href_for: Callable[[str], str]) -> str:
    return href_for(provider_id)


def _thumbnail_src(
    provider_id: str,
    rel_file: str,
    *,
    thumb_href_for: Callable[[str, str], str] | None,
) -> str:
    if thumb_href_for is not None:
        return thumb_href_for(provider_id, rel_file)
    return f"{provider_id}/{rel_file}"


def _build_thumbnail_picker(
    pid: str,
    sub: Path,
    *,
    thumb_href_for: Callable[[str, str], str] | None,
    api_base: str | None,
) -> str:
    data = load_thumbnails(sub)
    if not data or not data.get("candidates"):
        err = data.get("error") if data else None
        if err:
            return f'<p class="thumb-hint"><em>Thumbnails: {html.escape(err)}</em></p>'
        return ""

    selected = data.get("selected") or ""
    poster = sub / "poster.jpg"
    poster_note = ""
    if poster.is_file():
        src = _thumbnail_src(pid, "poster.jpg", thumb_href_for=thumb_href_for)
        poster_note = (
            f'<p class="thumb-selected">Saved poster: '
            f'<img src="{html.escape(src)}" alt="poster" class="thumb-poster-preview">'
            f" ({html.escape(selected or 'poster.jpg')})</p>"
        )

    tiles = []
    for cand in data["candidates"]:
        cid = cand["id"]
        rel = cand["file"]
        src = _thumbnail_src(pid, rel, thumb_href_for=thumb_href_for)
        label = html.escape(cand.get("label", cid))
        detail = html.escape(cand.get("detail", ""))
        active = " active" if cid == selected else ""
        tiles.append(
            f"""
            <button type="button" class="thumb-opt{active}" data-choice="{html.escape(cid)}"
                    title="{detail}">
              <img src="{html.escape(src)}" alt="{label}">
              <span>{label}</span>
              <small>{detail}</small>
            </button>
            """
        )

    api_attr = html.escape(api_base) if api_base else ""
    return f"""
    <div class="thumb-picker" data-provider="{html.escape(pid)}" data-api-base="{api_attr}">
      <h3>Thumbnail (splash / cover)</h3>
      <p class="thumb-hint">Pick one frame — first non-black, highest contrast, or scene cuts.</p>
      <div class="thumb-grid">{"".join(tiles)}</div>
      {poster_note}
      <p class="thumb-status" aria-live="polite"></p>
    </div>
    """


def build_review_html(
    arena_dir: Path,
    manifest: dict,
    *,
    href_for: Callable[[str], str] | None = None,
    thumb_href_for: Callable[[str, str], str] | None = None,
    back_href: str | None = None,
    api_base: str | None = None,
) -> str:
    """Return HTML for the arena comparison page.

    href_for(provider_id) must return the video URL for that slot (file or HTTP).
    Defaults to relative paths suitable for review.html on disk.
    """
    if href_for is None:
        href_for = lambda pid: f"{pid}/video.mp4"  # noqa: E731

    providers = manifest.get("providers", {})
    rows = []
    for pid, data in providers.items():
        sub = arena_dir / pid
        video = sub / "video.mp4"
        critique = sub / "critique.md"
        status = data.get("status", "unknown")
        video_tag = ""
        if video.is_file():
            src = html.escape(_video_src(pid, href_for))
            poster_attr = ""
            if (sub / "poster.jpg").is_file():
                poster_src = _thumbnail_src(
                    pid, "poster.jpg", thumb_href_for=thumb_href_for
                )
                poster_attr = f' poster="{html.escape(poster_src)}"'
            video_tag = (
                f'<video controls playsinline src="{src}"{poster_attr} '
                f'style="width:100%;max-height:420px;background:#000"></video>'
            )
        elif (sub / "SKIPPED.md").is_file():
            video_tag = f"<pre>{html.escape((sub / 'SKIPPED.md').read_text())}</pre>"
        elif (sub / "FAILED.md").is_file():
            video_tag = f"<pre>{html.escape((sub / 'FAILED.md').read_text())}</pre>"
        elif (sub / "DOWNLOAD.md").is_file():
            video_tag = f"<pre>{html.escape((sub / 'DOWNLOAD.md').read_text())}</pre>"
        else:
            video_tag = "<p><em>No video file</em></p>"

        critique_html = ""
        if critique.is_file():
            critique_html = (
                f"<details><summary>Critique</summary><pre>"
                f"{html.escape(critique.read_text())}</pre></details>"
            )

        thumb_html = ""
        if video.is_file():
            provider_api = f"{api_base}/{pid}" if api_base else ""
            thumb_html = _build_thumbnail_picker(
                pid,
                sub,
                thumb_href_for=thumb_href_for,
                api_base=provider_api or None,
            )

        rows.append(
            f"""
            <section class="card">
              <h2>{html.escape(data.get('display_name', pid))}</h2>
              <p><strong>Status:</strong> {html.escape(status)} — {html.escape(data.get('message', ''))}</p>
              {video_tag}
              {thumb_html}
              {critique_html}
              <label>Human score (1-5 motion): <input type="number" min="1" max="5" name="{pid}_motion"></label>
              <label>Notes: <textarea name="{pid}_notes" rows="2" style="width:100%"></textarea></label>
            </section>
            """
        )

    post_title = html.escape(manifest.get("title", "Video arena"))
    prompt_raw = load_prompt_text(arena_dir, manifest)
    prompt_area = html.escape(prompt_raw)
    api_root = html.escape(api_base) if api_base else ""
    body = "\n".join(rows)
    back_link = ""
    if back_href:
        back_link = f'<p><a href="{html.escape(back_href)}">← Back to variants</a></p>'

    winner_path = arena_dir / "WINNER.txt"
    winner_block = ""
    if winner_path.is_file():
        winner_text = winner_path.read_text(encoding="utf-8").strip()
        if winner_text and not winner_text.startswith("#"):
            winner_block = (
                f'<div class="winner"><h2>Current winner</h2>'
                f"<pre>{html.escape(winner_text)}</pre></div>"
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Video arena — {post_title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1rem; background: #111; color: #eee; }}
    h1 {{ font-size: 1.25rem; }}
    a {{ color: #8ab4ff; }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .card {{ background: #1a1a1a; padding: 1rem; border-radius: 8px; border: 1px solid #333; }}
    .prompt {{ background: #222; padding: 1rem; border-radius: 8px; white-space: pre-wrap; font-size: 0.85rem; }}
    .winner {{ margin-top: 2rem; padding: 1rem; background: #0d3320; border-radius: 8px; }}
    .thumb-picker {{ margin-top: 1rem; }}
    .thumb-picker h3 {{ font-size: 0.95rem; margin-bottom: 0.35rem; }}
    .thumb-hint {{ font-size: 0.8rem; color: #aaa; margin-bottom: 0.5rem; }}
    .thumb-grid {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .thumb-opt {{
      background: #222; border: 2px solid #444; border-radius: 6px; padding: 4px;
      cursor: pointer; max-width: 120px; text-align: center; color: #eee;
    }}
    .thumb-opt.active {{ border-color: #4caf50; box-shadow: 0 0 0 1px #4caf50; }}
    .thumb-opt img {{ display: block; width: 100%; height: auto; border-radius: 4px; }}
    .thumb-opt span {{ display: block; font-size: 0.7rem; margin-top: 4px; }}
    .thumb-opt small {{ display: block; font-size: 0.65rem; color: #888; }}
    .thumb-poster-preview {{ max-height: 80px; vertical-align: middle; margin-left: 8px; }}
    .thumb-status {{ font-size: 0.8rem; color: #8ab4ff; margin-top: 0.5rem; min-height: 1.2em; }}
    .prompt-editor {{ margin-bottom: 1.5rem; }}
    .prompt-editor textarea {{
      width: 100%; min-height: 11rem; font-family: ui-monospace, monospace;
      font-size: 0.85rem; line-height: 1.45; background: #222; color: #eee;
      border: 1px solid #444; border-radius: 8px; padding: 0.75rem; resize: vertical;
    }}
    .prompt-actions {{ margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    .prompt-actions button {{
      background: #2a5db0; color: #fff; border: none; border-radius: 6px;
      padding: 0.45rem 0.9rem; cursor: pointer; font-size: 0.85rem;
    }}
    .prompt-actions button:disabled {{ opacity: 0.5; cursor: default; }}
    .prompt-status {{ font-size: 0.8rem; color: #8ab4ff; min-height: 1.2em; }}
    .prompt-hint {{ font-size: 0.8rem; color: #aaa; margin-top: 0.35rem; }}
  </style>
  <script>
    (function() {{
      const apiRoot = document.getElementById('shared-prompt-editor')?.dataset.apiRoot || '';
      const ta = document.getElementById('shared-prompt-text');
      const status = document.getElementById('prompt-save-status');
      const btn = document.getElementById('prompt-save-btn');
      if (!ta || !btn) return;
      btn.addEventListener('click', async () => {{
        const prompt = ta.value.trim();
        if (!prompt) {{
          status.textContent = 'Prompt cannot be empty';
          return;
        }}
        if (!apiRoot) {{
          status.textContent = 'Saved locally only — use preview_server.py to write prompt.txt';
          return;
        }}
        btn.disabled = true;
        status.textContent = 'Saving…';
        try {{
          const res = await fetch(apiRoot + '/save-prompt', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ prompt }}),
          }});
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || res.statusText);
          status.textContent = 'Saved prompt.txt — re-run providers with --only';
        }} catch (e) {{
          status.textContent = 'Error: ' + e.message;
        }} finally {{
          btn.disabled = false;
        }}
      }});
    }})();

    document.querySelectorAll('.thumb-picker').forEach(picker => {{
      const apiBase = picker.dataset.apiBase;
      const status = picker.querySelector('.thumb-status');
      picker.querySelectorAll('.thumb-opt').forEach(btn => {{
        btn.addEventListener('click', async () => {{
          const choice = btn.dataset.choice;
          picker.querySelectorAll('.thumb-opt').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          if (!apiBase) {{
            status.textContent = 'Selected ' + choice + ' — open via preview_server.py to save poster.jpg';
            return;
          }}
          status.textContent = 'Saving…';
          try {{
            const res = await fetch(apiBase + '/select-thumbnail', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ choice }}),
            }});
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || res.statusText);
            status.textContent = 'Saved poster.jpg (' + choice + ')';
          }} catch (e) {{
            status.textContent = 'Error: ' + e.message;
            btn.classList.remove('active');
          }}
        }});
      }});
    }});
  </script>
</head>
<body>
  {back_link}
  <h1>Video arena — {post_title}</h1>
  <p>Compare providers side-by-side. Edit the <strong>shared prompt</strong> once, then re-run individual providers for new video only.</p>
  <section class="prompt-editor" id="shared-prompt-editor" data-api-root="{api_root}">
    <h2>Shared prompt (all providers)</h2>
    <p class="prompt-hint">Sent to every T2V API. Save here, then:
      <code>generate_video_arena.py POST_DIR --only azure_sora</code> (or vertex_veo, etc.).</p>
    <textarea id="shared-prompt-text" spellcheck="true">{prompt_area}</textarea>
    <div class="prompt-actions">
      <button type="button" id="prompt-save-btn">Save prompt</button>
      <span class="prompt-status" id="prompt-save-status" aria-live="polite"></span>
    </div>
  </section>
  <div class="grid">{body}</div>
  {winner_block}
  <div class="winner">
    <h2>Winner (human)</h2>
    <p>After review, create <code>WINNER.txt</code> in this folder with one line, e.g. <code>vertex_veo</code> and optional notes.</p>
  </div>
</body>
</html>
"""


def load_arena_manifest(arena_dir: Path) -> dict | None:
    manifest_path = arena_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_review_html(arena_dir: Path, manifest: dict, **kwargs) -> Path:
    """Write review.html listing provider slots with video tags when present."""
    page = build_review_html(arena_dir, manifest, **kwargs)
    out = arena_dir / "review.html"
    out.write_text(page, encoding="utf-8")
    return out
