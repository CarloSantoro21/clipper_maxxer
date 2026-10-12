"""Modelos de datos. El spec es la "receta" de cada video: Claude la escribe, el render la ejecuta.

Regla del proyecto: Claude nunca edita video directamente. Cualquier cambio
("acorta el hook", "subtítulos amarillos") es un cambio a un spec + re-render.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Transcripción ----------

class Word(BaseModel):
    text: str
    start: float
    end: float


class Transcript(BaseModel):
    language: str = "es"
    duration: float
    words: list[Word]

    def text_between(self, start: float, end: float) -> str:
        return " ".join(w.text for w in self.words if w.start >= start and w.end <= end)

    def words_between(self, start: float, end: float) -> list[Word]:
        return [w for w in self.words if w.end > start and w.start < end]


# ---------- Estilo ----------

class CaptionStyle(BaseModel):
    preset: Literal["karaoke", "pop", "plain"] = "karaoke"
    font: str = "Montserrat Black"
    size: int = 90                     # px sobre un lienzo de 1080x1920
    color: str = "#FFFFFF"             # color base
    highlight: str = "#FFE600"         # color de la palabra que se está diciendo
    outline: int = 6
    position: Literal["center", "lower", "upper"] = "lower"
    words_per_line: int = Field(3, ge=1, le=8)
    uppercase: bool = True


class Zoom(BaseModel):
    at: float = Field(..., ge=0, description="segundo relativo al inicio del clip")
    duration: float = Field(0.6, gt=0)
    scale: float = Field(1.15, ge=1.0, le=2.0)


Platform = Literal["tiktok", "instagram", "youtube", "x"]
Status = Literal["draft", "approved", "rejected", "rendered", "published"]


class PublishMetrics(BaseModel):
    """Métricas manuales de lo ya publicado (las llenas tú desde el dashboard). Todas opcionales."""
    published_url: Optional[str] = None
    platform: Optional[Platform] = None
    views: Optional[int] = Field(None, ge=0)
    published_at: Optional[date] = None


# ---------- Modo clip ----------

class ClipSpec(PublishMetrics):
    """Un clip vertical cortado de un video fuente."""
    id: str
    job_id: str
    campaign: Optional[str] = None
    source: str                          # ruta del video fuente
    start: float = Field(..., ge=0)
    end: float
    hook: str = Field(..., description="Texto en pantalla de los primeros segundos")
    hook_seconds: float = Field(2.5, gt=0, le=6)
    title: str = ""                      # caption/descripción para publicar
    hashtags: list[str] = []
    why: str = ""                        # por qué Claude cree que este momento pega
    score: float = Field(0, ge=0, le=10)
    crop_x: float = Field(0.5, ge=0, le=1, description="centro horizontal del recorte 9:16 (0=izq, 1=der)")
    captions: CaptionStyle = CaptionStyle()
    zooms: list[Zoom] = []
    status: Status = "draft"

    @property
    def duration(self) -> float:
        return self.end - self.start

    @model_validator(mode="after")
    def _check_range(self):
        if self.end <= self.start:
            raise ValueError("end debe ser mayor que start")
        return self


# ---------- Modo story ----------

class StorySpec(PublishMetrics):
    """Historia narrada con TTS sobre gameplay de fondo."""
    id: str
    title: str
    hook: str                            # primera frase: tiene que enganchar sola
    script: str                          # texto completo que se narra (incluye el hook)
    voice: str = "es-MX-JorgeNeural"
    rate: str = "+8%"                    # velocidad de la voz (edge-tts)
    background: Optional[str] = None     # video de gameplay; si es None se elige uno de assets/gameplay
    background_start: float = 0
    captions: CaptionStyle = CaptionStyle(position="center", words_per_line=2, size=92)
    part: Optional[int] = None           # para series "Parte 1/2/3"
    hashtags: list[str] = []
    status: Status = "draft"


# ---------- Campañas (brief de Whop u otro marketplace) ----------

class Campaign(BaseModel):
    """Reglas de una campaña. Se llena a partir del brief con /campaign."""
    slug: str
    name: str
    url: str = ""
    niche: str = ""
    account: str = ""                    # cuenta donde se publica (ej. "tech-es")
    rate_per_1k: float = 0
    platforms: list[Platform] = ["tiktok", "instagram", "youtube"]
    min_seconds: float = 15
    max_seconds: float = 90
    language: str = "es"
    source_urls: list[str] = []          # material autorizado por la campaña
    required_hashtags: list[str] = []
    required_mentions: list[str] = []
    required_text: list[str] = []        # textos obligatorios en caption
    banned: list[str] = []               # temas/palabras prohibidas
    notes: str = ""
    active: bool = True
