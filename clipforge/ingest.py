"""Descarga de la fuente (link de YouTube/Drive/etc.) o registro de un archivo local."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .config import job_dir


def _job_id_from(src: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", src)
    if m:
        return m.group(1)
    stem = Path(src).stem if not src.startswith("http") else re.sub(r"\W+", "-", src)[-40:]
    return re.sub(r"[^\w-]+", "-", stem).strip("-").lower()[:40] or "job"


def ingest(src: str, campaign: str | None = None) -> str:
    """Devuelve el job_id. Deja el video en data/jobs/<id>/source.mp4."""
    job_id = _job_id_from(src)
    d = job_dir(job_id)
    out = d / "source.mp4"
    meta = {"job_id": job_id, "src": src, "campaign": campaign}

    if out.exists():
        pass
    elif src.startswith("http"):
        if not shutil.which("yt-dlp"):
            raise RuntimeError("Falta yt-dlp: pip install 'clipforge[ingest]'")
        cmd = [
            "yt-dlp", src,
            "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
            "--merge-output-format", "mp4",
            "-o", str(out),
            "--write-info-json", "--no-playlist",
        ]
        subprocess.run(cmd, check=True)
        info = d / "source.info.json"
        if info.exists():
            data = json.loads(info.read_text(encoding="utf-8"))
            meta.update(title=data.get("title"), channel=data.get("channel"),
                        duration=data.get("duration"))
    else:
        p = Path(src).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        shutil.copy(p, out)
        meta["title"] = p.stem

    (d / "job.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return job_id


def load_job(job_id: str) -> dict:
    return json.loads((job_dir(job_id) / "job.json").read_text(encoding="utf-8"))
