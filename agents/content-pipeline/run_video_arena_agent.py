#!/usr/bin/env python3
"""Run video-arena agent from user text (direct tools or LLM plan).

Usage:
  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/run_video_arena_agent.py POST_DIR \\
    "Regenerate thumbnails for azure_sora"

  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/run_video_arena_agent.py POST_DIR \\
    --text-file path/to/brief.txt --no-llm

  uv run --project agents/content-pipeline \\
    python agents/content-pipeline/run_video_arena_agent.py POST_DIR \\
    --print-directions orchestrator
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from video_arena.agent_directions import (
    ROLE_SPECS,
    get_role_spec,
    load_arena_agent_context_extended,
    run_from_user_text,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Video arena agent: user text → tools (direct or LLM)"
    )
    parser.add_argument("post_dir", type=Path, help="Hugo post directory")
    parser.add_argument(
        "user_text",
        nargs="?",
        default="",
        help="Instruction or brief (optional if --text-file)",
    )
    parser.add_argument("--text-file", type=Path, help="Read user text from file")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Only use direct tool mapping; do not call LLM planner",
    )
    parser.add_argument(
        "--role",
        choices=sorted(ROLE_SPECS.keys()),
        default="orchestrator",
        help="LLM role when planning (default: orchestrator)",
    )
    parser.add_argument(
        "--print-directions",
        metavar="ROLE",
        help="Print role spec + tool catalog and exit",
    )
    parser.add_argument(
        "--print-context",
        action="store_true",
        help="Print arena context JSON and exit",
    )
    args = parser.parse_args()

    if args.print_directions:
        if args.print_directions not in ROLE_SPECS:
            parser.error(
                f"unknown role {args.print_directions!r}; choices: {sorted(ROLE_SPECS)}"
            )
        print(get_role_spec(args.print_directions))
        return

    post_dir = args.post_dir.resolve()
    arena_dir = post_dir / "_variants" / "video-arena"

    if args.print_context:
        ctx = load_arena_agent_context_extended(post_dir, arena_dir)
        ctx.pop("tool_catalog", None)
        print(json.dumps(ctx, indent=2))
        return

    user_text = args.user_text
    if args.text_file:
        user_text = args.text_file.read_text(encoding="utf-8")
    if not user_text.strip():
        print("error: provide user_text or --text-file", file=sys.stderr)
        raise SystemExit(1)

    try:
        report = run_from_user_text(
            post_dir,
            user_text,
            arena_dir=arena_dir,
            use_llm_if_ambiguous=not args.no_llm,
            role=args.role,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
