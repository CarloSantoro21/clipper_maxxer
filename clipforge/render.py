"""Render determinista con ffmpeg: recorte 9:16, zooms, subtítulos y hook."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .captions import H, W, build_ass
from .config import ROOT
from .specs import ClipSpec, Transcript, Zoom

FONTS = ROOT / "assets" / "fonts"


def _need_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Falta ffmpeg en el PATH (https://ffmpeg.org/download.html)")


def probe(path: str | Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def duration_of(path: str | Path) -> float:
    return float(probe(path)["format"]["duration"])


def _zoom_expr(zooms: list[Zoom]) -> str:
    if not zooms:
        return "1"
    terms = [f"{z.scale - 1:.3f}*between(t\\,{z.at:.3f}\\,{z.at + z.duration:.3f})" for z in zooms]
    return "(1+" + "+".join(terms) + ")"


def _ass_filter(ass_path: Path) -> str:
    # ffmpeg exige escapar ':' y '\' en rutas dentro del filtergraph
    p = str(ass_path).replace("\\", "/").replace(":", "\\:")
    f = f"ass='{p}'"
    if FONTS.exists() and any(FONTS.iterdir()):
        fd = str(FONTS).replace("\\", "/").replace(":", "\\:")
        f += f":fontsdir='{fd}'"
    return f


def vertical_filter(crop_x: float, zooms: list[Zoom], ass_path: Path | None) -> str:
    z = _zoom_expr(zooms)
    chain = [
        # cubrir 1080x1920 sin deformar y recortar en la posición horizontal elegida
        f"scale={W}:{H}:force_original_aspect_ratio=increase",
        f"crop={W}:{H}:(iw-{W})*{crop_x:.3f}:(ih-{H})/2",
    ]
    if zooms:
        chain += [
            f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame",
            f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2",
        ]
    chain += ["fps=30", "setsar=1"]
    if ass_path:
        chain.append(_ass_filter(ass_path))
    return ",".join(chain)


def render_clip(spec: ClipSpec, transcript: Transcript, out_dir: Path) -> Path:
    _need_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    ass_path = out_dir / f"{spec.id}.ass"
    ass_path.write_text(
        build_ass(
            transcript.words_between(spec.start, spec.end),
            spec.captions,
            offset=spec.start,
            hook=spec.hook,
            hook_seconds=spec.hook_seconds,
            total=spec.duration,
        ),
        encoding="utf-8",
    )
    out = out_dir / f"{spec.id}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{spec.start:.3f}", "-t", f"{spec.duration:.3f}", "-i", spec.source,
        "-vf", vertical_filter(spec.crop_x, spec.zooms, ass_path),
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def thumbnail(video: Path, at: float = 1.0) -> Path:
    out = video.with_suffix(".jpg")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at}", "-i", str(video),
         "-frames:v", "1", "-q:v", "3", str(out)],
        check=True,
    )
    return out
