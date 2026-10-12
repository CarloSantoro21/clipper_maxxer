---
name: story
description: Crea historias "storytime" narradas con voz TTS y subtítulos sobre gameplay de fondo para la cuenta de experimentos. Úsalo cuando Carlo pida historias, chismes, storytime o contenido original para esa cuenta.
---

# /story <premisa o tema> [segundos] [partes]

1. Verifica que haya gameplay en `assets/gameplay/`. Si está vacío, pide a Carlo que grabe 10–20 minutos de Minecraft parkour (o similar) en 1080p y lo ponga ahí. No uses gameplay descargado de otros creadores.
2. Si Carlo da sólo un tema ("infidelidad", "herencia familiar"), propón 3 premisas con giro y deja que elija, o elige la más fuerte si te dijo que decidas tú.
3. `clipforge story new "<premisa>" --seconds 75` (para serie: `--part 1`, luego una premisa que continúe la historia con `--part 2`).
4. Lee `data/stories/<id>/spec.json`. Revisa que:
   - La primera frase enganche por sí sola.
   - No haya nombres reales, marcas atacadas, ni contenido fuera de normas.
   - El ritmo tenga un giro cada 10–15 s y el final cierre o deje cliffhanger.
   Si hay que mejorar, edita `script`/`hook` en el JSON y corre `clipforge story render <id>`.
5. `clipforge review` y reporta: título, hook, duración y ruta del video. Recuerda la etiqueta de contenido IA si la voz suena realista.

Variables útiles en el spec: `voice` (ej. `es-MX-DaliaNeural`, `es-MX-JorgeNeural`), `rate` (velocidad, "+8%"), `captions.highlight`, `background`.
