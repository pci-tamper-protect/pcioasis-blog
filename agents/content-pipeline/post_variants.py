#!/usr/bin/env python3
"""Post platform variants to social media.

Text platforms — Playwright browser sessions (one-time login, headless after):
  facebook, threads, twitter, linkedin

API platforms — env var tokens:
  bluesky   BLUESKY_HANDLE + BLUESKY_APP_PASSWORD
  mastodon  MASTODON_ACCESS_TOKEN + MASTODON_SERVER (default: infosec.exchange)

Video platforms — needs a video file; posts the caption/script and skips:
  tiktok, instagram, snapchat, youtube_shorts

Usage:
  # One-time login per Playwright platform (headed browser — do this first)
  uv run --project agents/content-pipeline --extra social \\
    python agents/content-pipeline/post_variants.py --login facebook

  # Post all text platforms from a variants directory
  uv run --project agents/content-pipeline --extra social \\
    python agents/content-pipeline/post_variants.py \\
    content/posts/district31/cisa-brief

  # Post specific platforms only
  uv run --project agents/content-pipeline --extra social \\
    python agents/content-pipeline/post_variants.py \\
    content/posts/district31/cisa-brief --platforms bluesky,mastodon,linkedin

  # Dry run — print what would be posted without posting
  uv run --project agents/content-pipeline --extra social \\
    python agents/content-pipeline/post_variants.py \\
    content/posts/district31/cisa-brief --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

# Browser sessions stored outside the repo — never committed
SESSIONS_DIR = Path.home() / ".config" / "pcioasis-posting" / "sessions"

# platform key → relative path inside the post directory
VARIANT_FILES: dict[str, str] = {
    "facebook":     "_variants/facebook.txt",
    "threads":      "_variants/threads.txt",
    "twitter":      "_variants/twitter-xref.txt",
    "linkedin":     "_variants/linkedin.md",
    "bluesky":      "_variants/bluesky.txt",
    "mastodon":     "_variants/mastodon.txt",
    "tiktok":       "_variants/tiktok.txt",
    "snapchat":     "_variants/snapchat.txt",
    "instagram":    "_variants/reels-xref.txt",
    "youtube":      "_variants/youtube/description.md",
}

VIDEO_PLATFORMS = {"tiktok", "snapchat", "instagram", "youtube"}

LOGIN_URLS: dict[str, str] = {
    "facebook":   "https://www.facebook.com/login",
    "threads":    "https://www.threads.net/login",
    "twitter":    "https://x.com/i/flow/login",
    "linkedin":   "https://www.linkedin.com/login",
    "tiktok":     "https://www.tiktok.com/login",
    "voteearly":  "https://voteearly.tools/groups",
}

# Per-platform: lambda(url) → True when login is complete and session should be saved.
# Default (None) uses the generic "no login/signin in URL" check.
LOGIN_DONE: dict[str, object] = {
    # CF Access routes through accounts.google.com (no "login" in URL), which would
    # falsely trigger the generic check. Wait for the final redirect back to our domain.
    "voteearly": lambda url: "voteearly.tools" in url and "cloudflareaccess" not in url,
    # FB login via Google OAuth: URL hits facebook.com early but c_user/xs cookies
    # aren't written yet. Wait until we're on a real FB page past any checkpoint.
    "facebook": lambda url: (
        url.startswith("https://www.facebook.com/")
        and "login" not in url
        and "checkpoint" not in url
        and "recover" not in url
    ),
}


# ---------------------------------------------------------------------------
# Variant text parsing
# ---------------------------------------------------------------------------

def parse_variant(platform: str, raw: str) -> dict[str, str]:
    """Extract postable fields from a variant file."""
    text = raw.strip()

    if platform in ("facebook", "linkedin"):
        lines = text.splitlines()
        body = "\n".join(l for l in lines if not l.startswith("META_DESCRIPTION:")).strip()
        return {"text": body}

    if platform == "mastodon":
        m = re.match(r"CW:\s*(.+?)\n+(.*)", text, re.DOTALL)
        if m:
            return {"spoiler_text": m.group(1).strip(), "status": m.group(2).strip()}
        return {"spoiler_text": "", "status": text}

    if platform in ("tiktok", "snapchat"):
        m = re.search(r"^CAPTION:\s*(.+)$", text, re.MULTILINE)
        return {"caption": m.group(1).strip() if m else text, "full_script": text}

    if platform == "instagram":
        return {"caption": text}

    if platform == "youtube":
        lines = text.splitlines()
        body = "\n".join(l for l in lines if not l.startswith("META_DESCRIPTION:")).strip()
        return {"description": body}

    # bluesky, threads, twitter
    return {"text": text}


# ---------------------------------------------------------------------------
# API posters: Bluesky, Mastodon
# ---------------------------------------------------------------------------

def post_bluesky(parsed: dict, dry_run: bool) -> bool:
    handle = os.environ.get("BLUESKY_HANDLE")
    pw = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not pw:
        print("  bluesky: set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD")
        return False
    text = parsed["text"]
    if dry_run:
        print(f"  [dry-run] bluesky ({len(text)} chars): {text[:100]}")
        return True
    try:
        from atproto import Client
        client = Client()
        client.login(handle, pw)
        client.send_post(text)
        print("  bluesky: posted ✓")
        return True
    except Exception as e:
        print(f"  bluesky: FAILED — {e}")
        return False


def post_mastodon(parsed: dict, dry_run: bool) -> bool:
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    server = os.environ.get("MASTODON_SERVER", "infosec.exchange")
    if not token:
        print("  mastodon: set MASTODON_ACCESS_TOKEN (and optionally MASTODON_SERVER)")
        return False
    spoiler = parsed.get("spoiler_text", "")
    status = parsed.get("status", "")
    if dry_run:
        print(f"  [dry-run] mastodon CW={spoiler[:50]} | {status[:80]}")
        return True
    try:
        import requests
        resp = requests.post(
            f"https://{server}/api/v1/statuses",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": status, "spoiler_text": spoiler},
            timeout=15,
        )
        resp.raise_for_status()
        print(f"  mastodon: posted ✓ → {resp.json().get('url', '')}")
        return True
    except Exception as e:
        print(f"  mastodon: FAILED — {e}")
        return False


# ---------------------------------------------------------------------------
# Playwright: one-time login
# ---------------------------------------------------------------------------

async def browser_login(platform: str) -> None:
    """Open a detached Chrome window for login; connect via CDP to save session."""
    import asyncio
    import subprocess
    import sys
    import tempfile
    import time
    from playwright.async_api import async_playwright, Error as PlaywrightError

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{platform}.json"
    login_url = LOGIN_URLS.get(platform, f"https://www.{platform}.com")

    CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    CDP_PORT = 9355  # unlikely to conflict with other tools

    if not Path(CHROME).exists():
        sys.exit("Google Chrome not found at expected path — install Chrome and retry.")

    tmp_profile = tempfile.mkdtemp(prefix="pw-login-")
    print(f"\nOpening Chrome for {platform}. Log in — session saves automatically.")
    print("(Chrome is launched independently so keyboard input works normally.)")

    proc = subprocess.Popen(
        [
            CHROME,
            f"--remote-debugging-port={CDP_PORT}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={tmp_profile}",
            login_url,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # detach from terminal — macOS gives it proper keyboard focus
    )

    # Wait for Chrome to start accepting CDP connections
    cdp_url = f"http://localhost:{CDP_PORT}"
    for _ in range(20):
        try:
            import urllib.request
            urllib.request.urlopen(f"{cdp_url}/json/version", timeout=1)
            break
        except Exception:
            await asyncio.sleep(0.5)
    else:
        proc.terminate()
        sys.exit("Chrome did not start in time.")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            print("Complete login in the Chrome window — this terminal will wait (3 min timeout).")
            done_fn = LOGIN_DONE.get(platform) or (
                lambda url: "login" not in url and "signin" not in url and "sign-in" not in url
            )
            # Poll page.url rather than wait_for_url — the latter uses expect_navigation
            # which aborts on the CF Access → Google OAuth redirect chain.
            deadline = asyncio.get_event_loop().time() + 180
            while asyncio.get_event_loop().time() < deadline:
                try:
                    if done_fn(page.url):
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            else:
                print("Login timed out — session not saved.")

            try:
                await asyncio.sleep(6)
                await ctx.storage_state(path=str(session_file))
                print(f"Session saved → {session_file}")
            except PlaywrightError:
                print("Browser closed before session could be saved — try again.")
        finally:
            proc.terminate()


# ---------------------------------------------------------------------------
# Playwright: platform-specific post actions
# ---------------------------------------------------------------------------

async def _post_facebook(page, text: str) -> None:
    await page.goto("https://www.facebook.com")
    await page.wait_for_load_state("networkidle", timeout=20_000)
    # Open composer — try multiple known selectors
    for sel in [
        '[aria-label="Create a post"]',
        '[placeholder*="mind"]',
        '[data-testid="status-attachment-mentions-input"]',
    ]:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(1500)
    # Fill text
    textbox = page.locator('[role="textbox"][contenteditable="true"]').first
    await textbox.fill(text)
    await page.wait_for_timeout(800)
    # Post
    for sel in ['[aria-label="Post"]', '[data-testid="react-composer-post-button"]']:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(3000)


async def _post_threads(page, text: str) -> None:
    await page.goto("https://www.threads.net")
    await page.wait_for_load_state("networkidle", timeout=20_000)
    for sel in ['[aria-label="New thread"]', 'text="New thread"', '[aria-label="Create"]']:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(1500)
    textbox = page.locator('[contenteditable="true"]').first
    await textbox.fill(text)
    await page.wait_for_timeout(800)
    for sel in ['[aria-label="Post"]', 'button:has-text("Post")']:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(3000)


async def _post_twitter(page, text: str) -> None:
    await page.goto("https://x.com/compose/tweet")
    await page.wait_for_load_state("networkidle", timeout=20_000)
    for sel in [
        '[data-testid="tweetTextarea_0"]',
        '[aria-label="Tweet text"]',
        '[aria-label="Post text"]',
    ]:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.fill(text)
            break
    await page.wait_for_timeout(800)
    for sel in ['[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]']:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(3000)


async def _post_linkedin(page, text: str) -> None:
    await page.goto("https://www.linkedin.com/feed/")
    await page.wait_for_load_state("networkidle", timeout=20_000)
    for sel in [
        'button:has-text("Start a post")',
        '[aria-label*="Start a post"]',
        '[data-control-name="share.sharebox_feed_create_update"]',
    ]:
        if await page.locator(sel).count() > 0:
            await page.locator(sel).first.click()
            break
    await page.wait_for_timeout(1500)
    textbox = page.locator('[role="textbox"][contenteditable="true"]').first
    await textbox.fill(text)
    await page.wait_for_timeout(800)
    # Post button is usually last .post button in the modal
    for sel in ['button.share-actions__primary-action', 'button:has-text("Post")']:
        btns = page.locator(sel)
        if await btns.count() > 0:
            await btns.last.click()
            break
    await page.wait_for_timeout(3000)


PW_POSTERS = {
    "facebook": _post_facebook,
    "threads":  _post_threads,
    "twitter":  _post_twitter,
    "linkedin": _post_linkedin,
}


async def browser_post(platform: str, text: str, dry_run: bool) -> bool:
    session_file = SESSIONS_DIR / f"{platform}.json"
    if not session_file.exists():
        print(f"  {platform}: no saved session — run: post_variants.py --login {platform}")
        return False
    if dry_run:
        print(f"  [dry-run] {platform} ({len(text)} chars): {text[:100]}")
        return True
    poster = PW_POSTERS[platform]
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state=str(session_file))
        page = await ctx.new_page()
        try:
            await poster(page, text)
            # Refresh saved session in case tokens rotated
            await ctx.storage_state(path=str(session_file))
            print(f"  {platform}: posted ✓")
            return True
        except Exception as e:
            print(f"  {platform}: FAILED — {e}")
            return False
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def post_all(post_dir: Path, platforms: list[str], dry_run: bool) -> None:
    results: dict[str, bool] = {}

    for platform in platforms:
        variant_rel = VARIANT_FILES.get(platform)
        if not variant_rel:
            print(f"  {platform}: unknown platform")
            results[platform] = False
            continue

        variant_path = post_dir / variant_rel
        if not variant_path.exists():
            print(f"  {platform}: variant file missing ({variant_path.name}) — run generate_variants.py first")
            results[platform] = False
            continue

        raw = variant_path.read_text(encoding="utf-8")
        parsed = parse_variant(platform, raw)

        if platform in VIDEO_PLATFORMS:
            script_path = variant_path.relative_to(post_dir)
            print(f"  {platform}: video platform — post manually using {script_path}")
            results[platform] = False
            continue

        if platform == "bluesky":
            results[platform] = post_bluesky(parsed, dry_run)
        elif platform == "mastodon":
            results[platform] = post_mastodon(parsed, dry_run)
        elif platform in PW_POSTERS:
            results[platform] = await browser_post(platform, parsed["text"], dry_run)
        else:
            print(f"  {platform}: no poster implemented")
            results[platform] = False

    ok = [p for p, v in results.items() if v]
    fail = [p for p, v in results.items() if not v]
    print(f"\nDone — {len(ok)} posted, {len(fail)} skipped/failed")
    if fail:
        print(f"  Skipped/failed: {', '.join(fail)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

ALL_PLATFORMS = list(VARIANT_FILES.keys())


def main() -> None:
    global SESSIONS_DIR
    parser = argparse.ArgumentParser(
        description="Post content variants to social platforms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available platforms: {', '.join(ALL_PLATFORMS)}",
    )
    parser.add_argument("post_dir", nargs="?", type=Path,
                        help="Hugo post directory containing _variants/")
    parser.add_argument("--login", metavar="PLATFORM",
                        help="Open browser for one-time login to a Playwright platform")
    parser.add_argument("--platforms", metavar="P1,P2",
                        help="Comma-separated subset of platforms to post (default: all text platforms)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be posted without making any requests")
    parser.add_argument("--sessions-dir", type=Path,
                        help=f"Override session storage directory (default: {SESSIONS_DIR})")
    args = parser.parse_args()

    if args.sessions_dir:
        SESSIONS_DIR = args.sessions_dir
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if args.login:
        if args.login not in LOGIN_URLS:
            sys.exit(f"--login supports: {', '.join(LOGIN_URLS)}")
        asyncio.run(browser_login(args.login))
        return
        return

    if not args.post_dir:
        parser.print_help()
        sys.exit(0)

    post_dir = args.post_dir.resolve()
    if not (post_dir / "_variants").exists():
        sys.exit(f"No _variants/ in {post_dir} — run generate_variants.py first")

    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
        bad = [p for p in platforms if p not in ALL_PLATFORMS]
        if bad:
            sys.exit(f"Unknown platforms: {bad}. Valid: {ALL_PLATFORMS}")
    else:
        # Default: all non-video text platforms
        platforms = [p for p in ALL_PLATFORMS if p not in VIDEO_PLATFORMS]

    print(f"Posting variants from: {post_dir}")
    if args.dry_run:
        print("(dry run — no requests will be made)\n")
    asyncio.run(post_all(post_dir, platforms, args.dry_run))


if __name__ == "__main__":
    main()
