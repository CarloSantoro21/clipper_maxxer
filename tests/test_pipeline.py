"""Pruebas sin red ni Claude: subtítulos, validación de campaña, parseo de salida y render real con ffmpeg."""
import json
import shutil
import subprocess

import pytest

from clipforge.campaigns import validate_spec
from clipforge.captions import build_ass, estimate_words
from clipforge.claude_cli import parse_claude_output
from clipforge.planner import candidates_to_specs, snap
from clipforge.render import duration_of, probe, render_clip
from clipforge.specs import Campaign, ClipSpec, Transcript, Word, Zoom


def _transcript(n=40, step=0.5):
    words = [Word(text=f"palabra{i}", start=i * step, end=i * step + step * 0.8) for i in range(n)]
    return Transcript(duration=n * step, words=words)


def test_ass_highlights_one_word_per_event():
    t = _transcript(6)
    from clipforge.specs import CaptionStyle
    ass = build_ass(t.words, CaptionStyle(words_per_line=3), hook="Hola", hook_seconds=2)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue: 0")]
    assert len(dialogues) == 6
    assert all(l.count("\\c&H") == 2 for l in dialogues)  # activar y desactivar resaltado
    assert "Dialogue: 1,0:00:00.00,0:00:02.00,Hook" in ass


def test_ass_offset_drops_words_before_clip():
    t = _transcript(10)
    from clipforge.specs import CaptionStyle
    ass = build_ass(t.words_between(2.0, 4.0), CaptionStyle(), offset=2.0, total=2.0)
    assert "PALABRA1 " not in ass and "PALABRA4" in ass


def test_estimate_words_covers_duration():
    ws = estimate_words("uno dos tres cuatro", 4.0)
    assert ws[0].start == 0 and abs(ws[-1].end - 4.0) < 1e-6


def test_validate_adds_required_and_flags():
    t = _transcript()
    camp = Campaign(slug="x", name="X", min_seconds=30, max_seconds=60,
                    required_hashtags=["ad"], required_mentions=["@marca"], banned=["palabra3"])
    spec = ClipSpec(id="c01", job_id="j", source="s.mp4", start=0, end=5, hook="h", hashtags=["tech"])
    spec, issues = validate_spec(spec, camp, t)
    assert spec.hashtags == ["tech", "ad"] and "@marca" in spec.title
    assert any("mínimo" in i for i in issues) and any("prohibido" in i for i in issues)


def test_parse_claude_output_variants():
    assert parse_claude_output(json.dumps({"structured_output": {"clips": []}})) == {"clips": []}
    assert parse_claude_output(json.dumps({"result": "aquí va:\n```json\n{\"a\": 1}\n```"})) == {"a": 1}


def test_candidates_snap_and_sort(tmp_path, monkeypatch):
    monkeypatch.setattr("clipforge.planner.job_dir", lambda j: tmp_path)
    t = _transcript()
    raw = {"clips": [
        {"start": 1.1, "end": 6.2, "hook": "b", "title": "", "hashtags": ["#x"], "why": "", "score": 5},
        {"start": 10.3, "end": 15.0, "hook": "a", "title": "", "hashtags": [], "why": "", "score": 9},
    ]}
    specs = [s for s, _ in candidates_to_specs(raw, {"job_id": "j"}, t, None)]
    assert [s.hook for s in specs] == ["a", "b"]          # ordenados por score
    assert specs[1].hashtags == ["x"]
    assert snap(t, 1.1, 6.2)[0] == pytest.approx(1.0 - 0.08)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="sin ffmpeg")
def test_render_vertical_clip(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src),
    ], check=True)
    t = _transcript(24)
    spec = ClipSpec(id="c01", job_id="j", source=str(src), start=2, end=8, hook="Esto no lo sabías",
                    zooms=[Zoom(at=1.0, duration=1.0, scale=1.2)])
    out = render_clip(spec, t, tmp_path / "renders")
    v = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert duration_of(out) == pytest.approx(6, abs=0.3)
