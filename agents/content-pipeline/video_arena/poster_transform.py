"""Poster transforms via ffmpeg (crop, mild perspective dewarp)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Keep top 2/5 of frame; discard bottom 3/5 (empty phone bezel / lower animation clutter).
CROP_KEEP_TOP_NUM = 2
CROP_KEEP_TOP_DEN = 5

# Approximate dewarp for tilted phone-in-hand (720×~512 after crop). Tune per shot if needed.
PHONE_PERSPECTIVE = (
    "perspective="
    "x0=50:y0=25:x1=670:y1=15:"
    "x2=20:y2=460:x3=700:y3=450:"
    "sense=source"
)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def poster_vf_chain(*, dewarp_phone: bool = True, crop_top: bool = True) -> str:
    parts: list[str] = []
    if crop_top:
        parts.append(f"crop=iw:ih*{CROP_KEEP_TOP_NUM}/{CROP_KEEP_TOP_DEN}:0:0")
    if dewarp_phone:
        parts.append(PHONE_PERSPECTIVE)
    return ",".join(parts) if parts else "copy"


def phone_frame_options_from_text(
    text: str,
    provider_id: str = "azure_sora",
    *,
    choice_id: str = "max_contrast",
) -> dict[str, bool]:
    """Parse brief lines (final pass, thumbnail notes) for crop/dewarp on phone footage."""
    return {
        "dewarp_phone": should_dewarp_phone(
            provider_id, choice_id, thumbnail_brief=text
        ),
        "crop_top": should_crop_top(text)
        or should_dewarp_phone(provider_id, choice_id, thumbnail_brief=text),
    }


def poster_options_from_brief(
    provider_id: str,
    choice_id: str,
    thumbnail_brief: str,
) -> dict[str, bool]:
    return phone_frame_options_from_text(
        thumbnail_brief, provider_id, choice_id=choice_id
    )


def transform_poster_image(
    src: Path,
    dest: Path,
    *,
    dewarp_phone: bool = True,
    crop_top: bool = True,
) -> None:
    """Write poster JPEG with top crop and optional phone perspective correction."""
    if not _ffmpeg_available():
        shutil.copy2(src, dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = poster_vf_chain(dewarp_phone=dewarp_phone, crop_top=crop_top)
    if vf == "copy":
        shutil.copy2(src, dest)
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-update",
        "1",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def should_dewarp_phone(
    provider_id: str,
    choice_id: str,
    *,
    thumbnail_brief: str = "",
) -> bool:
    """Heuristic: Sora phone UI benefits from dewarp; brief can force straight-on."""
    if choice_id != "max_contrast":
        return False
    text = (thumbnail_brief or "").lower()
    if "dewarp" in text or "straight-on" in text or "straight on" in text:
        return True
    if "no dewarp" in text or "no crop" in text:
        return False
    return provider_id in ("azure_sora", "azure_sora_v1")


def should_crop_top(thumbnail_brief: str) -> bool:
    text = (thumbnail_brief or "").lower()
    if "no crop" in text:
        return False
    return any(
        w in text
        for w in ("crop", "3/5", "bottom 3", "top 2/5", "crop away bottom")
    )
