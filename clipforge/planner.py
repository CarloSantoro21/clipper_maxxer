"""Claude elige momentos y escribe los specs de los clips."""
from __future__ import annotations

import json

import yaml

from .campaigns import validate_spec
from .claude_cli import ask_json
from .config import PROMPTS, job_dir
from .specs import Campaign, ClipSpec, Transcript
from .transcribe import transcript_for_prompt

CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "hook": {"type": "string"},
                    "title": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "why": {"type": "string"},
                    "score": {"type": "number"},
                    "crop_x": {"type": "number"},
                },
                "required": ["start", "end", "hook", "title", "hashtags", "why", "score"],
            },
        }
    },
    "required": ["clips"],
}


def build_prompt(job: dict, t: Transcript, campaign: Campaign | None, n: int) -> str:
    camp = (
        yaml.safe_dump(campaign.model_dump(exclude={"source_urls", "active"}), allow_unicode=True, sort_keys=False)
        if campaign else "Sin campaña: idioma español, 20–60 s, apto para todo público."
    )
    tpl = (PROMPTS / "plan_clips.md").read_text(encoding="utf-8")
    return tpl.format(
        n=n,
        title=job.get("title") or job["job_id"],
        duration=round(t.duration),
        campaign=camp,
        transcript=transcript_for_prompt(t),
    )


def snap(t: Transcript, start: float, end: float) -> tuple[float, float]:
    """Ajusta inicio/fin a los bordes de palabra más cercanos para no cortar a media sílaba."""
    if not t.words:
        return start, end
    s = min(t.words, key=lambda w: abs(w.start - start)).start
    e = min(t.words, key=lambda w: abs(w.end - end)).end
    return max(s - 0.08, 0), min(e + 0.25, t.duration)


def candidates_to_specs(
    raw: dict, job: dict, t: Transcript, campaign: Campaign | None
) -> list[tuple[ClipSpec, list[str]]]:
    d = job_dir(job["job_id"])
    out = []
    for i, c in enumerate(sorted(raw.get("clips", []), key=lambda c: -c.get("score", 0)), start=1):
        start, end = snap(t, float(c["start"]), float(c["end"]))
        if end <= start:
            continue
        spec = ClipSpec(
            id=f"c{i:02d}",
            job_id=job["job_id"],
            source=str(d / "source.mp4"),
            start=round(start, 3),
            end=round(end, 3),
            hook=c["hook"].strip(),
            title=c.get("title", "").strip(),
            hashtags=[h.lstrip("#") for h in c.get("hashtags", [])],
            why=c.get("why", ""),
            score=max(0, min(10, float(c.get("score", 0)))),
            crop_x=max(0, min(1, float(c.get("crop_x", 0.5)))),
        )
        out.append(validate_spec(spec, campaign, t))
    return out


def plan(job: dict, t: Transcript, campaign: Campaign | None, n: int = 5) -> list[tuple[ClipSpec, list[str]]]:
    raw = ask_json(build_prompt(job, t, campaign, n), CANDIDATES_SCHEMA)
    results = candidates_to_specs(raw, job, t, campaign)
    save_specs(job["job_id"], [s for s, _ in results])
    return results


def save_specs(job_id: str, specs: list[ClipSpec]) -> None:
    d = job_dir(job_id) / "specs"
    for s in specs:
        (d / f"{s.id}.json").write_text(s.model_dump_json(indent=2), encoding="utf-8")


def load_specs(job_id: str) -> list[ClipSpec]:
    d = job_dir(job_id) / "specs"
    return [ClipSpec.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(d.glob("*.json"))]
