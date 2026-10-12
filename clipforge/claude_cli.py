"""Llama a Claude Code en modo headless (`claude -p`) para obtener JSON estructurado.

Usa tu sesión/suscripción de Claude Code: no hace falta API key.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile

from .config import settings


class ClaudeError(RuntimeError):
    pass


def ask_json(prompt: str, schema: dict, model: str | None = None, timeout: int = 600) -> dict:
    if not shutil.which(settings.claude_bin):
        raise ClaudeError(
            f"No encuentro '{settings.claude_bin}'. Instala Claude Code y corre `claude` una vez para iniciar sesión."
        )
    cmd = [
        settings.claude_bin, "-p",
        "--output-format", "json",
        "--model", model or settings.model,
        "--json-schema", json.dumps(schema),
        # el planner sólo piensa: no necesita herramientas
        "--disallowedTools", "Bash", "Edit", "Write", "WebFetch", "WebSearch",
    ]
    # cwd temporal: así no carga el CLAUDE.md del orquestador (ahorra contexto y uso de tu plan)
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=tmp)
    if proc.returncode != 0:
        raise ClaudeError(proc.stderr.strip() or proc.stdout.strip())
    return parse_claude_output(proc.stdout)


def parse_claude_output(stdout: str) -> dict:
    """Acepta el sobre JSON de `claude -p --output-format json` o texto con un bloque JSON."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        envelope = {"result": stdout}

    if isinstance(envelope, dict):
        if envelope.get("is_error"):
            raise ClaudeError(str(envelope.get("result")))
        for key in ("structured_output", "structuredOutput"):
            if isinstance(envelope.get(key), dict):
                return envelope[key]
        text = envelope.get("result", "")
        if isinstance(text, dict):
            return text
    else:
        text = stdout

    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ClaudeError(f"Claude no devolvió JSON:\n{text[:500]}")
    return json.loads(m.group(1))
