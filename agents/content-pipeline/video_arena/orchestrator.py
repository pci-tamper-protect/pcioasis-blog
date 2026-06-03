"""Run the multi-provider video arena for one post."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_arena.critique import write_critique
from video_arena.prompt_builder import build_video_prompt
from video_arena.providers import all_providers
from video_arena.review import write_review_html
from video_arena.thumbnails import extract_thumbnail_candidates


def _parse_frontmatter_title(index_md: Path) -> str:
    text = index_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    import yaml

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return ""
    return str(meta.get("title") or "")


def run_arena(
    post_dir: Path,
    *,
    only: list[str] | None = None,
    skip_critique: bool = False,
) -> Path:
    """Generate video candidates under post_dir/_variants/video-arena/."""
    post_dir = post_dir.resolve()
    index_md = post_dir / "index.md"
    if not index_md.is_file():
        raise FileNotFoundError(f"No index.md at {index_md}")

    title = _parse_frontmatter_title(index_md)
    prompt, ref_image = build_video_prompt(post_dir, title=title)
    arena_dir = post_dir / "_variants" / "video-arena"
    arena_dir.mkdir(parents=True, exist_ok=True)
    (arena_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    provider_classes = all_providers()
    if only:
        only_set = set(only)
        provider_classes = [p for p in provider_classes if p.provider_id in only_set]

    results: dict[str, Any] = {}
    for pcls in provider_classes:
        provider = pcls()
        print(f"  [{provider.provider_id}] starting...", flush=True)
        out_sub = arena_dir / provider.provider_id
        result = provider.run(prompt, out_sub, reference_image=ref_image)
        print(f"    -> {result.status}: {result.message}", flush=True)

        thumb_meta: dict[str, Any] = {}
        if result.status == "ok" and result.video_path:
            video_file = Path(result.video_path)
            if video_file.is_file():
                thumb_meta = extract_thumbnail_candidates(video_file, out_sub)
                n = len(thumb_meta.get("candidates", []))
                if n:
                    print(f"    -> thumbnails: {n} candidates", flush=True)
                elif thumb_meta.get("error"):
                    print(f"    -> thumbnails: skipped ({thumb_meta['error']})", flush=True)

        results[provider.provider_id] = {
            "display_name": provider.display_name,
            "status": result.status,
            "message": result.message,
            "model": result.model,
            "video_path": result.video_path,
            "elapsed_seconds": result.elapsed_seconds,
            "thumbnails": thumb_meta.get("candidates", []),
            "thumbnail_selected": thumb_meta.get("selected"),
        }

        if not skip_critique and result.status in ("ok", "failed", "skipped"):
            job_path = out_sub / "job.json"
            job_data = json.loads(job_path.read_text()) if job_path.is_file() else {}
            try:
                write_critique(
                    provider.provider_id,
                    prompt,
                    job_data,
                    out_sub / "critique.md",
                )
            except SystemExit:
                (out_sub / "critique.md").write_text(
                    "# Critique skipped\n\nLLM credentials not configured.\n",
                    encoding="utf-8",
                )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "title": title,
        "post_dir": str(post_dir),
        "prompt": prompt,
        "reference_image": str(ref_image) if ref_image else None,
        "providers": results,
    }
    (arena_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    review_path = write_review_html(arena_dir, manifest)
    print(f"\nReview: {review_path}")
    if not (arena_dir / "WINNER.txt").is_file():
        (arena_dir / "WINNER.txt").write_text(
            "# Set winner after human review, e.g.:\n# vertex_veo — best motion on diagram anchor\n",
            encoding="utf-8",
        )
    return arena_dir
