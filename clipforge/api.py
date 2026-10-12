"""API local del dashboard (Fase 2). Arranca con `clipforge serve`.

Mismo principio que la CLI: el dashboard nunca edita video; sólo cambia specs JSON
y encola re-renders que hace el código determinista de render.py / story.py.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Optional

import yaml
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import campaigns as camps
from . import config
from . import pipeline
from . import story as story_mod
from .claude_cli import ClaudeError, ask_json
from .planner import load_specs, save_specs
from .specs import Campaign, ClipSpec, Platform, Status, StorySpec, Transcript, Zoom

SAFE_ID = re.compile(r"^[\w-]{1,80}$")
STORY_ACCOUNT = "experimentos"  # cuenta propia de las stories (ver CLAUDE.md)


def _safe(value: str, what: str = "id") -> str:
    if not SAFE_ID.match(value or ""):
        raise HTTPException(400, f"{what} inválido: {value!r}")
    return value


def _jobs_dir() -> Path:
    return config.DATA / "jobs"


def _media_url(path: Path) -> Optional[str]:
    """URL bajo /media con ?v=mtime para que el navegador no muestre un render viejo."""
    if not path.exists():
        return None
    rel = path.resolve().relative_to(config.DATA.resolve()).as_posix()
    return f"/media/{rel}?v={int(path.stat().st_mtime)}"


# ======================================================================
# Cola de tareas: un trabajo a la vez, en memoria
# ======================================================================

class TaskContext:
    def __init__(self, task: dict, lock: threading.Lock):
        self._task, self._lock = task, lock

    def log(self, msg: str) -> None:
        with self._lock:
            for line in str(msg).splitlines() or [""]:
                self._task["log"].append(f"{datetime.now():%H:%M:%S} {line}")
            del self._task["log"][:-400]

    def progress(self, value: float, step: str = "") -> None:
        with self._lock:
            self._task["progress"] = round(max(0.0, min(1.0, value)), 3)
            if step:
                self._task["step"] = step

    def result(self, **data: Any) -> None:
        with self._lock:
            self._task["result"].update(data)


class TaskQueue:
    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self._fns: dict[str, Callable[[TaskContext], None]] = {}
        self._pending: deque[str] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._worker: Optional[threading.Thread] = None

    def submit(self, kind: str, label: str, fn: Callable[[TaskContext], None], target: Optional[dict] = None) -> dict:
        tid = uuid.uuid4().hex[:10]
        task = {
            "id": tid, "kind": kind, "label": label, "target": target or {},
            "status": "queued", "progress": 0.0, "step": "en cola", "log": [],
            "result": {}, "error": None,
            "created_at": time.time(), "started_at": None, "finished_at": None,
        }
        with self._wake:
            self.tasks[tid] = task
            self._fns[tid] = fn
            self._pending.append(tid)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, daemon=True, name="clipforge-queue")
                self._worker.start()
            self._wake.notify()
        return self.snapshot(tid)

    def _run(self) -> None:
        while True:
            with self._wake:
                while not self._pending:
                    self._wake.wait()
                tid = self._pending.popleft()
                task, fn = self.tasks[tid], self._fns.pop(tid)
                task.update(status="running", started_at=time.time(), step="empezando")
            ctx = TaskContext(task, self._lock)
            try:
                fn(ctx)
                with self._lock:
                    task.update(status="done", progress=1.0, step="listo")
            except Exception as e:  # el error queda en la tarea; la cola sigue
                ctx.log(traceback.format_exc(limit=3))
                with self._lock:
                    task.update(status="error", error=str(e) or e.__class__.__name__, step="error")
            finally:
                with self._lock:
                    task["finished_at"] = time.time()

    def snapshot(self, tid: str, with_log: bool = True) -> dict:
        with self._lock:
            t = dict(self.tasks[tid])
            t["log"] = list(t["log"]) if with_log else t["log"][-3:]
            t["result"] = dict(t["result"])
            return t

    def list(self) -> list[dict]:
        with self._lock:
            ids = sorted(self.tasks, key=lambda i: -self.tasks[i]["created_at"])
        return [self.snapshot(i, with_log=False) for i in ids]

    def wait(self, tid: str, timeout: float = 30) -> dict:
        """Útil en tests: espera a que una tarea termine."""
        end = time.time() + timeout
        while time.time() < end:
            if self.tasks[tid]["status"] in ("done", "error"):
                break
            time.sleep(0.02)
        return self.snapshot(tid)


# ======================================================================
# Serialización de jobs / clips / stories
# ======================================================================

def _campaign_or_none(slug: Optional[str]) -> Optional[Campaign]:
    if not slug:
        return None
    try:
        return camps.load_campaign(slug)
    except (FileNotFoundError, ValidationError, yaml.YAMLError):
        return None


def _load_transcript(job_id: str) -> Optional[Transcript]:
    p = _jobs_dir() / job_id / "transcript.json"
    if not p.exists():
        return None
    try:
        return Transcript.model_validate_json(p.read_text(encoding="utf-8"))
    except ValidationError:
        return None


def _issues(spec: ClipSpec, campaign: Optional[Campaign], transcript: Optional[Transcript]) -> list[str]:
    """Las mismas ⚠ que marca la CLI (duración fuera de rango, temas prohibidos)."""
    if campaign is None:
        return []
    t = transcript or Transcript(duration=spec.end, words=[])
    return camps.validate_spec(spec, campaign, t)[1]


def clip_out(spec: ClipSpec, campaign: Optional[Campaign], transcript: Optional[Transcript]) -> dict:
    renders = _jobs_dir() / spec.job_id / "renders"
    video = renders / f"{spec.id}.mp4"
    data = spec.model_dump(mode="json")
    data.update(
        kind="clip",
        duration=round(spec.duration, 3),
        account=campaign.account if campaign else "",
        video_url=_media_url(video),
        thumb_url=_media_url(renders / f"{spec.id}.jpg"),
        rendered_at=video.stat().st_mtime if video.exists() else None,
        issues=_issues(spec, campaign, transcript),
        caption=_caption(spec.title, spec.hashtags),
    )
    return data


def story_out(spec: StorySpec) -> dict:
    d = story_mod.STORIES / spec.id
    video = d / f"{spec.id}.mp4"
    data = spec.model_dump(mode="json")
    data.update(
        kind="story",
        account=STORY_ACCOUNT,
        video_url=_media_url(video),
        thumb_url=_media_url(d / f"{spec.id}.jpg"),
        rendered_at=video.stat().st_mtime if video.exists() else None,
        caption=_caption(spec.title, spec.hashtags),
    )
    return data


def _caption(title: str, hashtags: list[str]) -> str:
    tags = " ".join(f"#{h}" for h in hashtags)
    return f"{title}\n\n{tags}".strip()


def job_out(job_id: str) -> dict:
    jp = _jobs_dir() / job_id / "job.json"
    if not jp.exists():
        raise HTTPException(404, f"No existe el job {job_id}")
    job = json.loads(jp.read_text(encoding="utf-8"))
    campaign_cache: dict[Optional[str], Optional[Campaign]] = {}
    transcript = _load_transcript(job_id)
    clips = []
    for s in load_specs(job_id):
        slug = s.campaign or job.get("campaign")
        if slug not in campaign_cache:
            campaign_cache[slug] = _campaign_or_none(slug)
        clips.append(clip_out(s, campaign_cache[slug], transcript))
    camp = _campaign_or_none(job.get("campaign"))
    job.update(
        account=camp.account if camp else "",
        has_transcript=transcript is not None,
        source_duration=transcript.duration if transcript else job.get("duration"),
        clips=clips,
        updated_at=max([jp.stat().st_mtime] + [c["rendered_at"] or 0 for c in clips]),
    )
    return job


def _get_clip(job_id: str, clip_id: str) -> ClipSpec:
    _safe(job_id, "job"), _safe(clip_id, "clip")
    if not (_jobs_dir() / job_id / "job.json").exists():
        raise HTTPException(404, f"No existe el job {job_id}")
    p = _jobs_dir() / job_id / "specs" / f"{clip_id}.json"
    if not p.exists():
        raise HTTPException(404, f"No existe el clip {clip_id} en {job_id}")
    return ClipSpec.model_validate_json(p.read_text(encoding="utf-8"))


def _get_story(story_id: str) -> StorySpec:
    _safe(story_id, "story")
    if not (story_mod.STORIES / story_id / "spec.json").exists():
        raise HTTPException(404, f"No existe la story {story_id}")
    return story_mod.load_story(story_id)


# ======================================================================
# Modelos de entrada
# ======================================================================

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaptionPatch(Strict):
    preset: Optional[Literal["karaoke", "pop", "plain"]] = None
    font: Optional[str] = None
    size: Optional[int] = Field(None, ge=20, le=200)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    highlight: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    outline: Optional[int] = Field(None, ge=0, le=20)
    position: Optional[Literal["center", "lower", "upper"]] = None
    words_per_line: Optional[int] = Field(None, ge=1, le=8)
    uppercase: Optional[bool] = None


class MetricsPatch(Strict):
    published_url: Optional[str] = None
    platform: Optional[Platform] = None
    views: Optional[int] = Field(None, ge=0)
    published_at: Optional[date] = None


class ClipPatch(MetricsPatch):
    hook: Optional[str] = None
    hook_seconds: Optional[float] = None
    start: Optional[float] = None
    end: Optional[float] = None
    title: Optional[str] = None
    hashtags: Optional[list[str]] = None
    captions: Optional[CaptionPatch] = None
    zooms: Optional[list[Zoom]] = None
    crop_x: Optional[float] = None
    status: Optional[Status] = None


class StoryPatch(MetricsPatch):
    title: Optional[str] = None
    hook: Optional[str] = None
    script: Optional[str] = None
    voice: Optional[str] = None
    rate: Optional[str] = None
    background: Optional[str] = None
    background_start: Optional[float] = None
    captions: Optional[CaptionPatch] = None
    part: Optional[int] = None
    hashtags: Optional[list[str]] = None
    status: Optional[Status] = None


class NewJob(Strict):
    src: str = Field(..., min_length=1)
    campaign: Optional[str] = None
    n: int = Field(5, ge=1, le=20)
    # CLAUDE.md regla 1: si el link no está en una campaña activa, hay que decir de dónde viene el permiso
    permission_note: Optional[str] = None


class NewStory(Strict):
    premise: str = Field(..., min_length=3)
    seconds: int = Field(75, ge=15, le=180)
    part: Optional[int] = Field(None, ge=1, le=20)
    render: bool = True


class ExtractIn(Strict):
    text: str = Field(..., min_length=10)


class ChatContext(Strict):
    job: Optional[str] = None
    clip: Optional[str] = None
    story: Optional[str] = None


class ChatIn(Strict):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    context: ChatContext = ChatContext()


def apply_patch(model: BaseModel, patch: BaseModel) -> BaseModel:
    """Mezcla el patch sobre el spec y revalida todo el modelo (ej. end > start)."""
    data = model.model_dump()
    changes = patch.model_dump(exclude_unset=True)
    if "captions" in changes and changes["captions"] is not None:
        data["captions"] = {**data["captions"], **{k: v for k, v in changes.pop("captions").items() if v is not None}}
    if "hashtags" in changes and changes["hashtags"] is not None:
        changes["hashtags"] = [h.strip().lstrip("#") for h in changes["hashtags"] if h.strip().lstrip("#")]
    data.update(changes)
    try:
        return type(model).model_validate(data)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False, include_input=False)) from e


# ======================================================================
# Permiso de la fuente (regla 1 del proyecto)
# ======================================================================

def source_allowed(src: str, campaign_slug: Optional[str]) -> bool:
    """Archivos locales = contenido propio. Links: deben estar en source_urls de una campaña activa."""
    if not src.startswith("http"):
        return True
    norm = src.strip().rstrip("/")
    candidates = camps.list_campaigns()
    if campaign_slug:
        candidates = [c for c in candidates if c.slug == campaign_slug] or candidates
    return any(c.active and norm in [u.strip().rstrip("/") for u in c.source_urls] for c in candidates)


# ======================================================================
# Extracción de campañas con Claude
# ======================================================================

def campaign_schema() -> dict:
    schema = Campaign.model_json_schema()
    schema.pop("title", None)
    return schema


def build_extract_prompt(text: str) -> str:
    plantilla = (config.CAMPAIGNS / "_plantilla.yaml")
    ejemplo = plantilla.read_text(encoding="utf-8") if plantilla.exists() else ""
    return f"""Extrae las reglas de este brief de campaña de clipping (Whop, Vyro, etc.) al JSON del schema.

- slug: corto, minúsculas y guiones.
- rate_per_1k: USD por cada 1,000 vistas (número; 0 si no lo dice).
- min_seconds / max_seconds: duración permitida de cada clip.
- source_urls: links del material autorizado para clipear.
- required_hashtags sin '#'; required_mentions con '@'; required_text: textos obligatorios en la descripción.
- banned: temas o palabras prohibidas.
- account: déjalo vacío si el brief no lo deja claro.
- Todo lo que no quepa en los campos (y cualquier ambigüedad) va en notes, en español.
- active: false (Carlo la activa al revisar).

Plantilla de referencia:
{ejemplo}

Brief:
\"\"\"
{text.strip()}
\"\"\"
"""


def extract_campaign(text: str) -> Campaign:
    raw = ask_json(build_extract_prompt(text), campaign_schema())
    raw.setdefault("slug", "nueva-campana")
    raw.setdefault("name", raw["slug"])
    raw["slug"] = re.sub(r"[^a-z0-9-]+", "-", str(raw["slug"]).lower()).strip("-")[:60] or "nueva-campana"
    raw["required_hashtags"] = [h.lstrip("#") for h in raw.get("required_hashtags", [])]
    raw["active"] = False
    known = Campaign.model_fields
    return Campaign.model_validate({k: v for k, v in raw.items() if k in known})


# ======================================================================
# Chat con el orquestador (claude -p con stream-json)
# ======================================================================

CHAT_TOOLS = ["Bash(clipforge:*)", "Read", "Edit", "Glob", "Grep"]


def context_line(ctx: ChatContext) -> str:
    parts = []
    if ctx.job:
        parts.append(f"job={ctx.job} (data/jobs/{ctx.job}/)")
    if ctx.clip and ctx.job:
        parts.append(f"clip={ctx.clip} (spec: data/jobs/{ctx.job}/specs/{ctx.clip}.json)")
    if ctx.story:
        parts.append(f"story={ctx.story} (spec: data/stories/{ctx.story}/spec.json)")
    where = ", ".join(parts) if parts else "ningún clip seleccionado"
    return f"[Contexto del dashboard: {where}. Carlo revisa en el dashboard; tras cambiar un spec, re-renderiza con clipforge.]"


def build_chat_command(session_id: Optional[str] = None, claude_bin: Optional[str] = None) -> list[str]:
    """Comando de `claude -p`. El mensaje va por stdin (así --allowedTools, que es variádico, no se lo come)."""
    exe = claude_bin or config.settings.claude_bin
    exe = shutil.which(exe) or exe  # en Windows resuelve claude.cmd
    cmd = [
        exe, "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode", "acceptEdits",
        "--allowedTools", *CHAT_TOOLS,
    ]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _tool_summary(block: dict) -> dict:
    inp = block.get("input") or {}
    detail = inp.get("command") or inp.get("file_path") or inp.get("pattern") or ""
    return {"name": block.get("name", "?"), "detail": str(detail)[:200]}


def stream_json_to_sse(lines: Iterator[str]) -> Iterator[str]:
    """Traduce el stream-json de Claude Code a eventos SSE: text, tool, done."""
    session_id = None
    streamed = False  # si ya llegaron deltas, no repetimos el texto del mensaje completo
    final_sent = False
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        session_id = ev.get("session_id") or session_id
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            yield _sse("session", {"session_id": session_id})
        elif kind == "stream_event":
            inner = ev.get("event") or {}
            if inner.get("type") == "message_start":
                streamed = False
            elif inner.get("type") == "content_block_delta":
                delta = inner.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    streamed = True
                    yield _sse("text", {"text": delta["text"]})
        elif kind == "assistant":
            for block in (ev.get("message") or {}).get("content", []):
                if block.get("type") == "text" and not streamed and block.get("text"):
                    yield _sse("text", {"text": block["text"]})
                elif block.get("type") == "tool_use":
                    yield _sse("tool", _tool_summary(block))
            streamed = False
        elif kind == "result":
            final_sent = True
            yield _sse("done", {
                "session_id": session_id,
                "is_error": bool(ev.get("is_error")),
                "result": ev.get("result") if ev.get("is_error") else None,
                "cost_usd": ev.get("total_cost_usd"),
            })
    if not final_sent:
        yield _sse("done", {"session_id": session_id, "is_error": True, "result": "Claude terminó sin respuesta."})


def run_chat(body: ChatIn) -> Iterator[str]:
    cmd = build_chat_command(body.session_id)
    if not shutil.which(cmd[0]):
        yield _sse("done", {"session_id": body.session_id, "is_error": True,
                            "result": f"No encuentro '{cmd[0]}'. Instala Claude Code e inicia sesión con `claude`."})
        return
    prompt = context_line(body.context) + "\n\n" + body.message
    proc = subprocess.Popen(
        cmd, cwd=str(config.ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    try:
        assert proc.stdin and proc.stdout
        proc.stdin.write(prompt)
        proc.stdin.close()
        yield from stream_json_to_sse(iter(proc.stdout.readline, ""))
        proc.wait(timeout=10)
        if proc.returncode and proc.stderr:
            err = proc.stderr.read().strip()
            if err:
                yield _sse("error", {"message": err[-1500:]})
    finally:
        if proc.poll() is None:
            proc.kill()


# ======================================================================
# App
# ======================================================================

def create_app() -> FastAPI:
    app = FastAPI(title="clipforge", version="0.2.0")
    queue = TaskQueue()
    app.state.queue = queue

    origins = [o.strip() for o in os.environ.get(
        "CLIPFORGE_CORS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # desde el celular en la misma red: cualquier IP privada en el puerto 3000
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    config.DATA.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(config.DATA)), name="media")

    # ---------- salud ----------
    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "data": str(config.DATA),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "claude": bool(shutil.which(config.settings.claude_bin)),
        }

    # ---------- jobs / clips ----------
    @app.get("/api/jobs")
    def list_jobs():
        d = _jobs_dir()
        jobs = [job_out(p.parent.name) for p in d.glob("*/job.json")] if d.exists() else []
        return sorted(jobs, key=lambda j: -j["updated_at"])

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return job_out(_safe(job_id, "job"))

    @app.post("/api/jobs", status_code=202)
    def new_job(body: NewJob):
        if body.campaign:
            _safe(body.campaign, "campaña")
            if _campaign_or_none(body.campaign) is None:
                raise HTTPException(404, f"No existe la campaña {body.campaign}")
        if not source_allowed(body.src, body.campaign) and not (body.permission_note or "").strip():
            raise HTTPException(409, "Ese link no está en los source_urls de ninguna campaña activa. "
                                     "Indica de dónde viene el permiso (contenido propio, licencia libre…).")

        def work(ctx: TaskContext):
            if body.permission_note:
                ctx.log(f"permiso: {body.permission_note}")
            job_id = pipeline.clip_pipeline(body.src, body.campaign, body.n, log=ctx.log, progress=ctx.progress)
            ctx.result(job=job_id)

        return queue.submit("clip", f"Clips de {body.src}", work, {"campaign": body.campaign})

    @app.patch("/api/jobs/{job_id}/clips/{clip_id}")
    def patch_clip(job_id: str, clip_id: str, patch: ClipPatch):
        spec = apply_patch(_get_clip(job_id, clip_id), patch)
        save_specs(job_id, [spec])
        job = json.loads((_jobs_dir() / job_id / "job.json").read_text(encoding="utf-8"))
        return clip_out(spec, _campaign_or_none(spec.campaign or job.get("campaign")), _load_transcript(job_id))

    @app.post("/api/jobs/{job_id}/clips/{clip_id}/render", status_code=202)
    def render_clip(job_id: str, clip_id: str):
        spec = _get_clip(job_id, clip_id)
        if spec.status == "rejected":
            raise HTTPException(409, "El clip está rechazado; cámbiale el estado antes de renderizar.")

        def work(ctx: TaskContext):
            ctx.progress(0.1, f"renderizando {clip_id}")
            pipeline.render_job(job_id, [clip_id], log=ctx.log)
            ctx.result(job=job_id, clip=clip_id)

        return queue.submit("render", f"Re-render {job_id}/{clip_id}", work, {"job": job_id, "clip": clip_id})

    # ---------- stories ----------
    @app.get("/api/stories")
    def list_stories():
        d = story_mod.STORIES
        out = []
        for p in sorted(d.glob("*/spec.json")) if d.exists() else []:
            try:
                out.append(story_out(StorySpec.model_validate_json(p.read_text(encoding="utf-8"))))
            except ValidationError:
                continue
        return sorted(out, key=lambda s: -(s["rendered_at"] or 0))

    @app.get("/api/stories/{story_id}")
    def get_story(story_id: str):
        return story_out(_get_story(story_id))

    @app.post("/api/stories", status_code=202)
    def new_story(body: NewStory):
        def work(ctx: TaskContext):
            ctx.progress(0.1, "escribiendo guion con Claude")
            spec = story_mod.write_story(body.premise, body.seconds, body.part)
            ctx.log(f"{spec.id}: {spec.hook}")
            ctx.result(story=spec.id)
            if body.render:
                ctx.progress(0.5, "voz y render")
                pipeline.render_story_by_id(spec.id, log=ctx.log)

        return queue.submit("story", f"Story: {body.premise[:60]}", work)

    @app.patch("/api/stories/{story_id}")
    def patch_story(story_id: str, patch: StoryPatch):
        spec = apply_patch(_get_story(story_id), patch)
        story_mod.save_story(spec)
        return story_out(spec)

    @app.post("/api/stories/{story_id}/render", status_code=202)
    def render_story(story_id: str):
        _get_story(story_id)

        def work(ctx: TaskContext):
            ctx.progress(0.1, "voz y render")
            pipeline.render_story_by_id(story_id, log=ctx.log)
            ctx.result(story=story_id)

        return queue.submit("render", f"Re-render story {story_id}", work, {"story": story_id})

    # ---------- tareas ----------
    @app.get("/api/tasks")
    def list_tasks():
        return queue.list()

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str):
        if task_id not in queue.tasks:
            raise HTTPException(404, "No existe esa tarea")
        return queue.snapshot(task_id)

    # ---------- campañas ----------
    @app.get("/api/campaigns")
    def list_campaigns():
        return [c.model_dump(mode="json") for c in camps.list_campaigns()]

    @app.get("/api/campaigns/{slug}")
    def get_campaign(slug: str):
        c = _campaign_or_none(_safe(slug, "slug"))
        if c is None:
            raise HTTPException(404, f"No existe la campaña {slug}")
        return c.model_dump(mode="json")

    def _save(c: Campaign) -> dict:
        _safe(c.slug, "slug")
        if c.slug.startswith("_"):
            raise HTTPException(400, "El slug no puede empezar con '_'")
        camps.save_campaign(c)
        return c.model_dump(mode="json")

    @app.put("/api/campaigns")
    def put_campaign(c: Campaign):
        return _save(c)

    @app.put("/api/campaigns/{slug}")
    def put_campaign_slug(slug: str, c: Campaign):
        if c.slug != slug:
            raise HTTPException(400, "El slug del cuerpo no coincide con la URL")
        return _save(c)

    @app.post("/api/campaigns/extract")
    def extract(body: ExtractIn):
        try:
            draft = extract_campaign(body.text)
        except ClaudeError as e:
            raise HTTPException(502, f"Claude no pudo extraer el brief: {e}") from e
        except ValidationError as e:
            raise HTTPException(502, f"La respuesta de Claude no cuadra con el schema: {e}") from e
        exists = (config.CAMPAIGNS / f"{draft.slug}.yaml").exists()
        return {"draft": draft.model_dump(mode="json"), "exists": exists}

    # ---------- chat ----------
    @app.post("/api/chat")
    def chat(body: ChatIn = Body(...)):
        for v in (body.context.job, body.context.clip, body.context.story):
            if v:
                _safe(v)
        return StreamingResponse(
            run_chat(body), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
