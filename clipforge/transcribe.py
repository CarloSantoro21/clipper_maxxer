"""Transcripción local con faster-whisper (timestamps por palabra)."""
from __future__ import annotations

from pathlib import Path

from .config import job_dir, settings
from .specs import Transcript, Word


def transcribe(job_id: str, language: str | None = None, force: bool = False) -> Transcript:
    d = job_dir(job_id)
    out = d / "transcript.json"
    if out.exists() and not force:
        return Transcript.model_validate_json(out.read_text(encoding="utf-8"))

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Falta faster-whisper: pip install 'clipforge[transcribe]'") from e

    compute = "float16" if settings.device == "cuda" else "int8"
    model = WhisperModel(settings.whisper_model, device=settings.device, compute_type=compute)
    segments, info = model.transcribe(
        str(d / "source.mp4"),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append(Word(text=text, start=round(w.start, 3), end=round(w.end, 3)))

    t = Transcript(language=info.language, duration=info.duration, words=words)
    out.write_text(t.model_dump_json(indent=1), encoding="utf-8")
    return t


def transcript_for_prompt(t: Transcript, words_per_line: int = 14) -> str:
    """Formato compacto con timestamps para que Claude elija momentos: '[123.4] texto...'"""
    lines = []
    for i in range(0, len(t.words), words_per_line):
        chunk = t.words[i:i + words_per_line]
        lines.append(f"[{chunk[0].start:.1f}] " + " ".join(w.text for w in chunk))
    return "\n".join(lines)


def load_transcript(path: Path) -> Transcript:
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))
