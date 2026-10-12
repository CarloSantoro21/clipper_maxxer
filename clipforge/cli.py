"""CLI de clipforge. Claude Code (el orquestador) la usa vía los skills de .claude/skills."""
from __future__ import annotations

import json
from typing import Optional

import typer

from . import campaigns as camps
from .config import CAMPAIGNS, job_dir
from .specs import Campaign, ClipSpec

app = typer.Typer(help="Pipeline local de clips verticales.", no_args_is_help=True)
campaign_app = typer.Typer(help="Campañas (briefs de Whop, etc.)", no_args_is_help=True)
story_app = typer.Typer(help="Historias narradas sobre gameplay.", no_args_is_help=True)
app.add_typer(campaign_app, name="campaign")
app.add_typer(story_app, name="story")


def _campaign(slug: Optional[str]) -> Optional[Campaign]:
    return camps.load_campaign(slug) if slug else None


# ---------------- clips ----------------

@app.command()
def ingest(src: str, campaign: Optional[str] = typer.Option(None, "--campaign", "-c")):
    """Descarga un link (o copia un archivo local) y crea el job."""
    from .ingest import ingest as _ingest
    job_id = _ingest(src, campaign)
    typer.echo(job_id)


@app.command()
def transcribe(job_id: str, language: Optional[str] = None, force: bool = False):
    """Transcribe el video con timestamps por palabra."""
    from .transcribe import transcribe as _t
    t = _t(job_id, language, force)
    typer.echo(f"{len(t.words)} palabras, {t.duration:.0f}s, idioma {t.language}")


@app.command()
def plan(job_id: str, campaign: Optional[str] = typer.Option(None, "--campaign", "-c"), n: int = 5):
    """Claude elige los mejores momentos y escribe los specs (data/jobs/<id>/specs)."""
    from .ingest import load_job
    from .planner import plan as _plan
    from .transcribe import transcribe as _t
    job = load_job(job_id)
    results = _plan(job, _t(job_id), _campaign(campaign or job.get("campaign")), n)
    for spec, issues in results:
        flag = "  ⚠ " + "; ".join(issues) if issues else ""
        typer.echo(f"{spec.id}  {spec.score:>4.1f}  {spec.duration:>4.0f}s  {spec.hook}{flag}")


@app.command()
def render(job_id: str, only: Optional[list[str]] = typer.Option(None, "--only", help="ids de clips, ej. --only c01")):
    """Renderiza los specs del job (excepto los rechazados)."""
    from .planner import load_specs, save_specs
    from .render import render_clip
    from .transcribe import transcribe as _t
    t = _t(job_id)
    out_dir = job_dir(job_id) / "renders"
    specs = [s for s in load_specs(job_id) if s.status != "rejected" and (not only or s.id in only)]
    for s in specs:
        path = render_clip(s, t, out_dir)
        s.status = "rendered"
        typer.echo(str(path))
    save_specs(job_id, specs)


@app.command()
def clip(src: str, campaign: Optional[str] = typer.Option(None, "--campaign", "-c"), n: int = 5):
    """Todo de un jalón: link → clips renderizados."""
    from .ingest import ingest as _ingest
    job_id = _ingest(src, campaign)
    typer.echo(f"job: {job_id}")
    transcribe(job_id)
    plan(job_id, campaign, n)
    render(job_id, None)
    review()


@app.command()
def spec(job_id: str, clip_id: str, set_: Optional[list[str]] = typer.Option(None, "--set", help="campo=valor (JSON)")):
    """Ver o modificar un spec. Ej: --set end=812.5 --set 'hook=\"Nuevo hook\"' --set captions.highlight='\"#00FF88\"'"""
    from .planner import load_specs, save_specs
    specs = {s.id: s for s in load_specs(job_id)}
    s = specs[clip_id]
    if set_:
        data = s.model_dump()
        for kv in set_:
            key, _, raw = kv.partition("=")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            target = data
            *path, last = key.split(".")
            for k in path:
                target = target[k]
            target[last] = value
        s = ClipSpec.model_validate(data)
        save_specs(job_id, [s])
    typer.echo(s.model_dump_json(indent=2))


@app.command()
def review():
    """Genera data/review.html con todos los renders para revisarlos."""
    from .review import build_review
    typer.echo(str(build_review()))


@app.command()
def status():
    """Resumen de jobs, specs y renders."""
    from .config import DATA
    from .planner import load_specs
    jobs = sorted((DATA / "jobs").glob("*/job.json")) if (DATA / "jobs").exists() else []
    if not jobs:
        typer.echo("Sin jobs todavía.")
    for jp in jobs:
        job = json.loads(jp.read_text(encoding="utf-8"))
        specs = load_specs(job["job_id"])
        counts: dict[str, int] = {}
        for s in specs:
            counts[s.status] = counts.get(s.status, 0) + 1
        typer.echo(f"{job['job_id']:<14} {job.get('campaign') or '-':<16} {counts}  {job.get('title') or ''}")


# ---------------- campañas ----------------

@campaign_app.command("list")
def campaign_list():
    for c in camps.list_campaigns():
        typer.echo(f"{c.slug:<20} ${c.rate_per_1k:<5} {c.account or '-':<12} {'activa' if c.active else 'pausada'}  {c.name}")


@campaign_app.command("show")
def campaign_show(slug: str):
    typer.echo(camps.load_campaign(slug).model_dump_json(indent=2))


@campaign_app.command("new")
def campaign_new(slug: str, name: str = typer.Option(..., prompt=True)):
    """Crea campaigns/<slug>.yaml desde la plantilla para llenarlo."""
    if (CAMPAIGNS / f"{slug}.yaml").exists():
        raise typer.BadParameter("ya existe")
    camps.save_campaign(Campaign(slug=slug, name=name))
    typer.echo(str(CAMPAIGNS / f"{slug}.yaml"))


# ---------------- stories ----------------

@story_app.command("new")
def story_new(premise: str, seconds: int = 75, part: Optional[int] = None, render_now: bool = typer.Option(True, "--render/--no-render")):
    """Claude escribe una historia a partir de una premisa y (por defecto) la renderiza."""
    from .story import render_story, write_story
    spec = write_story(premise, seconds, part)
    typer.echo(f"{spec.id}: {spec.hook}")
    if render_now:
        typer.echo(str(render_story(spec)))


@story_app.command("render")
def story_render(story_id: str):
    """Re-renderiza una historia (después de editar data/stories/<id>/spec.json)."""
    from .story import load_story, render_story
    typer.echo(str(render_story(load_story(story_id))))


if __name__ == "__main__":
    app()
