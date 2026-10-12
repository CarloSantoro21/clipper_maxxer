"""Pasos del pipeline compartidos por la CLI y el dashboard (api.py), para no duplicar lógica."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Optional

from .config import job_dir
from .specs import ClipSpec

Log = Callable[[str], None]


def format_plan_line(spec: ClipSpec, issues: list[str]) -> str:
    flag = "  ⚠ " + "; ".join(issues) if issues else ""
    return f"{spec.id}  {spec.score:>4.1f}  {spec.duration:>4.0f}s  {spec.hook}{flag}"


def _thumb(video: Path, duration: float) -> None:
    from .render import thumbnail
    try:
        thumbnail(video, at=min(1.0, max(duration / 2, 0)))
    except Exception:  # la miniatura es cosmética: no tumba el render
        pass


def render_job(job_id: str, only: Optional[Iterable[str]] = None, log: Log = print) -> list[Path]:
    """Renderiza los specs del job (excepto los rechazados) y deja una miniatura .jpg junto a cada .mp4."""
    from .planner import load_specs, save_specs
    from .render import render_clip
    from .transcribe import transcribe

    only = set(only or [])
    t = transcribe(job_id)
    out_dir = job_dir(job_id) / "renders"
    specs = [s for s in load_specs(job_id) if s.status != "rejected" and (not only or s.id in only)]
    paths = []
    for s in specs:
        log(f"render {s.id}…")
        path = render_clip(s, t, out_dir)
        _thumb(path, s.duration)
        # releemos el spec: si alguien lo editó durante el render, no pisamos sus cambios
        fresh = next((x for x in load_specs(job_id) if x.id == s.id), s)
        if fresh.status != "published":
            fresh.status = "rendered"
        save_specs(job_id, [fresh])
        paths.append(path)
        log(str(path))
    return paths


def clip_pipeline(
    src: str,
    campaign: Optional[str] = None,
    n: int = 5,
    log: Log = print,
    progress: Optional[Callable[[float, str], None]] = None,
) -> str:
    """Todo de un jalón: ingest → transcribe → plan → render → review. Devuelve el job_id."""
    from .campaigns import load_campaign
    from .ingest import ingest, load_job
    from .planner import plan
    from .review import build_review
    from .transcribe import transcribe

    step = progress or (lambda _p, _s: None)
    step(0.02, "descargando")
    job_id = ingest(src, campaign)
    log(f"job: {job_id}")
    step(0.2, "transcribiendo")
    t = transcribe(job_id)
    log(f"{len(t.words)} palabras, {t.duration:.0f}s, idioma {t.language}")
    step(0.45, "planeando con Claude")
    job = load_job(job_id)
    slug = campaign or job.get("campaign")
    results = plan(job, t, load_campaign(slug) if slug else None, n)
    for spec, issues in results:
        log(format_plan_line(spec, issues))
    step(0.6, "renderizando")
    specs = [s for s, _ in results if s.status != "rejected"]
    for i, s in enumerate(specs):
        step(0.6 + 0.38 * i / max(len(specs), 1), f"renderizando {s.id}")
        render_job(job_id, [s.id], log=log)
    build_review()
    step(1.0, "listo")
    return job_id


def render_story_by_id(story_id: str, log: Log = print) -> Path:
    from .story import load_story, render_story
    spec = load_story(story_id)
    was_published = spec.status == "published"
    log(f"render story {story_id}…")
    path = render_story(spec)
    if was_published:
        from .story import save_story
        spec.status = "published"
        save_story(spec)
    from .render import duration_of
    try:
        _thumb(path, duration_of(path))
    except Exception:
        pass
    log(str(path))
    return path
