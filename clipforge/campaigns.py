"""Campañas en campaigns/<slug>.yaml y validación de specs contra sus reglas."""
from __future__ import annotations

import sys

import yaml
from pydantic import ValidationError

from .config import CAMPAIGNS
from .specs import Campaign, ClipSpec, Transcript


def load_campaign(slug: str) -> Campaign:
    path = CAMPAIGNS / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No existe la campaña {slug} ({path})")
    return Campaign.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def list_campaigns() -> list[Campaign]:
    """Campañas válidas. Un YAML roto (editado a mano) se salta con aviso en vez de tumbar todo."""
    out = []
    for p in sorted(CAMPAIGNS.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        try:
            out.append(Campaign.model_validate(yaml.safe_load(p.read_text(encoding="utf-8"))))
        except (yaml.YAMLError, ValidationError, TypeError) as e:
            print(f"[clipforge] se ignora {p.name}: no es una campaña válida ({e.__class__.__name__})", file=sys.stderr)
    return out


def save_campaign(c: Campaign) -> None:
    CAMPAIGNS.mkdir(exist_ok=True)
    (CAMPAIGNS / f"{c.slug}.yaml").write_text(
        yaml.safe_dump(c.model_dump(), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def validate_spec(spec: ClipSpec, campaign: Campaign | None, transcript: Transcript) -> tuple[ClipSpec, list[str]]:
    """Aplica arreglos automáticos y devuelve (spec, problemas que requieren tu revisión)."""
    issues: list[str] = []
    if campaign is None:
        return spec, issues

    if spec.duration < campaign.min_seconds:
        issues.append(f"dura {spec.duration:.0f}s; la campaña pide mínimo {campaign.min_seconds:.0f}s")
    if spec.duration > campaign.max_seconds:
        issues.append(f"dura {spec.duration:.0f}s; la campaña permite máximo {campaign.max_seconds:.0f}s")

    # hashtags y menciones obligatorias: se agregan solos
    tags = list(dict.fromkeys(spec.hashtags + campaign.required_hashtags))
    title = spec.title
    for m in campaign.required_mentions:
        if m not in title:
            title = f"{title} {m}".strip()
    for t in campaign.required_text:
        if t not in title:
            title = f"{title}\n{t}".strip()
    spec = spec.model_copy(update={"hashtags": tags, "title": title, "campaign": campaign.slug})

    text = " ".join([transcript.text_between(spec.start, spec.end), spec.hook, spec.title]).lower()
    for b in campaign.banned:
        if b.lower() in text:
            issues.append(f"contiene un tema prohibido por la campaña: '{b}'")

    return spec, issues
