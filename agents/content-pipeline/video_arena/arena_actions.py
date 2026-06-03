"""Arena dashboard actions: regenerate prompt, provider video, or final pass."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_arena.orchestrator import _parse_frontmatter_title, run_arena
from video_arena.prompt_builder import build_video_prompt, find_reference_image
from video_arena.prompt_store import (
    load_arena_agent_context,
    load_final_pass_brief,
    load_prompt_text,
    save_arena_prompt,
    save_final_pass_brief,
)
from video_arena.review import load_arena_manifest, write_review_html

FINAL_PASS_SPEC = """\
You are helping an editor combine the BEST parts of several text-to-video arena clips
into one Clapper-ready short. You have NOT seen pixels — only metadata and human notes.

Write a practical **final-pass combine brief** (≤250 words) the downstream agent can follow:
- Per provider id (azure_sora, vertex_veo, etc.): what to borrow (timing, motion, lighting, framing)
- What to avoid (e.g. blank lead-in frames, artifacts)
- Assembly guidance: order of beats, target duration, style constraints
- If a WINNER is named, say whether to use it as the base plate or only as reference

Use clear bullet lists. No markdown code fences.
"""


def rebuild_prompt_from_clapper(post_dir: Path, arena_dir: Path) -> dict[str, Any]:
    """Rebuild prompt.txt from _variants/clapper.txt (overwrites manual edits)."""
    post_dir = post_dir.resolve()
    index_md = post_dir / "index.md"
    if not index_md.is_file():
        raise FileNotFoundError(f"No index.md at {index_md}")

    title = _parse_frontmatter_title(index_md)
    prompt, ref = build_video_prompt(post_dir, title=title)
    save_arena_prompt(arena_dir, prompt)
    return {
        "prompt": prompt,
        "reference_image": str(ref) if ref else None,
    }


def regenerate_all_provider_videos(
    post_dir: Path,
    arena_dir: Path,
    provider_ids: list[str] | None = None,
    *,
    skip_critique: bool = True,
) -> list[str]:
    """Re-run T2V for multiple providers (defaults to keys in manifest)."""
    manifest = load_arena_manifest(arena_dir)
    if manifest is None:
        raise FileNotFoundError("manifest.json missing")

    ids = provider_ids or list(manifest.get("providers", {}).keys())
    if not ids:
        raise ValueError("no providers in manifest")

    prompt = load_prompt_text(arena_dir, manifest)
    if not prompt:
        raise ValueError("prompt.txt is empty — save or regenerate source text first")

    run_arena(post_dir, only=ids, skip_critique=skip_critique)
    return ids


def regenerate_provider_video(
    post_dir: Path,
    arena_dir: Path,
    provider_id: str,
    *,
    skip_critique: bool = True,
) -> dict[str, Any]:
    """Re-run T2V for one provider using current prompt.txt."""
    manifest = load_arena_manifest(arena_dir)
    if manifest is None:
        raise FileNotFoundError("manifest.json missing — run generate_video_arena.py first")

    prompt = load_prompt_text(arena_dir, manifest)
    if not prompt:
        raise ValueError("prompt.txt is empty — save or regenerate source text first")

    run_arena(post_dir, only=[provider_id], skip_critique=skip_critique)
    manifest = load_arena_manifest(arena_dir) or {}
    provider = manifest.get("providers", {}).get(provider_id, {})
    return {
        "provider_id": provider_id,
        "status": provider.get("status"),
        "message": provider.get("message"),
    }


def _parse_winner_id(winner_line: str) -> str:
    line = winner_line.strip().split("#", 1)[0].strip()
    if not line:
        return ""
    return line.split()[0].strip()


def _collect_provider_notes(arena_dir: Path) -> str:
    chunks: list[str] = []
    for sub in sorted(arena_dir.iterdir()):
        if not sub.is_dir() or sub.name in ("final_pass",):
            continue
        critique = sub / "critique.md"
        job = sub / "job.json"
        if job.is_file():
            data = json.loads(job.read_text(encoding="utf-8"))
            chunks.append(
                f"### {sub.name}\nstatus={data.get('status')} "
                f"message={data.get('message', '')}\n"
            )
        if critique.is_file():
            text = critique.read_text(encoding="utf-8").strip()
            if text and "skipped" not in text.lower()[:80]:
                chunks.append(text[:800] + "\n")
    return "\n".join(chunks) if chunks else "(no provider job metadata yet)"


def _llm_draft_final_pass_brief(arena_dir: Path, ctx: dict) -> str:
    from ai_backend import complete

    notes = _collect_provider_notes(arena_dir)
    user = (
        f"Post title: {ctx.get('title', '')}\n"
        f"Shared T2V prompt:\n{ctx.get('prompt', '')}\n\n"
        f"WINNER.txt: {ctx.get('winner') or '(not set)'}\n\n"
        f"Existing human brief (may be empty):\n{ctx.get('final_pass_brief', '')}\n\n"
        f"Provider runs:\n{notes}\n"
    )
    return complete(user, FINAL_PASS_SPEC, canonical_url="https://blog.pcioasis.com/").strip()


def run_final_pass(
    post_dir: Path,
    arena_dir: Path,
    *,
    use_llm_brief: bool = True,
) -> dict[str, Any]:
    """Run final-pass step: draft/use combine brief and stage output video."""
    post_dir = post_dir.resolve()
    arena_dir = arena_dir.resolve()
    manifest = load_arena_manifest(arena_dir) or {}
    ctx = load_arena_agent_context(arena_dir)
    ctx["title"] = manifest.get("title", "")

    brief = load_final_pass_brief(arena_dir, manifest).strip()
    if use_llm_brief and not brief:
        try:
            brief = _llm_draft_final_pass_brief(arena_dir, ctx)
            save_final_pass_brief(arena_dir, brief)
        except SystemExit:
            brief = _template_final_pass_brief(ctx, arena_dir)
            save_final_pass_brief(arena_dir, brief)
    elif not brief:
        brief = _template_final_pass_brief(ctx, arena_dir)
        save_final_pass_brief(arena_dir, brief)

    final_dir = arena_dir / "final_pass"
    final_dir.mkdir(parents=True, exist_ok=True)

    winner_id = _parse_winner_id(ctx.get("winner", ""))
    source_video: Path | None = None
    if winner_id:
        candidate = arena_dir / winner_id / "video.mp4"
        if candidate.is_file():
            source_video = candidate

    if source_video is None:
        for sub in sorted(arena_dir.iterdir()):
            if not sub.is_dir() or sub.name in ("final_pass",):
                continue
            vid = sub / "video.mp4"
            if vid.is_file():
                source_video = vid
                winner_id = sub.name
                break

    out_video = final_dir / "video.mp4"
    if source_video:
        shutil.copy2(source_video, out_video)
        video_note = f"Staged from {winner_id}/video.mp4 (replace with true combine when agent ready)."
    else:
        video_note = "No source video found — generate provider clips first."

    job = {
        "status": "ok" if source_video else "pending",
        "message": video_note,
        "source_provider": winner_id,
        "brief_file": "final_pass_brief.txt",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (final_dir / "job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    (final_dir / "README.md").write_text(
        f"# Final pass output\n\n{video_note}\n\nSee `../final_pass_brief.txt` for combine instructions.\n",
        encoding="utf-8",
    )

    manifest_path = arena_dir / "manifest.json"
    if manifest_path.is_file():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        data = {}
    data["final_pass"] = job
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    write_review_html(arena_dir, data)

    return {"brief": brief, "final_pass": job}


def _template_final_pass_brief(ctx: dict, arena_dir: Path) -> str:
    lines = [
        "# Combine brief (template — set WINNER.txt and re-run with LLM creds for richer draft)",
        "",
        f"Base prompt: {ctx.get('prompt', '')[:200]}...",
        "",
        "Per provider — fill after watching clips:",
    ]
    for sub in sorted(arena_dir.iterdir()):
        if sub.is_dir() and (sub / "video.mp4").is_file():
            lines.append(f"- {sub.name}: (timing / motion / lighting to borrow)")
    lines.extend(
        [
            "",
            "Assembly: target 6s vertical 9:16; slow push-in; no on-screen text.",
        ]
    )
    return "\n".join(lines) + "\n"
