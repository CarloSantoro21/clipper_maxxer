# Contexto del proyecto

Resumen de las decisiones tomadas al diseñar clipper_maxxer (octubre 2026), para que cualquier sesión nueva de Claude Code arranque sabiendo el porqué y no sólo el qué.

## Objetivo
Ganar **al menos 500 USD/mes** publicando clips verticales en TikTok, Instagram Reels y YouTube Shorts. Si no se ve camino a esa cifra, se deja.

**Regla de corte:** 30 días publicando 3–5 clips diarios en 2–3 campañas que paguen 1–3 USD por 1,000 vistas. Si al día 30 no vas camino a ~100k vistas semanales, se corta o se cambia de enfoque.

## De dónde sale el dinero
- **Campañas de clipping (fuente principal).** Marketplaces como Whop Content Rewards y Vyro. Una marca o creador publica una campaña con material autorizado, reglas y una tarifa por 1,000 vistas verificadas. Publicas desde tus cuentas, mandas el link y te pagan por vistas. Whop promedia ~1 USD/1K (rango 0.20–6), Vyro ~3 USD/1K. No hace falta tener audiencia propia. El presupuesto de cada campaña se reparte por orden de llegada y se puede agotar.
- **Pagos de las plataformas (secundario).** TikTok Creator Rewards: ~0.15–0.50 USD/1K en México, pide 10k seguidores, 100k vistas en 30 días y videos de más de 60 s (las fuentes no coinciden sobre si ya está disponible en México). YouTube Shorts: ~0.03–0.07 USD/1K. Instagram Reels: prácticamente nada.
- **Cuenta:** 500 USD/mes ≈ 500k vistas verificadas al mes en campañas de ~1 USD/1K (unas 17k diarias). La mayoría de los clips sacan pocas vistas y unos pocos hacen casi todo el ingreso, así que importa el volumen.

## Decisiones
- **Sólo material con permiso:** campañas, contenido propio o licencia libre. Nada de clipear YouTubers al azar (strikes de copyright y castigo por contenido reciclado). Transformar el video ayuda contra esa penalización, pero no da derechos sobre el material.
- **Whop es semiautomático.** Elegir campañas: manual, ~10 min por semana; no se hace scraping del dashboard de Whop (viola sus términos). Leer el brief: automático con `/campaign`. Mandar los links a Whop: manual al principio.
- **Publicar es manual** por ahora: las APIs de TikTok e Instagram piden aprobación y publicar en masa puede marcar las cuentas.
- **Arquitectura:** Claude decide, el código renderiza. Claude escribe specs JSON; ffmpeg los renderiza de forma determinista. La parte pesada (Whisper, render) corre local, así que la suscripción de Claude sólo se gasta en decisiones.
- **Claude por la suscripción**, con `claude -p` en modo headless (planner, extractor de briefs, chat del dashboard). No se usa API key.
- **Cuentas:** empezar con **2 cuentas de clips + 1 de experimentos** y agregar más cuando el pipeline funcione solo. Nichos considerados:
  - Traducidos (podcasts EN→ES): poca competencia en español. Primero confirmar que la campaña acepte audiencia hispana y traducción.
  - Tecnología y desarrollo personal: muchas campañas de podcasts encajan.
  - Gaming: la mayoría de los estudios permiten usar gameplay.
  - Deportes: sólo con campañas, porque las ligas bajan contenido.
  - Memes: sólo si se generan, no ajenos.
- **Cuenta de experimentos (stories):** historias tipo chisme narradas con TTS sobre Minecraft parkour, cambiando de nicho cada mes. No gana por Whop: su ingreso vendría de Creator Rewards o de patrocinios. El gameplay se graba uno mismo. Ficción original con nombres inventados y etiqueta de contenido IA si la voz suena realista.

## Cómo tienen que ser los clips
Hook en los primeros 1–2 s (la frase más fuerte primero), que se entienda solo, arco con cierre, subtítulos grandes palabra por palabra, un cambio visual cada 2–3 s y 30–60 s de duración (más de 60 sólo si se busca Creator Rewards). Esto ya está en `prompts/plan_clips.md`.

## Estado (al 12 de octubre de 2026)
- Fase 1 y dashboard de la fase 2 terminados, con tests, lint y build en verde.
- **Sin probar en una PC real:** descarga con yt-dlp, transcripción con Whisper y voz con edge-tts. Se escribieron en un entorno sin acceso a esos servicios.
- Falta poner `Montserrat-Black.ttf` en `assets/fonts/` y gameplay propio en `assets/gameplay/`.

## Siguientes pasos
1. Instalar en la PC (README), correr `pytest` y hacer una prueba real de punta a punta con un video propio o de licencia libre.
2. Elegir 1–2 campañas de Whop, registrarlas con `/campaign` y correr `/clip`.
3. Publicar y anotar las vistas en el dashboard; ajustar `prompts/plan_clips.md` según lo que pegue.
4. Pendientes del roadmap en CLAUDE.md: recorte que sigue la cara, traducción EN→ES, subagente de tendencias y métricas.
