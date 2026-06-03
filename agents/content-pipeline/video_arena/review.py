"""Generate static HTML comparison page for human video arena review."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable

from video_arena.prompt_store import load_final_pass_brief, load_prompt_text
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


def _build_provider_card(
    pid: str,
    data: dict,
    sub: Path,
    *,
    href_for: Callable[[str], str],
    thumb_href_for: Callable[[str, str], str] | None,
    api_base: str | None,
) -> str:
    video = sub / "video.mp4"
    critique = sub / "critique.md"
    status = data.get("status", "unknown")
    video_tag = ""
    if video.is_file():
        src = html.escape(_video_src(pid, href_for))
        poster_attr = ""
        if (sub / "poster.jpg").is_file():
            poster_src = _thumbnail_src(pid, "poster.jpg", thumb_href_for=thumb_href_for)
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
            pid, sub, thumb_href_for=thumb_href_for, api_base=provider_api or None
        )

    return f"""
    <section class="card" data-provider-id="{html.escape(pid)}">
      <h2>{html.escape(data.get('display_name', pid))}</h2>
      <p><strong>Status:</strong> {html.escape(status)} — {html.escape(data.get('message', ''))}</p>
      {video_tag}
      {thumb_html}
      {critique_html}
      <div class="card-actions">
        <button type="button" class="btn-regenerate btn-regenerate-provider"
                data-provider="{html.escape(pid)}">Regenerate video</button>
        <span class="action-status" data-role="provider-status" aria-live="polite"></span>
      </div>
      <label>Human score (1-5 motion): <input type="number" min="1" max="5" name="{pid}_motion"></label>
      <label>Notes: <textarea name="{pid}_notes" rows="2" style="width:100%"></textarea></label>
    </section>
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
    if href_for is None:
        href_for = lambda pid: f"{pid}/video.mp4"  # noqa: E731

    providers = manifest.get("providers", {})
    provider_ids = list(providers.keys())
    cards = [
        _build_provider_card(
            pid,
            data,
            arena_dir / pid,
            href_for=href_for,
            thumb_href_for=thumb_href_for,
            api_base=api_base,
        )
        for pid, data in providers.items()
    ]

    post_title = html.escape(manifest.get("title", "Video arena"))
    prompt_raw = load_prompt_text(arena_dir, manifest)
    prompt_area = html.escape(prompt_raw)
    brief_raw = load_final_pass_brief(arena_dir, manifest)
    brief_area = html.escape(brief_raw)
    api_root = html.escape(api_base) if api_base else ""
    provider_ids_attr = html.escape(json.dumps(provider_ids))

    brief_placeholder = html.escape(
        "e.g. Open on vertex_veo (0–2s); use azure_sora lighting for laptop beat; "
        "avoid Veo black lead-in; 6s vertical, no on-screen text."
    )

    final_video_html = ""
    fp_job = manifest.get("final_pass") or {}
    fp_video = arena_dir / "final_pass" / "video.mp4"
    if fp_video.is_file():
        fp_src = (
            f"{api_base}/final-pass/video.mp4" if api_base else "final_pass/video.mp4"
        )
        final_video_html = (
            f'<div class="final-output">'
            f'<h3>Staged output</h3>'
            f'<video controls playsinline src="{html.escape(fp_src)}" '
            f'style="width:100%;max-height:360px;background:#000"></video>'
            f'<p class="thumb-hint">{html.escape(str(fp_job.get("message", "")))}</p>'
            f"</div>"
        )

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

    cards_html = "\n".join(cards) if cards else "<p><em>No provider runs yet.</em></p>"

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
    .workspace-section {{
      padding: 1rem; border: 1px solid #333; border-radius: 8px;
      background: #161616; margin-bottom: 1.5rem;
    }}
    .workspace-section h2 {{ font-size: 1rem; margin-bottom: 0.35rem; }}
    .section-jump {{ display: flex; gap: 0.75rem; flex-wrap: wrap; font-size: 0.85rem; margin: 0.75rem 0 1.25rem; }}
    .section-jump a {{ color: #8ab4ff; }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .card {{ background: #1a1a1a; padding: 1rem; border-radius: 8px; border: 1px solid #333; }}
    .winner {{ margin-top: 1rem; padding: 1rem; background: #0d3320; border-radius: 8px; }}
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
    .workspace textarea {{
      width: 100%; min-height: 11rem; font-family: ui-monospace, monospace;
      font-size: 0.85rem; line-height: 1.45; background: #222; color: #eee;
      border: 1px solid #444; border-radius: 8px; padding: 0.75rem; resize: vertical;
    }}
    .panel-actions, .card-actions {{
      margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;
    }}
    .panel-actions button, .card-actions button {{
      border: none; border-radius: 6px; padding: 0.45rem 0.9rem; cursor: pointer;
      font-size: 0.85rem;
    }}
    .btn-save {{ background: #2a5db0; color: #fff; }}
    .btn-regenerate {{ background: #c45c26; color: #fff; }}
    button:disabled {{ opacity: 0.5; cursor: default; }}
    .action-status {{ font-size: 0.8rem; color: #8ab4ff; min-height: 1.2em; }}
    #section-final {{ background: #141422; border-color: #3d3d6b; }}
  </style>
  <script>
    const ARENA_API = document.body.dataset.apiRoot || '';

    async function arenaPost(path, payload, statusEl, btn, successMsg, validate) {{
      if (validate && !validate()) return;
      if (!ARENA_API) {{
        statusEl.textContent = 'Use preview_server.py (/arena) to save to disk';
        return;
      }}
      btn.disabled = true;
      statusEl.textContent = 'Saving…';
      try {{
        const res = await fetch(ARENA_API + path, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload),
        }});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        statusEl.textContent = successMsg;
      }} catch (e) {{
        statusEl.textContent = 'Error: ' + e.message;
      }} finally {{
        btn.disabled = false;
      }}
    }}

    async function arenaRegenerate(path, payload, statusEl, btn) {{
      if (!ARENA_API) {{
        statusEl.textContent = 'Use preview_server.py (/arena) for regenerate';
        return;
      }}
      btn.disabled = true;
      statusEl.textContent = 'Running… (may take several minutes)';
      try {{
        const res = await fetch(ARENA_API + path, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload),
        }});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        statusEl.textContent = data.message || 'Done';
        if (data.reload) setTimeout(() => location.reload(), 600);
      }} catch (e) {{
        statusEl.textContent = 'Error: ' + e.message;
      }} finally {{
        btn.disabled = false;
      }}
    }}

    const promptTa = document.getElementById('shared-prompt-text');
    const promptStatus = document.getElementById('prompt-save-status');
    document.getElementById('prompt-save-btn')?.addEventListener('click', () => arenaPost(
      '/save-prompt', {{ prompt: promptTa.value.trim() }}, promptStatus,
      document.getElementById('prompt-save-btn'), 'Saved prompt.txt',
      () => {{
        if (!promptTa.value.trim()) {{
          promptStatus.textContent = 'Prompt cannot be empty'; return false;
        }}
        return true;
      }}
    ));
    document.getElementById('prompt-regenerate-btn')?.addEventListener('click', () => {{
      if (!confirm('Rebuild prompt from clapper.txt? This overwrites manual prompt edits.')) return;
      arenaRegenerate('/regenerate-prompt', {{ from_clapper: true }}, promptStatus,
        document.getElementById('prompt-regenerate-btn'));
    }});

    const briefTa = document.getElementById('final-pass-brief-text');
    const briefStatus = document.getElementById('final-pass-save-status');
    document.getElementById('final-pass-save-btn')?.addEventListener('click', () => arenaPost(
      '/save-final-pass-brief', {{ brief: briefTa.value }}, briefStatus,
      document.getElementById('final-pass-save-btn'), 'Saved combine brief'
    ));
    document.getElementById('final-pass-regenerate-btn')?.addEventListener('click', () => arenaRegenerate(
      '/regenerate-final-pass',
      {{ brief: briefTa.value, use_llm_brief: true }},
      briefStatus, document.getElementById('final-pass-regenerate-btn')
    ));

    document.getElementById('regenerate-all-videos-btn')?.addEventListener('click', () => {{
      const ids = JSON.parse(document.body.dataset.providerIds || '[]');
      if (!ids.length) return;
      if (!confirm('Regenerate ALL provider videos? This is slow and billed.')) return;
      arenaRegenerate('/regenerate-providers', {{ provider_ids: ids }},
        document.getElementById('videos-panel-status'),
        document.getElementById('regenerate-all-videos-btn'));
    }});

    document.querySelectorAll('.btn-regenerate-provider').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const pid = btn.dataset.provider;
        const status = btn.closest('.card')?.querySelector('[data-role="provider-status"]');
        const payload = {{ provider_id: pid }};
        if (promptTa && promptTa.value.trim()) payload.prompt = promptTa.value.trim();
        arenaRegenerate('/regenerate-provider', payload, status, btn);
      }});
    }});

    document.querySelectorAll('.thumb-picker').forEach(picker => {{
      const apiBase = picker.dataset.apiBase;
      const status = picker.querySelector('.thumb-status');
      picker.querySelectorAll('.thumb-opt').forEach(btn => {{
        btn.addEventListener('click', async () => {{
          const choice = btn.dataset.choice;
          picker.querySelectorAll('.thumb-opt').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          if (!apiBase) {{
            status.textContent = 'Selected ' + choice + ' — use preview_server for poster.jpg';
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
<body data-api-root="{api_root}" data-provider-ids="{provider_ids_attr}">
  {back_link}
  <h1>Video arena — {post_title}</h1>
  <p>Three workspaces on one page — each can be saved or regenerated independently.</p>
  <nav class="section-jump" aria-label="Jump to section">
    <a href="#section-prompt">1 · Source text</a>
    <a href="#section-videos">2 · Videos &amp; thumbnails</a>
    <a href="#section-final">3 · Final pass</a>
  </nav>

  <section id="section-prompt" class="workspace-section">
    <h2>1 · Source text (shared T2V prompt)</h2>
    <p class="thumb-hint">All providers use this prompt. Regenerate rebuilds from <code>clapper.txt</code>.</p>
    <textarea id="shared-prompt-text" spellcheck="true">{prompt_area}</textarea>
    <div class="panel-actions">
      <button type="button" class="btn-save" id="prompt-save-btn">Save</button>
      <button type="button" class="btn-regenerate" id="prompt-regenerate-btn">Regenerate from clapper</button>
      <span class="action-status" id="prompt-save-status" aria-live="polite"></span>
    </div>
  </section>

  <section id="section-videos" class="workspace-section">
    <h2>2 · Videos &amp; thumbnail feedback</h2>
    <p class="thumb-hint">Regenerate one provider or all. Saves current source text first if you edited it above.</p>
    <div class="panel-actions">
      <button type="button" class="btn-regenerate" id="regenerate-all-videos-btn">Regenerate all videos</button>
      <span class="action-status" id="videos-panel-status" aria-live="polite"></span>
    </div>
    <div class="grid">{cards_html}</div>
    {winner_block}
    <div class="winner">
      <h2>Winner (human)</h2>
      <p>Set <code>WINNER.txt</code> with one line, e.g. <code>vertex_veo</code> — used by final pass.</p>
    </div>
  </section>

  <section id="section-final" class="workspace-section">
    <h2>3 · Final-pass combine</h2>
    <p class="thumb-hint">Instructions for the combine agent. Regenerate drafts brief (LLM) and stages <code>final_pass/video.mp4</code> from WINNER.</p>
    <textarea id="final-pass-brief-text" spellcheck="true"
      placeholder="{brief_placeholder}">{brief_area}</textarea>
    <div class="panel-actions">
      <button type="button" class="btn-save" id="final-pass-save-btn">Save</button>
      <button type="button" class="btn-regenerate" id="final-pass-regenerate-btn">Regenerate final pass</button>
      <span class="action-status" id="final-pass-save-status" aria-live="polite"></span>
    </div>
    {final_video_html}
  </section>
</body>
</html>
"""


def load_arena_manifest(arena_dir: Path) -> dict | None:
    manifest_path = arena_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_review_html(arena_dir: Path, manifest: dict, **kwargs) -> Path:
    page = build_review_html(arena_dir, manifest, **kwargs)
    out = arena_dir / "review.html"
    out.write_text(page, encoding="utf-8")
    return out
