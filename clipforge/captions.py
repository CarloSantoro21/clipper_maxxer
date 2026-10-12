"""Genera subtítulos .ass (libass) estilo TikTok: palabra por palabra con la palabra activa resaltada."""
from __future__ import annotations

from .specs import CaptionStyle, Word

W, H = 1080, 1920


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB -> &HAABBGGRR (formato de ASS)."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


_ALIGN = {"lower": 2, "center": 5, "upper": 8}
_MARGIN_V = {"lower": 420, "center": 0, "upper": 300}


def build_ass(
    words: list[Word],
    style: CaptionStyle,
    offset: float = 0.0,
    hook: str | None = None,
    hook_seconds: float = 2.5,
    total: float | None = None,
) -> str:
    """words: con tiempos absolutos; offset se resta (inicio del clip)."""
    base = _ass_color(style.color)
    hi = _ass_color(style.highlight)
    outline = _ass_color("#000000")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{style.font},{style.size},{base},{hi},{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},2,{_ALIGN[style.position]},80,80,{_MARGIN_V[style.position]},1
Style: Hook,{style.font},72,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,90,90,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []

    if hook:
        events.append(f"Dialogue: 1,{_ts(0)},{_ts(hook_seconds)},Hook,,0,0,0,,{_esc(hook)}")

    rel = [Word(text=w.text, start=w.start - offset, end=w.end - offset) for w in words]
    rel = [w for w in rel if w.end > 0 and (total is None or w.start < total)]
    n = style.words_per_line

    for g in range(0, len(rel), n):
        group = rel[g:g + n]
        next_start = rel[g + n].start if g + n < len(rel) else None
        for i, w in enumerate(group):
            start = w.start
            if i + 1 < len(group):
                end = group[i + 1].start
            else:
                # el último del grupo se queda hasta que empiece el siguiente grupo (máx 0.6s de silencio)
                end = min(next_start, w.end + 0.6) if next_start else w.end + 0.4
            end = max(end, start + 0.05)
            if total is not None:
                end = min(end, total)
            parts = []
            for j, other in enumerate(group):
                txt = _esc(other.text.upper() if style.uppercase else other.text)
                if j == i:
                    if style.preset == "plain":
                        parts.append(txt)
                    elif style.preset == "pop":
                        parts.append(f"{{\\c{hi}\\fscx112\\fscy112}}{txt}{{\\c{base}\\fscx100\\fscy100}}")
                    else:
                        parts.append(f"{{\\c{hi}}}{txt}{{\\c{base}}}")
                else:
                    parts.append(txt)
            events.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")

    return header + "\n".join(events) + "\n"


def estimate_words(text: str, duration: float, lead: float = 0.0) -> list[Word]:
    """Fallback: reparte tiempos proporcionalmente al largo de cada palabra."""
    tokens = text.split()
    if not tokens:
        return []
    weights = [len(t) + 2 for t in tokens]
    total = sum(weights)
    span = max(duration - lead, 0.1)
    words, t = [], lead
    for tok, wgt in zip(tokens, weights):
        d = span * wgt / total
        words.append(Word(text=tok, start=round(t, 3), end=round(t + d, 3)))
        t += d
    return words
