"""Generalized directions and tool catalog for video-arena agents.

Cursor agents, CLI runners, and LLM planners should:
1. Read user text + ``load_arena_agent_context()``.
2. Call ``try_direct_tools()`` when intent maps cleanly to a tool.
3. Otherwise call ``plan_tools_with_llm()`` then ``execute_tool()`` for each step.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from video_arena.prompt_store import (
    load_arena_agent_context,
    save_arena_prompt,
    save_final_pass_brief,
)

# ---------------------------------------------------------------------------
# Shared principles (prepended to role-specific specs)
# ---------------------------------------------------------------------------

AGENT_PRINCIPLES = """\
## Video arena agent principles

You work on ``content/posts/.../_variants/video-arena/`` for one Hugo post.

**Inputs you may receive**
- Free-form **user text** (briefs, commands, notes).
- On-disk context: ``prompt.txt``, ``final_pass_brief.txt``, ``WINNER.txt``, provider ``video.mp4``, thumbnails, ``manifest.json``.

**How to act**
1. **Prefer deterministic tools** (Python functions / CLI / preview HTTP) when the user asks for a concrete operation (save, regen, combine, poster, assess).
2. **Use LLM only** for drafting text (T2V prompt, combine brief, critique) or when ``assess_combine_brief`` says generative regen is required.
3. **Never invent provider ids** — use: ``azure_sora``, ``azure_sora_v1``, ``vertex_veo``, ``bedrock_luma``, ``replicate_hailuo``.
4. After mutating files, refresh ``review.html`` via ``write_review_html`` when the preview server is in use (``api_base="/arena"``).

**Provider nicknames in user text**
- sora / sora2 → ``azure_sora`` (or ``azure_sora_v1`` if user says v1)
- veo → ``vertex_veo``
- luma → ``bedrock_luma``
- hailuo → ``replicate_hailuo``
"""

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "rebuild_prompt_from_clapper",
        "summary": "Rebuild shared T2V prompt from _variants/clapper.txt → prompt.txt",
        "callable": "arena_actions.rebuild_prompt_from_clapper",
        "args": [],
    },
    {
        "id": "save_prompt",
        "summary": "Persist user-edited text to prompt.txt + manifest",
        "callable": "prompt_store.save_arena_prompt",
        "args": ["prompt"],
    },
    {
        "id": "save_final_pass_brief",
        "summary": "Persist combine instructions to final_pass_brief.txt",
        "callable": "prompt_store.save_final_pass_brief",
        "args": ["brief"],
    },
    {
        "id": "run_arena_all",
        "summary": "Run all configured T2V providers (slow, billed)",
        "callable": "orchestrator.run_arena",
        "args": ["only", "skip_critique"],
    },
    {
        "id": "regenerate_provider_video",
        "summary": "Re-run one provider T2V from current prompt.txt",
        "callable": "arena_actions.regenerate_provider_video",
        "args": ["provider_id", "skip_critique"],
    },
    {
        "id": "regenerate_all_provider_videos",
        "summary": "Re-run many providers from current prompt.txt",
        "callable": "arena_actions.regenerate_all_provider_videos",
        "args": ["provider_ids"],
    },
    {
        "id": "extract_thumbnails",
        "summary": "ffmpeg: first non-black, max contrast, scene cuts → thumbnails/",
        "callable": "thumbnails.extract_thumbnail_candidates",
        "args": ["provider_id"],
    },
    {
        "id": "regenerate_provider_thumbnails",
        "summary": "Re-extract thumbnail candidates for one provider",
        "callable": "arena_actions.regenerate_provider_thumbnails",
        "args": ["provider_id"],
    },
    {
        "id": "regenerate_arena_thumbnails",
        "summary": "Re-extract thumbnails for every provider with video.mp4",
        "callable": "thumbnails.regenerate_arena_thumbnails",
        "args": [],
    },
    {
        "id": "select_thumbnail",
        "summary": "Copy candidate to poster.jpg (optional phone crop/dewarp for Sora max_contrast)",
        "callable": "thumbnails.apply_thumbnail_selection",
        "args": ["provider_id", "choice_id"],
    },
    {
        "id": "assess_combine_brief",
        "summary": "Decide if final pass is ffmpeg-feasible or needs generative regen",
        "callable": "final_pass_combine.assess_combine_brief",
        "args": ["brief"],
    },
    {
        "id": "ffmpeg_combine",
        "summary": "Concat Sora phone/chat then Veo animation (when assessment allows)",
        "callable": "final_pass_combine.run_ffmpeg_final_pass",
        "args": ["brief"],
    },
    {
        "id": "run_final_pass",
        "summary": "Save brief, assess, ffmpeg combine when possible, update final_pass/",
        "callable": "arena_actions.run_final_pass",
        "args": ["use_llm_brief"],
    },
    {
        "id": "write_critique",
        "summary": "LLM text critique from prompt + job.json (no vision)",
        "callable": "critique.write_critique",
        "args": ["provider_id"],
    },
    {
        "id": "write_review_html",
        "summary": "Regenerate arena review.html dashboard",
        "callable": "review.write_review_html",
        "args": ["api_base"],
    },
]

ORCHESTRATOR_SPEC = f"""\
{AGENT_PRINCIPLES}

You are the **video arena orchestrator**. The user message is the source of truth.

**Your job**
1. Understand intent from user text + bundled context (paths, providers, briefs).
2. Choose zero or more tools from the catalog below.
3. Respond with **only** valid JSON (no markdown fences):

```json
{{
  "reasoning": "one short paragraph",
  "tools": [
    {{"id": "tool_id_from_catalog", "args": {{}}}}
  ],
  "user_text_to_save": {{
    "prompt": null,
    "final_pass_brief": null
  }}
}}

Set ``user_text_to_save.prompt`` or ``.final_pass_brief`` when the user supplied new copy to persist before other tools run.
Order tools so saves happen before regens/combines. Prefer ``assess_combine_brief`` before ``ffmpeg_combine`` when combining.
If generative video regen is required, return empty ``tools`` and explain in ``reasoning`` which T2V providers to re-prompt.
"""

PROMPT_AGENT_SPEC = f"""\
{AGENT_PRINCIPLES}

You are the **shared T2V prompt agent**.

Given user text and/or clapper metadata, produce or refine the **single shared prompt** sent to every provider (9:16, 5–8s, infosec explainer tone).

Output: plain prompt text only (no markdown fences). If the user only asked to rebuild from clapper, say TOOL:rebuild_prompt_from_clapper instead of rewriting.
"""

FINAL_PASS_AGENT_SPEC = f"""\
{AGENT_PRINCIPLES}

You are the **final-pass combine agent**.

Given user text and provider metadata, write a ≤250 word **combine brief** for downstream tooling:
- Which provider supplies which visual (chat UI, motion, lighting, diagram, etc.)
- Audio preference (provider id or either)
- Poster notes (e.g. max_contrast, crop bottom 3/5, dewarp phone)
- Assembly: sequential vs same-frame (same-frame usually needs generative regen, not ffmpeg)

If user text is already a complete brief, return it unchanged (light edit only).
If user asks to run combine now, say TOOL:run_final_pass after the brief is clear.
"""

CRITIQUE_AGENT_SPEC = f"""\
{AGENT_PRINCIPLES}

You are the **provider critique agent** (text-only; no pixels unless a future vision tool is called).

Write ≤200 words: Prompt adherence, motion, artifact risk, B2B fit (1–5 each), Verdict (ship / re-prompt / discard).
"""

ROLE_SPECS: dict[str, str] = {
    "orchestrator": ORCHESTRATOR_SPEC,
    "prompt": PROMPT_AGENT_SPEC,
    "final_pass": FINAL_PASS_AGENT_SPEC,
    "critique": CRITIQUE_AGENT_SPEC,
}


@dataclass
class ToolStep:
    id: str
    args: dict[str, Any] = field(default_factory=dict)


def tool_catalog_for_prompt() -> str:
    lines = ["## Tool catalog", ""]
    for t in TOOL_CATALOG:
        args = ", ".join(t["args"]) or "(post_dir, arena_dir implicit)"
        lines.append(f"- **{t['id']}**: {t['summary']} — args: {args}")
    return "\n".join(lines)


def get_role_spec(role: str) -> str:
    base = ROLE_SPECS.get(role, ORCHESTRATOR_SPEC)
    return base + "\n\n" + tool_catalog_for_prompt()


def load_arena_agent_context_extended(
    post_dir: Path,
    arena_dir: Path | None = None,
) -> dict[str, Any]:
    """Context bundle for agents: text files + tool catalog + paths."""
    post_dir = post_dir.resolve()
    if arena_dir is None:
        arena_dir = post_dir / "_variants" / "video-arena"
    arena_dir = arena_dir.resolve()
    ctx = load_arena_agent_context(arena_dir)
    ctx.update(
        {
            "post_dir": str(post_dir),
            "arena_dir": str(arena_dir),
            "tool_catalog": TOOL_CATALOG,
            "agent_principles": AGENT_PRINCIPLES,
        }
    )
    return ctx


def _resolve_provider_id(text: str) -> str | None:
    lower = text.lower()
    mapping = [
        (r"\bsora\s*v1\b|\bsora_v1\b", "azure_sora_v1"),
        (r"\bsora\s*2\b|\bsora2\b|\bsora\b", "azure_sora"),
        (r"\bveo\b", "vertex_veo"),
        (r"\bluma\b", "bedrock_luma"),
        (r"\bhailuo\b", "replicate_hailuo"),
    ]
    for pattern, pid in mapping:
        if re.search(pattern, lower):
            return pid
    for pid in ("azure_sora", "azure_sora_v1", "vertex_veo", "bedrock_luma", "replicate_hailuo"):
        if pid in lower:
            return pid
    return None


def try_direct_tools(
    user_text: str,
    post_dir: Path,
    arena_dir: Path,
) -> list[ToolStep] | None:
    """Map common user phrases to tool steps without LLM."""
    text = (user_text or "").strip()
    if not text:
        return None
    lower = text.lower()
    pid = _resolve_provider_id(text)

    if re.search(r"rebuild|regenerat(e|ing).*prompt|prompt.*clapper|from clapper", lower):
        return [ToolStep("rebuild_prompt_from_clapper")]

    if re.search(r"thumbnail|poster|splash|cover", lower) and re.search(
        r"regen|refresh|extract|re-extract|again", lower
    ):
        if pid:
            return [ToolStep("regenerate_provider_thumbnails", {"provider_id": pid})]
        return [ToolStep("regenerate_arena_thumbnails")]

    if re.search(r"max[_\s-]?contrast|highest contrast", lower) and pid:
        return [ToolStep("select_thumbnail", {"provider_id": pid, "choice_id": "max_contrast"})]

    if re.search(r"regen(erate)?\s+(the\s+)?video|re-run\s+t2v|new\s+video", lower):
        if pid:
            return [ToolStep("regenerate_provider_video", {"provider_id": pid})]
        return None

    if re.search(r"final\s*pass|run\s+combine|stage\s+final", lower):
        return [
            ToolStep("save_final_pass_brief", {"brief": text}),
            ToolStep("run_final_pass", {"use_llm_brief": False}),
            ToolStep("write_review_html", {"api_base": "/arena"}),
        ]

    if re.search(r"assess|feasib", lower) and re.search(r"combine|final|ffmpeg", lower):
        return [ToolStep("assess_combine_brief", {"brief": text})]

    if re.search(r"ffmpeg|concat|combine", lower) and not re.search(
        r"same frame|simultaneous|inpaint|new dialogue", lower
    ):
        steps = [ToolStep("save_final_pass_brief", {"brief": text})]
        steps.append(ToolStep("ffmpeg_combine", {"brief": text}))
        steps.append(ToolStep("write_review_html", {"api_base": "/arena"}))
        return steps

    return None


def execute_tool(
    tool_id: str,
    post_dir: Path,
    arena_dir: Path,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one catalog tool by id."""
    args = dict(args or {})
    post_dir = post_dir.resolve()
    arena_dir = arena_dir.resolve()

    if tool_id == "rebuild_prompt_from_clapper":
        from video_arena.arena_actions import rebuild_prompt_from_clapper

        return rebuild_prompt_from_clapper(post_dir, arena_dir)

    if tool_id == "save_prompt":
        save_arena_prompt(arena_dir, str(args["prompt"]))
        return {"ok": True}

    if tool_id == "save_final_pass_brief":
        save_final_pass_brief(arena_dir, str(args.get("brief", "")))
        return {"ok": True}

    if tool_id == "run_arena_all":
        from video_arena.orchestrator import run_arena

        run_arena(post_dir, only=args.get("only"), skip_critique=bool(args.get("skip_critique")))
        return {"ok": True}

    if tool_id == "regenerate_provider_video":
        from video_arena.arena_actions import regenerate_provider_video

        return regenerate_provider_video(
            post_dir,
            arena_dir,
            str(args["provider_id"]),
            skip_critique=bool(args.get("skip_critique", True)),
        )

    if tool_id == "regenerate_all_provider_videos":
        from video_arena.arena_actions import regenerate_all_provider_videos

        ids = args.get("provider_ids")
        return {"ran": regenerate_all_provider_videos(post_dir, arena_dir, ids)}

    if tool_id == "extract_thumbnails":
        from video_arena.thumbnails import extract_thumbnail_candidates

        pid = str(args["provider_id"])
        video = arena_dir / pid / "video.mp4"
        return extract_thumbnail_candidates(video, arena_dir / pid)

    if tool_id == "regenerate_provider_thumbnails":
        from video_arena.arena_actions import regenerate_provider_thumbnails

        return regenerate_provider_thumbnails(arena_dir, str(args["provider_id"]))

    if tool_id == "regenerate_arena_thumbnails":
        from video_arena.thumbnails import regenerate_arena_thumbnails

        regenerate_arena_thumbnails(arena_dir)
        return {"ok": True}

    if tool_id == "select_thumbnail":
        from video_arena.thumbnails import apply_thumbnail_selection

        poster = apply_thumbnail_selection(
            arena_dir / str(args["provider_id"]),
            str(args["choice_id"]),
        )
        return {"poster": str(poster)}

    if tool_id == "assess_combine_brief":
        from video_arena.final_pass_combine import assess_combine_brief

        a = assess_combine_brief(str(args.get("brief", "")))
        return {
            "ffmpeg_feasible": a.ffmpeg_feasible,
            "mode": a.mode,
            "notes": a.notes,
            "llm_regen_recommended": a.llm_regen_recommended,
            "suggested_models": a.suggested_models,
        }

    if tool_id == "ffmpeg_combine":
        from video_arena.final_pass_combine import run_ffmpeg_final_pass

        return run_ffmpeg_final_pass(arena_dir, str(args.get("brief", "")))

    if tool_id == "run_final_pass":
        from video_arena.arena_actions import run_final_pass

        return run_final_pass(
            post_dir,
            arena_dir,
            use_llm_brief=bool(args.get("use_llm_brief", False)),
        )

    if tool_id == "write_critique":
        from video_arena.critique import write_critique
        from video_arena.prompt_store import load_prompt_text
        from video_arena.review import load_arena_manifest

        pid = str(args["provider_id"])
        manifest = load_arena_manifest(arena_dir) or {}
        prompt = load_prompt_text(arena_dir, manifest)
        job_path = arena_dir / pid / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8")) if job_path.is_file() else {}
        out = arena_dir / pid / "critique.md"
        write_critique(pid, prompt, job, out)
        return {"critique": str(out)}

    if tool_id == "write_review_html":
        from video_arena.review import load_arena_manifest, write_review_html

        manifest = load_arena_manifest(arena_dir) or {}
        api = args.get("api_base", "/arena")
        path = write_review_html(
            arena_dir,
            manifest,
            href_for=lambda p: f"{api}/{p}/video.mp4",
            thumb_href_for=lambda p, rel: f"{api}/{p}/{rel}",
            back_href="/",
            api_base=api,
        )
        return {"review_html": str(path)}

    raise ValueError(f"Unknown tool id: {tool_id}")


def execute_tool_plan(
    post_dir: Path,
    arena_dir: Path,
    steps: list[ToolStep],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in steps:
        results.append(
            {
                "tool": step.id,
                "result": execute_tool(step.id, post_dir, arena_dir, step.args),
            }
        )
    return results


def plan_tools_with_llm(
    user_text: str,
    ctx: dict[str, Any],
    *,
    role: str = "orchestrator",
) -> dict[str, Any]:
    """Ask configured LLM for a JSON tool plan."""
    from ai_backend import complete

    spec = get_role_spec(role)
    payload = (
        f"User text:\n{user_text.strip()}\n\n"
        f"Context JSON:\n{json.dumps({k: v for k, v in ctx.items() if k != 'tool_catalog'}, indent=2)[:12000]}\n"
    )
    raw = complete(payload, spec, canonical_url="https://blog.pcioasis.com/").strip()
    # Strip optional markdown fence
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"error": f"LLM did not return valid JSON: {exc}", "raw": raw[:2000]}


def run_from_user_text(
    post_dir: Path,
    user_text: str,
    *,
    arena_dir: Path | None = None,
    use_llm_if_ambiguous: bool = True,
    role: str = "orchestrator",
) -> dict[str, Any]:
    """Intake user text → direct tools or LLM plan → execute."""
    post_dir = post_dir.resolve()
    if arena_dir is None:
        arena_dir = post_dir / "_variants" / "video-arena"
    arena_dir = arena_dir.resolve()
    if not arena_dir.is_dir():
        raise FileNotFoundError(f"No video arena at {arena_dir}")

    ctx = load_arena_agent_context_extended(post_dir, arena_dir)
    report: dict[str, Any] = {"user_text": user_text, "path": "direct"}

    steps = try_direct_tools(user_text, post_dir, arena_dir)
    plan: dict[str, Any] | None = None

    if steps is None and use_llm_if_ambiguous:
        report["path"] = "llm_plan"
        plan = plan_tools_with_llm(user_text, ctx, role=role)
        if plan.get("error"):
            return {**report, "plan": plan}

        saves = plan.get("user_text_to_save") or {}
        if saves.get("prompt"):
            save_arena_prompt(arena_dir, str(saves["prompt"]))
        if saves.get("final_pass_brief"):
            save_final_pass_brief(arena_dir, str(saves["final_pass_brief"]))

        steps = [ToolStep(t["id"], t.get("args") or {}) for t in plan.get("tools") or []]

    if not steps:
        return {
            **report,
            "plan": plan,
            "message": "No tools matched. Refine user text or set use_llm_if_ambiguous=True.",
        }

    results = execute_tool_plan(post_dir, arena_dir, steps)
    return {**report, "plan": plan, "steps": [{"id": s.id, "args": s.args} for s in steps], "results": results}
