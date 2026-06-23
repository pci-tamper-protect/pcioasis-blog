"""Extract thumbnail candidates from arena MP4s (ffmpeg)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ThumbnailCandidate:
    id: str
    label: str
    file: str  # relative to provider dir, e.g. thumbnails/first_non_black.jpg
    detail: str = ""


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def _video_duration(video: Path) -> float:
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
    )
    if proc.returncode != 0:
        return 6.0
    try:
        return max(0.1, float(proc.stdout.strip()))
    except ValueError:
        return 6.0


def _frame_mean_luma(image: Path) -> float:
    """Average luma 0–255 via ffmpeg signalstats on a single image."""
    proc = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(image),
            "-vf",
            "signalstats",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        check=False,
    )
    for line in (proc.stderr or "").splitlines():
        match = re.search(r"YAVG=([0-9.]+)", line)
        if match:
            return float(match.group(1))
    return 0.0


def _extract_frame(video: Path, dest: Path, *, timestamp: float) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ],
        check=False,
    )
    return proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def _first_non_black(video: Path, thumb_dir: Path, duration: float) -> ThumbnailCandidate | None:
    dest = thumb_dir / "first_non_black.jpg"
    max_t = min(2.0, duration * 0.5)
    t = 0.05
    while t <= max_t:
        tmp = thumb_dir / "_probe.jpg"
        if _extract_frame(video, tmp, timestamp=t):
            if _frame_mean_luma(tmp) >= 18.0:
                tmp.replace(dest)
                return ThumbnailCandidate(
                    id="first_non_black",
                    label="First non-black",
                    file=f"thumbnails/{dest.name}",
                    detail=f"at {t:.2f}s",
                )
        t += 0.05
    return None


def _max_contrast(video: Path, thumb_dir: Path) -> ThumbnailCandidate | None:
    dest = thumb_dir / "max_contrast.jpg"
    n = max(30, int(_video_duration(video) * 20))
    proc = _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"thumbnail={n}",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ],
        check=False,
    )
    if proc.returncode != 0 or not dest.is_file():
        return None
    return ThumbnailCandidate(
        id="max_contrast",
        label="Highest contrast",
        file=f"thumbnails/{dest.name}",
        detail=f"thumbnail filter (n={n})",
    )


def _scene_changes(
    video: Path, thumb_dir: Path, *, max_scenes: int = 4, threshold: float = 0.32
) -> list[ThumbnailCandidate]:
    pattern = thumb_dir / "scene_%02d.jpg"
    proc = _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"select='gt(scene\\,{threshold})',scale=720:-1",
            "-vsync",
            "vfr",
            "-frames:v",
            str(max_scenes),
            "-q:v",
            "2",
            str(pattern),
        ],
        check=False,
    )
    if proc.returncode != 0:
        return []
    out: list[ThumbnailCandidate] = []
    for path in sorted(thumb_dir.glob("scene_*.jpg")):
        idx = path.stem.split("_")[-1]
        out.append(
            ThumbnailCandidate(
                id=f"scene_{idx}",
                label=f"Scene change {idx}",
                file=f"thumbnails/{path.name}",
                detail=f"scene>{threshold}",
            )
        )
    return out


def extract_thumbnail_candidates(
    video: Path,
    provider_dir: Path,
    *,
    max_scenes: int = 4,
) -> dict:
    """Write thumbnails/*.jpg and thumbnails.json under provider_dir."""
    manifest_path = provider_dir / "thumbnails.json"
    if not video.is_file():
        return {"candidates": [], "selected": None, "error": "no video.mp4"}

    if not _ffmpeg_available():
        data = {
            "candidates": [],
            "selected": _load_selected_id(manifest_path),
            "error": "ffmpeg/ffprobe not installed",
        }
        manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    thumb_dir = provider_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    for old in thumb_dir.glob("*.jpg"):
        old.unlink()

    try:
        duration = _video_duration(video)
        candidates: list[ThumbnailCandidate] = []

        first = _first_non_black(video, thumb_dir, duration)
        if first:
            candidates.append(first)

        contrast = _max_contrast(video, thumb_dir)
        if contrast:
            candidates.append(contrast)

        candidates.extend(_scene_changes(video, thumb_dir, max_scenes=max_scenes))
    except OSError as exc:
        data = {
            "candidates": [],
            "selected": _load_selected_id(manifest_path),
            "error": f"ffmpeg failed: {exc}",
        }
        manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    # Dedupe by file path (scene filter can overlap contrast pick)
    seen: set[str] = set()
    unique: list[ThumbnailCandidate] = []
    for c in candidates:
        if c.file in seen:
            continue
        seen.add(c.file)
        unique.append(c)

    selected = _load_selected_id(manifest_path)
    if selected and not any(c.id == selected for c in unique):
        selected = None

    err_msg = None
    if not unique:
        err_msg = "no frames extracted — check ffmpeg/ffprobe (brew reinstall ffmpeg if dylib errors)"

    data = {
        "candidates": [asdict(c) for c in unique],
        "selected": selected,
        "duration_seconds": round(duration, 3),
        "error": err_msg,
    }
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def _load_selected_id(manifest_path: Path) -> str | None:
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    sel = data.get("selected")
    return str(sel) if sel else None


def load_thumbnails(provider_dir: Path) -> dict | None:
    path = provider_dir / "thumbnails.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def apply_thumbnail_selection(provider_dir: Path, choice_id: str) -> Path:
    """Copy chosen candidate to poster.jpg; update thumbnails.json and THUMBNAIL.txt."""
    data = load_thumbnails(provider_dir)
    if not data:
        raise FileNotFoundError(f"No thumbnails.json in {provider_dir}")

    match = next((c for c in data.get("candidates", []) if c.get("id") == choice_id), None)
    if not match:
        raise ValueError(f"Unknown thumbnail id: {choice_id}")

    src = provider_dir / match["file"]
    if not src.is_file():
        raise FileNotFoundError(f"Missing candidate file {src}")

    from video_arena.poster_transform import poster_options_from_brief, transform_poster_image
    from video_arena.provider_briefs import load_thumbnail_brief

    thumb_brief = load_thumbnail_brief(provider_dir)
    opts = poster_options_from_brief(provider_dir.name, choice_id, thumb_brief)
    poster = provider_dir / "poster.jpg"
    if opts["dewarp_phone"] or opts["crop_top"]:
        transform_poster_image(
            src,
            poster,
            dewarp_phone=opts["dewarp_phone"],
            crop_top=opts["crop_top"],
        )
    else:
        shutil.copy2(src, poster)
    data["selected"] = choice_id
    (provider_dir / "thumbnails.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (provider_dir / "THUMBNAIL.txt").write_text(f"{choice_id}\n", encoding="utf-8")
    return poster


def regenerate_arena_thumbnails(arena_dir: Path) -> None:
    """Re-extract candidates for every provider with video.mp4."""
    for sub in sorted(arena_dir.iterdir()):
        if not sub.is_dir():
            continue
        video = sub / "video.mp4"
        if video.is_file():
            extract_thumbnail_candidates(video, sub)
