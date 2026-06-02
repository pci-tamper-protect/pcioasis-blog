#!/usr/bin/env python3
"""Assemble generated content variants into a review PR on pcioasis-blog.

Creates a branch named content/<slug>-variants, commits all _variants/ files,
and opens a pull request so the author can review every platform post before
anything is published.

Usage:
    python assemble_pr.py <post_dir> [--repo <owner/repo>] [--base main]

Requires:
    - gh CLI authenticated
    - GH_TOKEN or GITHUB_TOKEN env var for API calls (gh picks this up automatically)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from env_help import check_gh_available, print_gh_setup_commands, print_missing_variants_help

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def git(args: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=cwd, **kwargs)


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def read_manifest(variants_dir: Path) -> dict:
    mp = variants_dir / "manifest.json"
    if mp.exists():
        return json.loads(mp.read_text())
    return {}


def variant_summary(variants_dir: Path) -> str:
    """Build a markdown table summarising all generated variants."""
    PLATFORM_LABELS = {
        "planetkesten.md": ("🌍 planetkesten.com", "Blog — broad audience"),
        "kbroughton.md": ("👨‍💻 kbroughton.github.io", "Blog — technical audience"),
        "linkedin.md": ("💼 LinkedIn", "Short link post + OG card"),
        "bluesky.txt": ("🦋 Bluesky", "Micro-post (≤300 chars)"),
        "mastodon.txt": ("🐘 Mastodon", "Micro-post w/ CW (≤500 chars)"),
        "pixelfed.txt": ("📷 Pixelfed", "Image caption"),
        "clapper.txt": ("🎬 Clapper (primary)", "Short-form video caption"),
        "tiktok-xref.txt": ("🎵 TikTok xref", "Manual xref to Clapper"),
        "douyin-xref.txt": ("🇨🇳 Douyin xref", "Manual xref to Clapper"),
        "rednote-xref.txt": ("📕 RedNote 小红书 xref", "Manual xref to Clapper"),
        "youtube-shorts.txt": ("▶️ YouTube Shorts xref", "Reposts Clapper video"),
        "reels-xref.txt": ("📸 Instagram Reels xref", "Reposts Clapper video"),
        "twitter-xref.txt": ("🔁 Twitter/X xref", "Manual xref to Bluesky"),
        "youtube/script.md": ("📜 YouTube script", "Narration script"),
        "youtube/description.md": ("📝 YouTube description", "Video description"),
        "youtube/chapters.txt": ("⏱ YouTube chapters", "Timestamp list"),
    }
    rows = ["| Platform | Type | Status | Chars |", "|---|---|---|---|"]
    for rel, (label, kind) in PLATFORM_LABELS.items():
        path = variants_dir / rel.replace("/", "/")
        if path.exists():
            chars = len(path.read_text())
            rows.append(f"| {label} | {kind} | ✅ generated | {chars:,} |")
        else:
            rows.append(f"| {label} | {kind} | ❌ missing | — |")
    return "\n".join(rows)


def build_pr_body(post_title: str, canonical: str, variants_dir: Path) -> str:
    summary = variant_summary(variants_dir)
    return f"""## Content Variants Review — {post_title}

Canonical source: [{canonical}]({canonical})

All platform variants were generated from `index.md` via `generate_variants.py`.
Review each file in `_variants/` and edit as needed before approving this PR.

### Generated variants

{summary}

### Publish checklist

- [ ] Review `planetkesten.md` — tone appropriate for general audience?
- [ ] Review `kbroughton.md` — depth appropriate for senior engineers?
- [ ] Review `linkedin.md` — professional tone, correct hashtags?
- [ ] Review `bluesky.txt` — under 300 chars, good hook?
- [ ] Review `mastodon.txt` — CW line accurate, under 500 chars?
- [ ] Review `pixelfed.txt` — image cues match available diagrams?
- [ ] Review `clapper.txt` — HOOK line punchy, talking points clear?
- [ ] Review `youtube/script.md` — natural spoken language, timing reasonable?
- [ ] Approve and merge this PR
- [ ] Trigger `publish-ethical-first.yml` (Phase 4: Bluesky, Mastodon, Pixelfed, **Clapper**, LinkedIn)
- [ ] Record + upload YouTube long-form video using approved script
- [ ] Upload Clapper video (primary short-form)
- [ ] Post short-form xrefs (after Clapper is live): paste Clapper URL into TikTok, Douyin, RedNote, YouTube Shorts, Reels captions
- [ ] Trigger `publish-xref.yml` (Phase 5: TikTok, Douyin, RedNote, YouTube Shorts, Reels, Twitter/X)

> **Publishing order:** Clapper (primary) → ethical-first text (Bluesky, Mastodon) → LinkedIn → wait 24h → dominant cross-references (TikTok, Douyin, RedNote, YouTube Shorts, Reels, Twitter/X, Facebook, Instagram)
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def assemble_pr(post_dir: Path, repo: str, base_branch: str, dry_run: bool) -> None:
    index_file = post_dir / "index.md"
    if not index_file.exists():
        sys.exit(f"No index.md at {index_file}")

    meta = parse_frontmatter(index_file.read_text())
    slug = meta.get("slug") or post_dir.name
    post_title = meta.get("title", slug)

    variants_dir = post_dir / "_variants"
    if not variants_dir.exists():
        print_missing_variants_help(variants_dir, post_dir)

    manifest = read_manifest(variants_dir)
    section = post_dir.parent.name.lower()
    canonical = manifest.get("canonical", f"https://blog.pcioasis.com/posts/{section}/{slug}/")

    branch_name = f"content/{slug}-variants"

    # Find the git root (pcioasis-blog root)
    result = git(["rev-parse", "--show-toplevel"], cwd=post_dir)
    repo_root = Path(result.stdout.strip())

    print(f"Post:     {post_title}")
    print(f"Slug:     {slug}")
    print(f"Branch:   {branch_name}")
    print(f"Repo:     {repo}")
    print(f"Dry-run:  {dry_run}")

    if dry_run:
        print("\n[dry-run] Would create branch, commit _variants/, and open PR.")
        return

    check_gh_available()
    if subprocess.run(
        ["gh", "auth", "status"],
        cwd=repo_root,
        capture_output=True,
    ).returncode != 0:
        print_gh_setup_commands(reason="GitHub CLI not authenticated.")
        sys.exit(1)

    # Create branch from base
    git(["checkout", "-B", branch_name, f"origin/{base_branch}"], cwd=repo_root)

    # _variants/ is gitignored on main; force-add so review branches can commit them.
    rel_variants = variants_dir.relative_to(repo_root)
    git(["add", "-f", str(rel_variants)], cwd=repo_root)

    status = git(["status", "--short"], cwd=repo_root)
    if not status.stdout.strip():
        print(
            "Nothing to commit — variants already up to date on this branch, "
            f"or no files under {rel_variants}."
        )
        return

    git(
        [
            "commit",
            "-m",
            f"content({slug}): add generated platform variants\n\nGenerated by generate_variants.py from index.md",
        ],
        cwd=repo_root,
    )

    # Push branch
    git(["push", "-u", "origin", branch_name], cwd=repo_root)

    # Open PR via gh CLI
    pr_body = build_pr_body(post_title, canonical, variants_dir)
    pr_result = run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--title",
            f"Content variants: {post_title}",
            "--body",
            pr_body,
            "--base",
            base_branch,
            "--head",
            branch_name,
        ],
        cwd=repo_root,
    )

    pr_url = pr_result.stdout.strip()
    print(f"\nPR opened: {pr_url}")
    print(
        "Review each _variants/ file, edit as needed, then approve to proceed to publishing."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble content variants into a review PR"
    )
    parser.add_argument(
        "post_dir", type=Path, help="Hugo post directory containing index.md"
    )
    parser.add_argument(
        "--repo",
        default="pci-tamper-protect/pcioasis-blog",
        help="GitHub owner/repo (default: pci-tamper-protect/pcioasis-blog)",
    )
    parser.add_argument(
        "--base", default="main", help="Base branch for the PR (default: main)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    assemble_pr(args.post_dir.resolve(), args.repo, args.base, args.dry_run)


if __name__ == "__main__":
    main()
