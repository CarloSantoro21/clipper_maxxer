"""Staging mínimo: genera data/review.html con todos los clips renderizados para revisarlos en el navegador.

(El dashboard con chat al orquestador es la fase 2; esto sirve desde el día 1.)
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .config import DATA
from .specs import ClipSpec, StorySpec


def _card(video: Path, title: str, meta: list[tuple[str, str]], caption: str) -> str:
    rel = video.relative_to(DATA).as_posix()
    rows = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in meta if v)
    cap = html.escape(caption)
    return f"""<article>
  <video src="{rel}" controls preload="metadata" playsinline></video>
  <h2>{html.escape(title)}</h2>
  <dl>{rows}</dl>
  <textarea readonly>{cap}</textarea>
  <button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent='Copiado'">Copiar caption</button>
</article>"""


def build_review() -> Path:
    cards: list[str] = []
    for spec_path in sorted((DATA / "jobs").glob("*/specs/*.json")):
        spec = ClipSpec.model_validate(json.loads(spec_path.read_text(encoding="utf-8")))
        video = spec_path.parent.parent / "renders" / f"{spec.id}.mp4"
        if not video.exists():
            continue
        caption = spec.title + "\n\n" + " ".join(f"#{h}" for h in spec.hashtags)
        cards.append(_card(video, spec.hook, [
            ("Job / clip", f"{spec.job_id} / {spec.id}"),
            ("Campaña", spec.campaign or ""),
            ("Duración", f"{spec.duration:.0f}s ({spec.start:.1f}–{spec.end:.1f})"),
            ("Score", f"{spec.score:.1f}"),
            ("Por qué", spec.why),
        ], caption))
    for spec_path in sorted((DATA / "stories").glob("*/spec.json")):
        s = StorySpec.model_validate(json.loads(spec_path.read_text(encoding="utf-8")))
        video = spec_path.parent / f"{s.id}.mp4"
        if not video.exists():
            continue
        caption = s.title + "\n\n" + " ".join(f"#{h}" for h in s.hashtags)
        cards.append(_card(video, s.title, [("Story", s.id), ("Hook", s.hook)], caption))

    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clipforge · revisión</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--ink:#1d1c1a;--mute:#6b6a65;--line:#e3e1db}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--card:#1f1f1d;--ink:#eceae4;--mute:#9c9a93;--line:#33322f}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
header{{padding:20px 16px}} h1{{margin:0;font-size:20px;font-weight:600}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding:0 16px 32px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}}
video{{width:100%;aspect-ratio:9/16;background:#000;border-radius:8px}}
h2{{font-size:16px;margin:10px 0 6px}} dl{{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:0 0 8px;font-size:13px}}
dt{{color:var(--mute)}} dd{{margin:0}}
textarea{{width:100%;box-sizing:border-box;min-height:70px;font:13px system-ui;background:transparent;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px}}
button{{margin-top:6px;padding:6px 12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}}
</style></head><body>
<header><h1>Clips listos para revisar ({len(cards)})</h1></header>
<main>{''.join(cards) or '<p>No hay renders todavía.</p>'}</main>
</body></html>"""
    out = DATA / "review.html"
    DATA.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
