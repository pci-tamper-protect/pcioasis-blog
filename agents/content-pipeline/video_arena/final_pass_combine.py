"""FFmpeg-only final-pass combine for arena provider clips."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SORA_IDS = frozenset({"azure_sora", "azure_sora_v1"})
VEO_IDS = frozenset({"vertex_veo"})

# Target output resolution for arena vertical video (9:16 TikTok/Reels).
ARENA_WIDTH = 720
ARENA_HEIGHT = 1280


def _resolve_sora_id(arena_dir: Path) -> str:
    for pid in SORA_IDS:
        if (arena_dir / pid / "video.mp4").is_file():
            return pid
    return "azure_sora"


def _combine_visual_brief(arena_dir: Path, brief: str) -> str:
    """Merge final-pass brief with per-provider thumbnail notes for Sora."""
    from video_arena.provider_briefs import load_thumbnail_brief

    sora_id = _resolve_sora_id(arena_dir)
    thumb = load_thumbnail_brief(arena_dir / sora_id)
    parts = [brief.strip(), thumb.strip()]
    return "\n".join(p for p in parts if p)


def _sora_video_filter_chain(visual_brief: str, sora_id: str) -> str:
    """ffmpeg filters for Sora segment before scale/trim (crop + dewarp from brief)."""
    from video_arena.poster_transform import (
        phone_frame_options_from_text,
        poster_vf_chain,
    )

    opts = phone_frame_options_from_text(visual_brief, sora_id)
    parts = ["fps=30"]
    vf = poster_vf_chain(dewarp_phone=opts["dewarp_phone"], crop_top=opts["crop_top"])
    if vf != "copy":
        parts.append(vf)
    parts.extend(
        [
            f"scale={ARENA_WIDTH}:{ARENA_HEIGHT}:force_original_aspect_ratio=decrease",
            f"pad={ARENA_WIDTH}:{ARENA_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "setsar=1",
        ]
    )
    return ",".join(parts)


@dataclass
class CombineAssessment:
    ffmpeg_feasible: bool
    mode: str
    notes: str
    llm_regen_recommended: bool
    suggested_models: list[str]


def assess_combine_brief(brief: str) -> CombineAssessment:
    """Decide whether the brief is mechanical (ffmpeg) or needs generative regen."""
    text = (brief or "").lower()
    spatial = any(
        w in text
        for w in (
            "same frame",
            "same time",
            "simultaneous",
            "picture in picture",
            "pip",
            "mask",
            "replace face",
            "inpaint",
            "seamless",
            "one shot",
        )
    )
    semantic = any(
        w in text
        for w in (
            "rephrase",
            "new dialogue",
            "change text",
            "regenerate",
            "reshoot",
            "different angle",
        )
    )
    has_sora = "sora" in text
    has_veo = "veo" in text
    sequential_ok = has_sora and has_veo and not spatial

    if sequential_ok and not semantic:
        return CombineAssessment(
            ffmpeg_feasible=True,
            mode="concat_xfade",
            notes=(
                "Sequential combine: Sora phone/chat (crop/dewarp per brief) then Veo "
                "animation, crossfade, audio per brief."
            ),
            llm_regen_recommended=False,
            suggested_models=[],
        )

    if spatial or semantic:
        return CombineAssessment(
            ffmpeg_feasible=False,
            mode="generative",
            notes=(
                "Brief needs same-frame compositing, new dialogue, or semantic edits ffmpeg "
                "cannot infer. Re-prompt T2V or use a video-edit model with the brief + refs."
            ),
            llm_regen_recommended=True,
            suggested_models=[
                "T2V re-run: azure_sora + vertex_veo with an explicit shot-list prompt",
                "Planning: Gemini 2.5 Pro/Flash (video parts) or Claude Opus (frames) → shot list",
                "Edit APIs: Runway Gen-4/Aleph, Luma modify, Pika (when licensed)",
            ],
        )

    return CombineAssessment(
        ffmpeg_feasible=True,
        mode="concat_xfade",
        notes="Default arena recipe: Sora then Veo, 6s total.",
        llm_regen_recommended=False,
        suggested_models=[],
    )


def _resolve_provider_paths(arena_dir: Path) -> tuple[Path | None, Path | None]:
    sora: Path | None = None
    veo: Path | None = None
    for pid in SORA_IDS:
        p = arena_dir / pid / "video.mp4"
        if p.is_file():
            sora = p
            break
    for pid in VEO_IDS:
        p = arena_dir / pid / "video.mp4"
        if p.is_file():
            veo = p
            break
    return sora, veo


def _audio_source_id(brief: str, default: str = "azure_sora") -> str:
    text = (brief or "").lower()
    if re.search(r"voice.*either|audio.*either|either.*voice", text):
        return default
    if re.search(r"voice.*sora|audio.*sora|sound.*sora", text):
        return "azure_sora"
    if re.search(r"voice.*veo|audio.*veo", text):
        return "vertex_veo"
    return default


def combine_sora_then_veo(
    arena_dir: Path,
    out_video: Path,
    *,
    brief: str = "",
    sora_seconds: float = 4.0,
    veo_seconds: float = 2.0,
    xfade_seconds: float = 0.5,
    total_seconds: float = 6.0,
) -> dict[str, Any]:
    """Concat Sora (phone/chat) then Veo (animation) with xfade; audio from brief preference."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not installed")

    sora, veo = _resolve_provider_paths(arena_dir)
    if not sora or not veo:
        raise FileNotFoundError("Need both azure_sora and vertex_veo video.mp4 under arena")

    audio_id = _audio_source_id(brief)
    audio_path = arena_dir / audio_id / "video.mp4"
    if not audio_path.is_file():
        audio_path = sora

    sora_id = _resolve_sora_id(arena_dir)
    visual_brief = _combine_visual_brief(arena_dir, brief)
    sora_chain = _sora_video_filter_chain(visual_brief, sora_id)

    offset = max(0.0, sora_seconds - xfade_seconds)
    fc = (
        f"[0:v]{sora_chain},trim=duration={sora_seconds},setpts=PTS-STARTPTS[v0];"
        f"[1:v]fps=30,scale={ARENA_WIDTH}:{ARENA_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={ARENA_WIDTH}:{ARENA_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,trim=duration={veo_seconds},"
        f"setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]xfade=transition=fade:duration={xfade_seconds}:offset={offset}[vout];"
        f"[2:a]aresample=48000,atrim=duration={total_seconds},asetpts=PTS-STARTPTS[aout]"
    )

    out_video.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(sora),
        "-i",
        str(veo),
        "-i",
        str(audio_path),
        "-filter_complex",
        fc,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-t",
        str(total_seconds),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(out_video),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    from video_arena.poster_transform import phone_frame_options_from_text

    frame_opts = phone_frame_options_from_text(visual_brief, sora_id)
    return {
        "mode": "concat_xfade",
        "sora": str(sora),
        "veo": str(veo),
        "audio_from": audio_id,
        "duration": total_seconds,
        "sora_frame_crop": frame_opts["crop_top"],
        "sora_frame_dewarp": frame_opts["dewarp_phone"],
    }


def run_ffmpeg_final_pass(arena_dir: Path, brief: str) -> dict[str, Any]:
    """Assess brief and run ffmpeg combine when feasible."""
    assessment = assess_combine_brief(brief)
    result: dict[str, Any] = {
        "assessment": {
            "ffmpeg_feasible": assessment.ffmpeg_feasible,
            "mode": assessment.mode,
            "notes": assessment.notes,
            "llm_regen_recommended": assessment.llm_regen_recommended,
            "suggested_models": assessment.suggested_models,
        }
    }
    if not assessment.ffmpeg_feasible:
        result["skipped"] = True
        return result

    out = arena_dir / "final_pass" / "video.mp4"
    meta = combine_sora_then_veo(arena_dir, out, brief=brief)
    result["output"] = str(out)
    result["combine"] = meta
    (arena_dir / "final_pass" / "combine_assessment.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
