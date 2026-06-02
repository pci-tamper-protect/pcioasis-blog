"""Generate static HTML comparison page for human video arena review."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable


def _video_src(provider_id: str, href_for: Callable[[str], str]) -> str:
    return href_for(provider_id)


def build_review_html(
    arena_dir: Path,
    manifest: dict,
    *,
    href_for: Callable[[str], str] | None = None,
    back_href: str | None = None,
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
            video_tag = (
                f'<video controls playsinline src="{src}" '
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

        rows.append(
            f"""
            <section class="card">
              <h2>{html.escape(data.get('display_name', pid))}</h2>
              <p><strong>Status:</strong> {html.escape(status)} — {html.escape(data.get('message', ''))}</p>
              {video_tag}
              {critique_html}
              <label>Human score (1-5 motion): <input type="number" min="1" max="5" name="{pid}_motion"></label>
              <label>Notes: <textarea name="{pid}_notes" rows="2" style="width:100%"></textarea></label>
            </section>
            """
        )

    post_title = html.escape(manifest.get("title", "Video arena"))
    prompt_pre = html.escape(manifest.get("prompt", ""))
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
  </style>
</head>
<body>
  {back_link}
  <h1>Video arena — {post_title}</h1>
  <p>Compare providers side-by-side. Pick one clip for <code>_variants/clapper/clip.mp4</code>, then record in <code>WINNER.txt</code>.</p>
  <h2>Shared prompt</h2>
  <div class="prompt">{prompt_pre}</div>
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


def write_review_html(arena_dir: Path, manifest: dict) -> Path:
    """Write review.html listing provider slots with video tags when present."""
    page = build_review_html(arena_dir, manifest)
    out = arena_dir / "review.html"
    out.write_text(page, encoding="utf-8")
    return out
