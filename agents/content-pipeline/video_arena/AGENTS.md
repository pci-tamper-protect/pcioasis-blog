# Video arena agents

Generalized directions for Cursor agents, `run_video_arena_agent.py`, and LLM backends. Source of truth for specs and tools: **`agent_directions.py`**.

## Intake

| Input | Location |
|-------|----------|
| User command / brief | Chat, `run_video_arena_agent.py` arg, `--text-file`, or arena dashboard textareas |
| Shared T2V prompt | `prompt.txt` |
| Combine brief | `final_pass_brief.txt` |
| Winner | `WINNER.txt` |
| Clapper source | `_variants/clapper.txt` |

Load full bundle:

```python
from video_arena.agent_directions import load_arena_agent_context_extended
ctx = load_arena_agent_context_extended(post_dir)
```

## Roles

| Role | Spec key | Use when |
|------|----------|----------|
| **Orchestrator** | `orchestrator` | Free-form user text → tool plan (default) |
| **Prompt** | `prompt` | Draft/refine `prompt.txt` |
| **Final pass** | `final_pass` | Draft combine brief or drive `run_final_pass` |
| **Critique** | `critique` | Text critique per provider |

Print directions:

```bash
uv run --project agents/content-pipeline \
  python agents/content-pipeline/run_video_arena_agent.py POST_DIR \
  --print-directions orchestrator
```

## How to act (Cursor / SDK agent)

1. **Read** `load_arena_agent_context_extended(post_dir)` and user text.
2. **Try tools first** — call `execute_tool()` or `run_from_user_text()`; do not re-implement ffmpeg/T2V in chat.
3. **Use LLM** only when:
   - User asks for drafted prompt/brief/critique text, or
   - `assess_combine_brief` reports `llm_regen_recommended: true`, or
   - `try_direct_tools` returns no match → `plan_tools_with_llm()` then execute JSON `tools` list.

```bash
# Direct mapping (fast)
uv run --project agents/content-pipeline \
  python agents/content-pipeline/run_video_arena_agent.py POST_DIR \
  "Regenerate thumbnails for sora" --no-llm

# LLM planner when ambiguous
uv run --project agents/content-pipeline \
  python agents/content-pipeline/run_video_arena_agent.py POST_DIR \
  "Use phone chat from sora and animation from veo, voice either"
```

## Tool catalog (summary)

| Tool id | Action |
|---------|--------|
| `rebuild_prompt_from_clapper` | `prompt.txt` ← clapper |
| `save_prompt` / `save_final_pass_brief` | Persist user text |
| `regenerate_provider_video` | One T2V provider |
| `regenerate_all_provider_videos` | All providers |
| `regenerate_provider_thumbnails` / `regenerate_arena_thumbnails` | ffmpeg frames |
| `select_thumbnail` | `poster.jpg` (+ Sora dewarp when `max_contrast`) |
| `assess_combine_brief` | ffmpeg vs generative |
| `ffmpeg_combine` | Sora → Veo concat |
| `run_final_pass` | Brief + assess + combine + manifest |
| `write_critique` | LLM `critique.md` |
| `write_review_html` | Refresh dashboard |

Full list and args: `agent_directions.TOOL_CATALOG` or `--print-directions orchestrator`.

## Preview server HTTP (same tools)

When `preview_server.py` is running, the dashboard POSTs to `/arena/…` — equivalent to save/regenerate endpoints. Agents on disk should prefer Python `execute_tool()` for batch/CI.

## Generative regen (not in tool catalog)

When combine needs same-frame fusion, new dialogue, or inpainting:

- Re-run T2V: `generate_video_arena.py --only azure_sora` with an explicit shot-list in `prompt.txt`
- Planning: Gemini 2.5 (video input) or Claude (frames) → new prompt or edit API
- Edit APIs: Runway, Luma modify, Pika (not wired here)

See `final_pass/combine_assessment.json` after `ffmpeg_combine` or `assess_combine_brief`.
