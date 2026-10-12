"""Rutas del proyecto y configuración leída de .env / variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Carga un .env simple (KEY=VALUE) sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    claude_bin: str = os.environ.get("CLIPFORGE_CLAUDE_BIN", "claude")
    model: str = os.environ.get("CLIPFORGE_MODEL", "sonnet")
    whisper_model: str = os.environ.get("CLIPFORGE_WHISPER_MODEL", "small")
    device: str = os.environ.get("CLIPFORGE_DEVICE", "cpu")
    tts_voice: str = os.environ.get("CLIPFORGE_TTS_VOICE", "es-MX-JorgeNeural")


settings = Settings()

DATA = Path(os.environ.get("CLIPFORGE_DATA", ROOT / "data"))
CAMPAIGNS = ROOT / "campaigns"
PROMPTS = ROOT / "prompts"
GAMEPLAY = ROOT / "assets" / "gameplay"


def job_dir(job_id: str) -> Path:
    """Carpeta de un trabajo: data/jobs/<id>/ con source, transcript, specs y renders."""
    d = DATA / "jobs" / job_id
    for sub in ("specs", "renders"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d
