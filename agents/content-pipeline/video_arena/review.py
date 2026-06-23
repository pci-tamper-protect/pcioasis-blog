"""Generate static HTML comparison page for human video arena review."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable

from video_arena.prompt_store import load_final_pass_brief, load_prompt_text
from video_arena.provider_briefs import load_thumbnail_brief, load_video_brief
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
    data = load_thumbnails(sub) or {}
    err = data.get("error")

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
    for cand in (data or {}).get("candidates") or []:
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

    if tiles:
        grid_html = f'<div class="thumb-grid">{"".join(tiles)}</div>'
    else:
        hint = "No candidates yet — use Regenerate thumbnails."
        if err:
            hint = f"{hint} ({err})"
        grid_html = f'<p class="thumb-hint"><em>{html.escape(hint)}</em></p>'

    provider_api = f"{api_base}/{pid}" if api_base else ""
    api_attr = html.escape(provider_api)
    thumb_brief = html.escape(load_thumbnail_brief(sub))

    return f"""
    <div class="thumb-picker" data-provider="{html.escape(pid)}" data-api-base="{api_attr}">
      <h3>Thumbnail (splash / cover)</h3>
      <p class="thumb-hint">Pick one frame — first non-black, highest contrast, or scene cuts.</p>
      {grid_html}
      <div class="provider-field-block provider-field-thumbs">
        <label class="provider-brief-label" for="{html.escape(pid)}-thumb-brief">Thumbnail notes</label>
        <textarea id="{html.escape(pid)}-thumb-brief" class="provider-brief provider-thumb-brief"
          data-provider="{html.escape(pid)}" rows="3"
          placeholder="e.g. max contrast; crop bottom 3/5; dewarp phone straight-on">{thumb_brief}</textarea>
        <div class="thumb-actions card-actions">
          <button type="button" class="btn-regenerate btn-regenerate-thumbnails"
                  data-provider="{html.escape(pid)}">Regenerate thumbnails</button>
          <span class="action-status status-idle" data-role="thumb-regen-status" aria-live="polite"></span>
        </div>
      </div>
      {poster_note}
      <p class="thumb-status status-idle" data-role="thumb-select-status" aria-live="polite"></p>
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
        thumb_html = _build_thumbnail_picker(
            pid, sub, thumb_href_for=thumb_href_for, api_base=api_base
        )

    video_brief = html.escape(load_video_brief(sub))

    return f"""
    <section class="card" data-provider-id="{html.escape(pid)}">
      <h2>{html.escape(data.get('display_name', pid))}</h2>
      <p><strong>Status:</strong> {html.escape(status)} — {html.escape(data.get('message', ''))}</p>
      <div class="video-stack">
        {video_tag}
        <div class="provider-field-block provider-field-video">
          <label class="provider-brief-label" for="{html.escape(pid)}-video-brief">Video script (this provider)</label>
          <textarea id="{html.escape(pid)}-video-brief" class="provider-brief provider-video-brief"
            data-provider="{html.escape(pid)}" rows="4"
            placeholder="Leave blank to use section 1. When set, only this provider uses this script.">{video_brief}</textarea>
          <div class="card-actions card-actions-video">
            <button type="button" class="btn-regenerate btn-regenerate-video"
                    data-provider="{html.escape(pid)}">Regenerate video</button>
            <span class="action-status status-idle" data-role="video-regen-status" aria-live="polite"></span>
          </div>
        </div>
      </div>
      {thumb_html}
      {critique_html}
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
    :root {{
      --bg: #111; --bg-surface: #161616; --bg-card: #1a1a1a; --bg-input: #222;
      --bg-winner: #0d3320; --bg-final: #141422; --bg-banner: #3d2a14;
      --text: #eee; --text-muted: #aaa; --text-faint: #888; --text-label: #ccc;
      --border: #333; --border-input: #444; --border-final: #3d3d6b;
      --border-banner: #c45c26; --text-banner: #ffccbc;
      --link: #8ab4ff;
      --status-idle: #888; --status-done: #81c784; --status-error: #e57373; --status-running: #ffb74d;
    }}
    body.light {{
      --bg: #f4f4f5; --bg-surface: #e9e9eb; --bg-card: #fff; --bg-input: #f0f0f2;
      --bg-winner: #d4edda; --bg-final: #eef0ff; --bg-banner: #fff3e0;
      --text: #111; --text-muted: #555; --text-faint: #777; --text-label: #444;
      --border: #ccc; --border-input: #bbb; --border-final: #9999cc;
      --border-banner: #e65100; --text-banner: #bf360c;
      --link: #1558b0;
      --status-idle: #777; --status-done: #2e7d32; --status-error: #c62828; --status-running: #e65100;
    }}
    body {{ font-family: system-ui, sans-serif; margin: 1rem; background: var(--bg); color: var(--text); }}
    h1 {{ font-size: 1.25rem; }}
    a {{ color: var(--link); }}
    .workspace-section {{
      padding: 1rem; border: 1px solid var(--border); border-radius: 8px;
      background: var(--bg-surface); margin-bottom: 1.5rem;
    }}
    .workspace-section h2 {{ font-size: 1rem; margin-bottom: 0.35rem; }}
    .section-jump {{ display: flex; gap: 0.75rem; flex-wrap: wrap; font-size: 0.85rem; margin: 0.75rem 0 1.25rem; }}
    .section-jump a {{ color: var(--link); }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .card {{ background: var(--bg-card); padding: 1rem; border-radius: 8px; border: 1px solid var(--border); }}
    .winner {{ margin-top: 1rem; padding: 1rem; background: var(--bg-winner); border-radius: 8px; }}
    .video-stack {{ margin: 0.5rem 0 0; }}
    .video-stack video, .video-stack pre {{ display: block; margin-bottom: 0.35rem; }}
    .card-actions-video {{ margin-top: 0.25rem; margin-bottom: 0; }}
    .thumb-picker {{ margin-top: 1rem; }}
    .thumb-picker h3 {{ font-size: 0.95rem; margin-bottom: 0.35rem; }}
    .thumb-hint {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; }}
    .thumb-grid {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .thumb-opt {{
      background: var(--bg-input); border: 2px solid var(--border-input); border-radius: 6px; padding: 4px;
      cursor: pointer; max-width: 120px; text-align: center; color: var(--text);
    }}
    .thumb-opt.active {{ border-color: #4caf50; box-shadow: 0 0 0 1px #4caf50; }}
    .thumb-opt img {{ display: block; width: 100%; height: auto; border-radius: 4px; }}
    .thumb-opt span {{ display: block; font-size: 0.7rem; margin-top: 4px; }}
    .thumb-opt small {{ display: block; font-size: 0.65rem; color: var(--text-faint); }}
    .thumb-poster-preview {{ max-height: 80px; vertical-align: middle; margin-left: 8px; }}
    .thumb-actions {{ margin-top: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    .thumb-status, .action-status {{
      font-size: 0.8rem; margin-top: 0.25rem; min-height: 1.2em;
    }}
    .status-idle {{ color: var(--status-idle); }}
    .status-running {{ color: var(--status-running); }}
    .status-running::before {{
      content: ""; display: inline-block; width: 0.55em; height: 0.55em;
      margin-right: 0.35em; border-radius: 50%; background: currentColor;
      animation: arena-pulse 1s ease-in-out infinite;
    }}
    .status-done {{ color: var(--status-done); }}
    .status-done::before {{ content: "✓ "; }}
    .status-error {{ color: var(--status-error); }}
    .status-error::before {{ content: "✕ "; }}
    @keyframes arena-pulse {{ 50% {{ opacity: 0.35; }} }}
    .workspace textarea {{
      width: 100%; min-height: 3.5rem; font-family: ui-monospace, monospace;
      font-size: 0.85rem; line-height: 1.45; background: var(--bg-input); color: var(--text);
      border: 1px solid var(--border-input); border-radius: 8px; padding: 0.75rem; resize: none;
      overflow-y: hidden; box-sizing: border-box;
    }}
    .workspace textarea.textarea-scroll {{ overflow-y: auto; }}
    .provider-field-block {{
      display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.5rem;
    }}
    .provider-brief-label {{ display: block; font-size: 0.8rem; color: var(--text-label); margin: 0; }}
    .provider-brief {{
      width: 100%; font-family: ui-monospace, monospace; font-size: 0.8rem;
      line-height: 1.4; background: var(--bg-input); color: var(--text); border: 1px solid var(--border-input);
      border-radius: 6px; padding: 0.5rem; resize: vertical; box-sizing: border-box;
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
    .btn-link {{
      background: none; border: none; color: var(--link); cursor: pointer;
      font-size: 0.8rem; text-decoration: underline; padding: 0;
    }}
    button:disabled {{ opacity: 0.5; cursor: default; }}
    .action-status {{ font-size: 0.8rem; color: var(--link); min-height: 1.2em; }}
    #section-final {{ background: var(--bg-final); border-color: var(--border-final); }}
    #arena-api-banner {{
      display: none; padding: 0.65rem 1rem; margin-bottom: 1rem; border-radius: 8px;
      background: var(--bg-banner); border: 1px solid var(--border-banner); color: var(--text-banner); font-size: 0.85rem;
    }}
    #arena-api-banner.visible {{ display: block; }}
    #theme-toggle {{
      position: fixed; top: 0.75rem; right: 1rem; z-index: 100;
      background: var(--bg-card); color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; padding: 0.3rem 0.7rem; cursor: pointer; font-size: 0.8rem;
    }}
  </style>
</head>
<body data-api-root="{api_root}" data-provider-ids="{provider_ids_attr}">
  <button id="theme-toggle" aria-label="Toggle light/dark mode">☀ Light</button>
  <script>
    (function() {{
      var btn = document.getElementById('theme-toggle');
      function apply(light) {{
        document.body.classList.toggle('light', light);
        btn.textContent = light ? '🌙 Dark' : '☀ Light';
        try {{ localStorage.setItem('arena-theme', light ? 'light' : 'dark'); }} catch(e) {{}}
      }}
      try {{ apply(localStorage.getItem('arena-theme') === 'light'); }} catch(e) {{}}
      btn.addEventListener('click', function() {{ apply(!document.body.classList.contains('light')); }});
    }})();
  </script>
  {back_link}
  <div id="arena-api-banner" role="status"></div>
  <h1>Video arena — {post_title}</h1>
  <p>Three workspaces on one page — each can be saved or regenerated independently.</p>
  <nav class="section-jump" aria-label="Jump to section">
    <a href="#section-prompt">1 · Source text</a>
    <a href="#section-videos">2 · Videos &amp; thumbnails</a>
    <a href="#section-final">3 · Final pass</a>
  </nav>

  <section id="section-prompt" class="workspace-section">
    <h2>1 · Script text (shared)</h2>
    <p class="thumb-hint">Edits here are saved to <code>prompt.txt</code> and used when you regenerate videos (unless a provider box below overrides).</p>
    <textarea id="shared-prompt-text" class="workspace-field" spellcheck="true">{prompt_area}</textarea>
    <div class="panel-actions">
      <button type="button" class="btn-regenerate" id="prompt-save-regenerate-btn">Save and Regenerate</button>
      <span class="action-status" id="prompt-save-status" aria-live="polite"></span>
    </div>
    <p class="thumb-hint optional-link">
      <button type="button" class="btn-link" id="rebuild-from-clapper-btn">Rebuild script from clapper.txt</button>
      (replaces text above — optional)
    </p>
  </section>

  <section id="section-videos" class="workspace-section">
    <h2>2 · Videos &amp; thumbnail feedback</h2>
    <p class="thumb-hint">Use <strong>Save and Regenerate</strong> in section 1 for all providers, or each card below for one provider.</p>
    <div class="grid">{cards_html}</div>
    {winner_block}
    <div class="winner">
      <h2>Winner (human)</h2>
      <p>Set <code>WINNER.txt</code> with one line, e.g. <code>vertex_veo</code> — used by final pass.</p>
    </div>
  </section>

  <section id="section-final" class="workspace-section">
    <h2>3 · Final-pass combine</h2>
    <p class="thumb-hint">Instructions for combine (ffmpeg when possible, else T2V regen). Box grows to ~2 paragraphs then scrolls. Regenerate runs ffmpeg Sora→Veo when both clips exist.</p>
    <textarea id="final-pass-brief-text" class="workspace-field" spellcheck="true"
      placeholder="{brief_placeholder}">{brief_area}</textarea>
    <div class="panel-actions">
      <button type="button" class="btn-save" id="final-pass-save-btn">Save</button>
      <button type="button" class="btn-regenerate" id="final-pass-regenerate-btn">Regenerate final pass</button>
      <span class="action-status" id="final-pass-save-status" aria-live="polite"></span>
    </div>
    {final_video_html}
  </section>
  <script>
    function getArenaApi() {{
      const root = (document.body && document.body.dataset.apiRoot) || '';
      if (root) return root;
      const p = location.pathname.replace(/\\/+$/, '');
      if (p === '/arena' || p.endsWith('/arena')) return '/arena';
      return '';
    }}

    let ARENA_API = '';

    const TEXTAREA_MAX_LINES = 10;

    function fitTextarea(ta) {{
      if (!ta) return;
      const lh = parseFloat(getComputedStyle(ta).lineHeight) || 20;
      const maxH = Math.ceil(lh * TEXTAREA_MAX_LINES);
      ta.classList.remove('textarea-scroll');
      ta.style.height = 'auto';
      const need = ta.scrollHeight;
      ta.style.height = Math.min(need, maxH) + 'px';
      if (need > maxH) ta.classList.add('textarea-scroll');
    }}

    function setJobStatus(el, state, message) {{
      if (!el) return;
      el.classList.remove('status-idle', 'status-running', 'status-done', 'status-error');
      if (state) el.classList.add('status-' + state);
      el.textContent = message || '';
    }}

    function providerApiBase(picker) {{
      const base = (picker && picker.dataset.apiBase) || '';
      if (base) return base;
      const pid = picker && picker.dataset.provider;
      if (ARENA_API && pid) return ARENA_API + '/' + pid;
      return '';
    }}

    async function readJsonResponse(res) {{
      const ct = res.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {{
        const snippet = (await res.text()).slice(0, 120);
        throw new Error('Server returned non-JSON — restart preview_server? ' + snippet);
      }}
      return res.json();
    }}

    function sharedScriptText() {{
      const ta = document.getElementById('shared-prompt-text');
      return ta ? ta.value : '';
    }}

    function withSharedPrompt(payload) {{
      const text = sharedScriptText();
      if (text.trim()) payload.prompt = text;
      return payload;
    }}

    async function saveSharedScript(statusEl, btn) {{
      if (!ARENA_API) {{
        throw new Error('Start preview_server.py and open http://localhost:5050/arena');
      }}
      const text = sharedScriptText();
      if (!text.trim()) {{
        throw new Error('Section 1 script is empty');
      }}
      if (btn) btn.disabled = true;
      setJobStatus(statusEl, 'running', 'Saving script…');
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      try {{
        const res = await fetch(ARENA_API + '/save-prompt', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ prompt: text }}),
          signal: controller.signal,
        }});
        const data = await readJsonResponse(res);
        if (!res.ok) throw new Error(data.error || res.statusText);
        setJobStatus(statusEl, 'done', data.message || 'Script saved');
        return data;
      }} finally {{
        clearTimeout(timeout);
        if (btn) btn.disabled = false;
      }}
    }}

    async function arenaPost(path, payload, statusEl, btn, successMsg, validate) {{
      if (validate && !validate()) return;
      try {{
        if (path === '/save-prompt') {{
          await saveSharedScript(statusEl, btn);
          return;
        }}
        if (!ARENA_API) {{
          setJobStatus(statusEl, 'error', 'Start preview_server.py and open http://localhost:5050/arena');
          return;
        }}
        if (btn) btn.disabled = true;
        setJobStatus(statusEl, 'running', 'Saving…');
        const res = await fetch(ARENA_API + path, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(payload),
        }});
        const data = await readJsonResponse(res);
        if (!res.ok) throw new Error(data.error || res.statusText);
        setJobStatus(statusEl, 'done', successMsg);
      }} catch (e) {{
        const msg = e.name === 'AbortError' ? 'Save timed out — restart preview_server' : e.message;
        setJobStatus(statusEl, 'error', msg);
      }} finally {{
        if (btn) btn.disabled = false;
      }}
    }}

    async function arenaRegenerate(path, payload, statusEl, btn, runningMsg) {{
      if (!ARENA_API) {{
        setJobStatus(statusEl, 'error', 'Start preview_server.py and open http://localhost:5050/arena');
        return;
      }}
      if (btn) btn.disabled = true;
      try {{
        if (path !== '/regenerate-prompt') {{
          setJobStatus(statusEl, 'running', 'Saving script…');
          await saveSharedScript(statusEl, null);
        }}
        setJobStatus(statusEl, 'running', runningMsg || 'Running…');
        const res = await fetch(ARENA_API + path, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify(withSharedPrompt(payload)),
        }});
        const data = await readJsonResponse(res);
        if (!res.ok) throw new Error(data.error || res.statusText);
        setJobStatus(statusEl, 'done', data.message || 'Completed');
        if (data.reload) setTimeout(() => location.reload(), 600);
      }} catch (e) {{
        setJobStatus(statusEl, 'error', e.message);
      }} finally {{
        if (btn) btn.disabled = false;
      }}
    }}

    function initArenaDashboard() {{
      ARENA_API = getArenaApi();
      const banner = document.getElementById('arena-api-banner');
      if (banner) {{
        if (!ARENA_API) {{
          banner.textContent = 'Save/Regenerate need preview_server: uv run python agents/content-pipeline/preview_server.py POST_DIR then open /arena (not the file on disk).';
          banner.classList.add('visible');
        }} else {{
          banner.classList.remove('visible');
        }}
      }}

      document.querySelectorAll('.workspace-field').forEach(ta => {{
        fitTextarea(ta);
        ta.addEventListener('input', () => fitTextarea(ta));
      }});

      function providerVideoBrief(pid) {{
        return document.getElementById(pid + '-video-brief')?.value ?? '';
      }}

      function providerThumbBrief(pid) {{
        return document.getElementById(pid + '-thumb-brief')?.value ?? '';
      }}

      const promptStatus = document.getElementById('prompt-save-status');
      const promptSaveRegenBtn = document.getElementById('prompt-save-regenerate-btn');
      const clapperBtn = document.getElementById('rebuild-from-clapper-btn');

      if (promptSaveRegenBtn) {{
        promptSaveRegenBtn.addEventListener('click', async () => {{
          const ids = JSON.parse(document.body.dataset.providerIds || '[]');
          if (!ids.length) {{
            setJobStatus(promptStatus, 'error', 'No providers to regenerate');
            return;
          }}
          if (!confirm('Save script and regenerate ALL provider videos? This is slow and billed.')) return;
          promptSaveRegenBtn.disabled = true;
          try {{
            await saveSharedScript(promptStatus, null);
            setJobStatus(promptStatus, 'running', 'Regenerating all videos…');
            const res = await fetch(ARENA_API + '/regenerate-providers', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(withSharedPrompt({{ provider_ids: ids }})),
            }});
            const data = await readJsonResponse(res);
            if (!res.ok) throw new Error(data.error || res.statusText);
            setJobStatus(promptStatus, 'done', data.message || 'All videos regenerated');
            if (data.reload) setTimeout(() => location.reload(), 600);
          }} catch (e) {{
            setJobStatus(promptStatus, 'error', e.message);
          }} finally {{
            promptSaveRegenBtn.disabled = false;
          }}
        }});
      }}

      if (clapperBtn) {{
        clapperBtn.addEventListener('click', () => {{
          if (!confirm('Rebuild script from clapper.txt? This replaces section 1 text (does not regenerate videos).')) return;
          arenaRegenerate('/regenerate-prompt', {{ from_clapper: true }}, promptStatus,
            clapperBtn, 'Rebuilding from clapper…');
        }});
      }}

      const briefTa = document.getElementById('final-pass-brief-text');
      const briefStatus = document.getElementById('final-pass-save-status');
      const briefSaveBtn = document.getElementById('final-pass-save-btn');
      const briefRegenBtn = document.getElementById('final-pass-regenerate-btn');

      if (briefSaveBtn && briefTa) {{
        briefSaveBtn.addEventListener('click', () => arenaPost(
          '/save-final-pass-brief', {{ brief: briefTa.value }}, briefStatus,
          briefSaveBtn, 'Saved combine brief'
        ));
      }}

      if (briefRegenBtn && briefTa) {{
        briefRegenBtn.addEventListener('click', () => arenaRegenerate(
          '/regenerate-final-pass',
          {{ brief: briefTa.value, use_llm_brief: true }},
          briefStatus, briefRegenBtn, 'Running final pass…'
        ));
      }}

      document.querySelectorAll('.btn-regenerate-video').forEach(btn => {{
        btn.addEventListener('click', () => {{
          const pid = btn.dataset.provider;
          const status = btn.closest('.video-stack')?.querySelector('[data-role="video-regen-status"]')
            || btn.closest('.card')?.querySelector('[data-role="video-regen-status"]');
          const payload = {{
            provider_id: pid,
            video_brief: providerVideoBrief(pid),
          }};
          arenaRegenerate('/regenerate-provider', payload, status, btn,
            'Regenerating video… (may take several minutes)');
        }});
      }});

      document.querySelectorAll('.btn-regenerate-thumbnails').forEach(btn => {{
        btn.addEventListener('click', () => {{
          const pid = btn.dataset.provider;
          const picker = btn.closest('.thumb-picker');
          const status = picker?.querySelector('[data-role="thumb-regen-status"]');
          arenaRegenerate('/regenerate-thumbnails', {{
            provider_id: pid,
            thumbnail_brief: providerThumbBrief(pid),
          }}, status, btn, 'Extracting thumbnail candidates…');
        }});
      }});

      document.querySelectorAll('.thumb-picker').forEach(picker => {{
        const status = picker.querySelector('[data-role="thumb-select-status"]');
        picker.querySelectorAll('.thumb-opt').forEach(btn => {{
          btn.addEventListener('click', async () => {{
            const choice = btn.dataset.choice;
            const apiBase = providerApiBase(picker);
            picker.querySelectorAll('.thumb-opt').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (!apiBase) {{
              setJobStatus(status, 'error', 'Open /arena via preview_server to save poster');
              return;
            }}
            setJobStatus(status, 'running', 'Saving poster…');
            try {{
              const res = await fetch(apiBase + '/select-thumbnail', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ choice }}),
              }});
              const data = await res.json();
              if (!res.ok) throw new Error(data.error || res.statusText);
              setJobStatus(status, 'done', 'Poster saved (' + choice + ')');
            }} catch (e) {{
              setJobStatus(status, 'error', e.message);
              btn.classList.remove('active');
            }}
          }});
        }});
      }});
    }}

    initArenaDashboard();
  </script>
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
