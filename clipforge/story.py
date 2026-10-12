"""Modo story: Claude escribe el guion → voz TTS → subtítulos sobre gameplay vertical."""
from __future__ import annotations

import asyncio
import json
import random
import re
import subprocess
from pathlib import Path

from .captions import build_ass, estimate_words
from .claude_cli import ask_json
from .config import DATA, GAMEPLAY, PROMPTS, settings
from .render import _need_ffmpeg, duration_of, vertical_filter
from .specs import StorySpec, Word

STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "script": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "hook", "script", "hashtags"],
}

STORIES = DATA / "stories"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:40].strip("-") or "story"


def story_dir(story_id: str) -> Path:
    d = STORIES / story_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_story(premise: str, seconds: int = 75, part: int | None = None) -> StorySpec:
    prompt = (PROMPTS / "write_story.md").read_text(encoding="utf-8").format(
        premise=premise, seconds=seconds, words=int(seconds * 2.6), part=part or "única"
    )
    raw = ask_json(prompt, STORY_SCHEMA)
    base = _slug(raw["title"])
    story_id, k = base, 2
    while (STORIES / story_id).exists():
        story_id, k = f"{base}-{k}", k + 1
    spec = StorySpec(
        id=story_id,
        title=raw["title"],
        hook=raw["hook"],
        script=raw["script"],
        voice=settings.tts_voice,
        part=part,
        hashtags=[h.lstrip("#") for h in raw["hashtags"]],
    )
    save_story(spec)
    return spec


def save_story(spec: StorySpec) -> Path:
    p = story_dir(spec.id) / "spec.json"
    p.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_story(story_id: str) -> StorySpec:
    return StorySpec.model_validate(json.loads((story_dir(story_id) / "spec.json").read_text(encoding="utf-8")))


# ---------- TTS ----------

async def _tts(text: str, voice: str, rate: str, out_mp3: Path) -> list[Word]:
    import edge_tts

    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    except TypeError:  # versiones viejas de edge-tts no tienen `boundary`
        comm = edge_tts.Communicate(text, voice, rate=rate)
    words: list[Word] = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append(Word(text=chunk["text"], start=start, end=start + chunk["duration"] / 1e7))
    return words


def synthesize(spec: StorySpec) -> tuple[Path, list[Word]]:
    try:
        import edge_tts  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Falta edge-tts: pip install 'clipforge[tts]'") from e
    d = story_dir(spec.id)
    mp3 = d / "voice.mp3"
    words = asyncio.run(_tts(spec.script, spec.voice, spec.rate, mp3))
    if not words:  # sin WordBoundary: repartimos los tiempos
        words = estimate_words(spec.script, duration_of(mp3))
    (d / "words.json").write_text(json.dumps([w.model_dump() for w in words], ensure_ascii=False), encoding="utf-8")
    return mp3, words


def pick_background(spec: StorySpec) -> Path:
    if spec.background:
        return Path(spec.background)
    vids = [p for p in GAMEPLAY.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]
    if not vids:
        raise RuntimeError(
            f"No hay gameplay en {GAMEPLAY}. Graba unos minutos de Minecraft parkour (o similar) y ponlos ahí."
        )
    return random.choice(vids)


def render_story(spec: StorySpec, audio: Path | None = None, words: list[Word] | None = None) -> Path:
    _need_ffmpeg()
    d = story_dir(spec.id)
    if audio is None or words is None:
        audio, words = synthesize(spec)
    total = duration_of(audio) + 0.4
    bg = pick_background(spec)
    bg_len = duration_of(bg)
    start = spec.background_start or (random.uniform(0, max(bg_len - total, 0)) if bg_len > total else 0)

    ass = d / "captions.ass"
    label = f"Parte {spec.part}" if spec.part else None
    ass.write_text(build_ass(words, spec.captions, hook=label, hook_seconds=3, total=total), encoding="utf-8")

    out = d / f"{spec.id}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", str(bg),
        "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{total:.2f}",
        "-vf", vertical_filter(0.5, [], ass),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    spec.status = "rendered"
    save_story(spec)
    return out
