---
name: clip
description: Convierte un link de video en clips verticales listos para revisar. Úsalo cuando Carlo pase un link de YouTube/Drive o diga "haz clips de...".
---

# /clip <url> [campaña] [n]

1. **Permiso.** Busca el link en `campaigns/*.yaml` (`source_urls`). Si no aparece en una campaña activa, pregunta a Carlo de dónde viene el permiso y no sigas hasta que responda.
2. **Brief.** `clipforge campaign show <slug>` y ten presentes duración, idioma, hashtags y temas prohibidos.
3. **Pipeline.** `clipforge ingest <url> -c <slug>` → `clipforge transcribe <job>` → `clipforge plan <job> -c <slug> -n <n>` (5 por defecto).
4. **Revisión propia antes de renderizar.** Lee los specs en `data/jobs/<job>/specs/`. Para cada uno, revisa contra la transcripción (`transcript.json`):
   - ¿La primera frase dicha engancha sin contexto? Si no, mueve `start` a la frase fuerte.
   - ¿Termina justo después del remate? Recorta colas.
   - ¿El hook promete algo que el clip entrega?
   - Arregla cualquier ⚠ del plan. Usa `clipforge spec <job> <clip> --set ...`.
   - Si un candidato es malo, márcalo `--set 'status="rejected"'`.
   Si quieres segunda opinión, usa el subagente `hook-critic`.
5. **Render.** `clipforge render <job>` y luego `clipforge review`.
6. **Reporte** a Carlo según CLAUDE.md: tabla clip/duración/score/hook/⚠, cuáles publicar primero, ruta de `data/review.html`.

Para cambios posteriores ("el c03 más corto", "subtítulos verdes"): edita el spec y `clipforge render <job> --only <clip>`.
