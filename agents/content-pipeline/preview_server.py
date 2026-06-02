#!/usr/bin/env python3
"""Local preview server for generated content variants.

Serves mobile-friendly HTML mockups of each platform's post so the author
can review on an Android device (or desktop) before the PR is opened.

Usage:
    python preview_server.py <post_dir>
    python preview_server.py ~/projectos/pcioasis-blog/content/posts/zkTLS/zktls-proof-of-provenance

Then open http://<your-lan-ip>:5050/ on your phone.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from wsgiref.simple_server import make_server

try:
    import markdown

    _MD_AVAILABLE = True
except ImportError:
    _MD_AVAILABLE = False

PORT = 5050

PLATFORM_META = {
    # Blogs
    "planetkesten": {
        "label": "planetkesten.com",
        "color": "#1976d2",
        "icon": "🌍",
        "type": "blog",
    },
    "kbroughton": {
        "label": "kbroughton.github.io",
        "color": "#455a64",
        "icon": "👨‍💻",
        "type": "blog",
    },
    # Professional
    "linkedin": {
        "label": "LinkedIn",
        "color": "#0a66c2",
        "icon": "💼",
        "type": "social",
    },
    # Ethical-first micro-social
    "bluesky": {"label": "Bluesky", "color": "#0085ff", "icon": "🦋", "type": "micro"},
    "mastodon": {
        "label": "Mastodon (infosec.exchange)",
        "color": "#563acc",
        "icon": "🐘",
        "type": "micro",
    },
    "pixelfed": {
        "label": "Pixelfed",
        "color": "#e040fb",
        "icon": "📷",
        "type": "social",
    },
    # Short-form video — Clapper primary
    "clapper": {
        "label": "Clapper (primary)",
        "color": "#ff4500",
        "icon": "🎬",
        "type": "video",
    },
    "tiktok-xref": {
        "label": "TikTok (xref)",
        "color": "#010101",
        "icon": "🎵",
        "type": "xref",
    },
    "douyin-xref": {
        "label": "Douyin (xref)",
        "color": "#fe2c55",
        "icon": "🇨🇳",
        "type": "xref",
    },
    "rednote-xref": {
        "label": "RedNote 小红书 (xref)",
        "color": "#ff2442",
        "icon": "📕",
        "type": "xref",
    },
    "youtube-shorts": {
        "label": "YouTube Shorts (xref)",
        "color": "#ff0000",
        "icon": "▶️",
        "type": "xref",
    },
    "reels-xref": {
        "label": "Instagram Reels (xref)",
        "color": "#c13584",
        "icon": "📸",
        "type": "xref",
    },
    # Text dominant xref
    "twitter-xref": {
        "label": "Twitter/X (xref)",
        "color": "#1da1f2",
        "icon": "🔁",
        "type": "xref",
    },
    # Long-form YouTube
    "youtube/script": {
        "label": "YouTube — Narration Script",
        "color": "#ff0000",
        "icon": "📜",
        "type": "video",
    },
    "youtube/description": {
        "label": "YouTube — Description",
        "color": "#ff0000",
        "icon": "📝",
        "type": "video",
    },
    "youtube/chapters": {
        "label": "YouTube — Chapters",
        "color": "#ff0000",
        "icon": "⏱",
        "type": "video",
    },
}

NAV_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f5f5f5; color: #212121; }
header { background: #212121; color: #fff; padding: 16px 20px; position: sticky;
         top: 0; z-index: 10; }
header h1 { font-size: 1rem; font-weight: 600; }
header small { opacity: .7; font-size: .8rem; display: block; margin-top: 2px; }
nav { display: flex; flex-wrap: wrap; gap: 8px; padding: 16px 20px;
      background: #fff; border-bottom: 1px solid #e0e0e0; }
nav a { text-decoration: none; padding: 6px 12px; border-radius: 20px;
        font-size: .85rem; border: 1px solid #ddd; color: #333;
        white-space: nowrap; }
nav a:hover { background: #f0f0f0; }
nav a.active { color: #fff; border-color: transparent; }
main { max-width: 480px; margin: 0 auto; padding: 20px 16px; }
.card { background: #fff; border-radius: 12px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,.12); margin-bottom: 20px; }
.card-header { padding: 14px 16px; display: flex; align-items: center; gap: 10px; }
.card-header .icon { font-size: 1.4rem; }
.card-header .name { font-weight: 600; font-size: .95rem; }
.card-header .badge { margin-left: auto; font-size: .7rem; padding: 2px 8px;
                       border-radius: 10px; background: rgba(0,0,0,.08); }
.card-body { padding: 16px; border-top: 1px solid #f0f0f0; }
.card-body pre { background: #f8f8f8; border-radius: 6px; padding: 12px;
                  font-size: .82rem; white-space: pre-wrap; word-break: break-word;
                  line-height: 1.5; }
.card-body .prose { font-size: .92rem; line-height: 1.65; }
.card-body .prose h1 { font-size: 1.2rem; margin: 0 0 12px; }
.card-body .prose h2 { font-size: 1.05rem; margin: 16px 0 6px; }
.card-body .prose p  { margin-bottom: 10px; }
.card-body .prose ul, .card-body .prose ol { margin: 8px 0 10px 20px; }
.char-count { font-size: .75rem; color: #777; margin-top: 8px; text-align: right; }
.warn { color: #c62828; }
.index-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.index-tile { background: #fff; border-radius: 10px; padding: 16px 14px;
               box-shadow: 0 1px 3px rgba(0,0,0,.1); text-decoration: none;
               color: inherit; display: flex; flex-direction: column; gap: 6px; }
.index-tile .icon { font-size: 1.8rem; }
.index-tile .name { font-weight: 600; font-size: .9rem; }
.index-tile .type { font-size: .75rem; color: #888; }
"""


def md_to_html(text: str) -> str:
    if _MD_AVAILABLE:
        return markdown.markdown(text, extensions=["fenced_code", "tables"])
    # fallback: very basic conversion
    escaped = html.escape(text)
    escaped = re.sub(r"^## (.+)$", r"<h2>\1</h2>", escaped, flags=re.M)
    escaped = re.sub(r"^# (.+)$", r"<h1>\1</h1>", escaped, flags=re.M)
    escaped = re.sub(r"\n\n", "</p><p>", escaped)
    return f"<p>{escaped}</p>"


def read_variants(variants_dir: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for key in PLATFORM_META:
        # key may contain a slash (youtube/script)
        rel = key.replace("/", os.sep if False else "/")
        for ext in (".md", ".txt"):
            path = variants_dir / (rel + ext)
            if path.exists():
                data[key] = path.read_text(encoding="utf-8")
                break
    return data


def read_manifest(variants_dir: Path) -> dict:
    mp = variants_dir / "manifest.json"
    if mp.exists():
        return json.loads(mp.read_text())
    return {}


def platform_card(key: str, text: str) -> str:
    meta = PLATFORM_META.get(
        key, {"label": key, "color": "#888", "icon": "📄", "type": "other"}
    )
    color = meta["color"]
    is_prose = meta["type"] == "blog"
    char_count = len(text)
    limits = {
        "bluesky": 300,
        "mastodon": 500,
        "clapper": 2200,
        "twitter-xref": 280,
        "tiktok-xref": 150,
    }
    limit = limits.get(key)
    warn = limit and char_count > limit

    if is_prose:
        body = f'<div class="prose">{md_to_html(text)}</div>'
    else:
        body = f"<pre>{html.escape(text)}</pre>"

    count_html = ""
    if limit:
        cls = "char-count warn" if warn else "char-count"
        over = f" ⚠ over limit ({limit})" if warn else ""
        count_html = f'<p class="{cls}">{char_count} chars{over}</p>'

    return f"""
<div class="card" id="{html.escape(key)}">
  <div class="card-header" style="border-left: 4px solid {color}">
    <span class="icon">{meta['icon']}</span>
    <span class="name">{html.escape(meta['label'])}</span>
    <span class="badge">{meta['type']}</span>
  </div>
  <div class="card-body">{body}{count_html}</div>
</div>
"""


def render_page(title: str, body: str, active: str = "") -> str:
    nav_links = []
    for k, m in PLATFORM_META.items():
        cls = ' class="active"' if k == active else ""
        style = f' style="background:{m["color"]}"' if k == active else ""
        anchor = k.replace("/", "-")
        nav_links.append(
            f'<a href="/{anchor}"{cls}{style}>{m["icon"]} {m["label"]}</a>'
        )
    nav_html = "\n".join(nav_links)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Content Preview</title>
<style>{NAV_CSS}</style>
</head>
<body>
<header>
  <h1>📱 Content Preview</h1>
  <small>{html.escape(title)}</small>
</header>
<nav>{nav_html}</nav>
<main>{body}</main>
</body>
</html>"""


def render_index(manifest: dict, variants: dict[str, str]) -> str:
    post_title = manifest.get("title", "Unknown post")
    canonical = manifest.get("canonical", "")
    tiles = []
    for key, meta in PLATFORM_META.items():
        has = "✓" if key in variants else "✗"
        anchor = key.replace("/", "-")
        tiles.append(
            f'<a class="index-tile" href="/{anchor}" '
            f'style="border-top: 3px solid {meta["color"]}">'
            f'<span class="icon">{meta["icon"]}</span>'
            f'<span class="name">{html.escape(meta["label"])}</span>'
            f'<span class="type">{meta["type"]} {has}</span>'
            f"</a>"
        )
    grid = f'<div class="index-grid">{"".join(tiles)}</div>'
    info = f"<p style='margin-bottom:16px;font-size:.85rem;color:#555'>Canonical: <a href='{html.escape(canonical)}'>{html.escape(canonical)}</a></p>"
    return render_page(post_title, info + grid, active="")


def wsgi_app(variants_dir: Path):
    """Return a minimal WSGI application."""

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/").lstrip("/")
        variants = read_variants(variants_dir)
        manifest = read_manifest(variants_dir)
        post_title = manifest.get("title", variants_dir.parent.name)

        if not path or path == "index.html":
            body = render_index(manifest, variants)
            status = "200 OK"
        else:
            # Nav links are generated as key.replace("/", "-"), so reverse that mapping.
            url_to_key = {k.replace("/", "-"): k for k in PLATFORM_META}
            key = url_to_key.get(path, path)
            if key in variants:
                card_html = platform_card(key, variants[key])
                body = render_page(post_title, card_html, active=key)
                status = "200 OK"
            else:
                body = render_page(
                    "Not found", "<p>Variant not found. Has it been generated yet?</p>"
                )
                status = "404 Not Found"

        encoded = body.encode("utf-8")
        start_response(
            status,
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(encoded))),
            ],
        )
        return [encoded]

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview generated content variants")
    parser.add_argument(
        "post_dir",
        type=Path,
        help="Hugo post directory (must contain _variants/ subdirectory)",
    )
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    variants_dir = args.post_dir.resolve() / "_variants"
    if not variants_dir.exists():
        from env_help import print_missing_variants_help

        print_missing_variants_help(variants_dir, args.post_dir.resolve())

    import socket

    hostname = socket.gethostname()
    try:
        lan_ip = socket.gethostbyname(hostname)
    except Exception:
        lan_ip = "127.0.0.1"

    print("Preview server running:")
    print(f"  Local:   http://localhost:{args.port}/")
    print(f"  Network: http://{lan_ip}:{args.port}/  (open on Android)")
    print("Press Ctrl-C to stop.")

    httpd = make_server("0.0.0.0", args.port, wsgi_app(variants_dir))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


import os  # noqa: E402 (needed by read_variants path logic)

if __name__ == "__main__":
    main()
