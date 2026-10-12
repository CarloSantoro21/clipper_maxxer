# clipper_maxxer

Pipeline local que convierte videos largos en clips verticales para TikTok, Reels y Shorts, y que genera historias narradas sobre gameplay. Lo orquesta **Claude Code** con tu suscripción: tú le hablas, él corre el pipeline, revisa los resultados y te reporta.

```
link de campaña ─► yt-dlp ─► Whisper ─► Claude elige momentos ─► spec JSON ─► ffmpeg ─► review.html ─► tú publicas
premisa ─────────────────────────────► Claude escribe guion ─► voz TTS ─► subtítulos sobre gameplay ─┘
```

**Principio:** Claude decide y el código renderiza. Cada clip es un spec JSON (inicio, fin, hook, estilo de subtítulos, zooms). Para cambiar algo se edita el spec y se vuelve a renderizar; nadie edita video a mano.

El porqué del proyecto (objetivo, cómo pagan las campañas, decisiones y estado) está en [docs/CONTEXTO.md](docs/CONTEXTO.md).

## Instalación (Windows, macOS o Linux)

Requisitos: Python 3.11+, [ffmpeg](https://ffmpeg.org/download.html) en el PATH y [Claude Code](https://claude.com/claude-code) con tu sesión iniciada.

```bash
git clone https://github.com/CarloSantoro21/clipper_maxxer
cd clipper_maxxer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[all]"
cp .env.example .env                                # ajusta CLIPFORGE_DEVICE=cuda si tienes GPU NVIDIA
pytest                                              # debe pasar todo
```

Opcional: copia `Montserrat-Black.ttf` a `assets/fonts/` (ver el README de esa carpeta).

## Uso con Claude Code (lo normal)

Abre `claude` en la carpeta del repo y háblale:

- `/campaign <link o texto del brief de Whop>` → registra la campaña en `campaigns/`
- `/clip <link> <campaña>` → descarga, transcribe, elige momentos, revisa sus propios cortes, renderiza y te reporta
- `/story historias de infidelidad, 3 partes` → guion + voz + subtítulos sobre tu gameplay
- "el c03 que empiece 2 segundos después y con subtítulos verdes" → edita el spec y re-renderiza

Después abre `data/review.html` en el navegador: ahí ves cada clip con su caption y hashtags listos para copiar.

## Dashboard

Interfaz local para revisar, ajustar y aprobar todo sin tocar la terminal. Requiere además Node.js 20+.

```bash
pip install -e ".[dashboard]"     # ya viene incluido en ".[all]"
./scripts/dev.sh                  # Windows: .\scripts\dev.ps1
```

Abre http://localhost:3000. Con `--lan` (Windows: `-Lan`) también lo abres desde tu celular en la misma red Wi-Fi. Úsalo sólo en tu red de casa: el chat puede correr comandos de `clipforge` en tu PC.

| Vista | Para qué |
|---|---|
| **Revisión** | Todos los clips y stories renderizados con su video 9:16. Filtras por estado y cuenta, apruebas, rechazas, marcas como publicado y copias el caption. |
| **Detalle** (clic en un clip) | Ajustas hook, inicio/fin (±0.5 s), encuadre, caption, hashtags y estilo de subtítulos; "Guardar y re-renderizar". Registras link y vistas cuando lo publicas. |
| **Nuevo** | Lanzas clips (link + campaña + cuántos) o una story (premisa + duración + parte) y ves el progreso y el log de cada tarea. |
| **Campañas** | Pegas el brief de Whop, Claude arma el borrador, lo revisas y lo guardas. También editas o pausas campañas. |
| **Chat** | Hablas con el orquestador (Claude Code con este CLAUDE.md). Sabe qué clip tienes abierto: "hazlo 3 s más corto y con otro hook" y lo hace. |

Por debajo: `clipforge serve` levanta la API (FastAPI) en el puerto 8000 y `dashboard/` es la app Next.js. La cola procesa una tarea a la vez.

## Uso directo de la CLI

```bash
clipforge clip "https://youtu.be/XXXXXXXXXXX" -c mi-campana -n 5
clipforge spec <job> c02 --set end=95.2 --set 'hook="Nuevo hook"'
clipforge render <job> --only c02
clipforge story new "Mi esposa me engañó con mi mejor amigo y la perdoné" --seconds 75 --part 1
clipforge review
clipforge status
```

## Reglas

- Sólo se clipea material con permiso: campañas (Whop, Vyro), contenido propio o licencia libre.
- Nada se publica sin que lo revises.
- Sin música comercial añadida; usa la biblioteca de cada plataforma al publicar.
- El gameplay de fondo de las stories lo grabas tú (`assets/gameplay/`).

## Roadmap

- [x] **Fase 1:** CLI modo clip y modo story, validación contra el brief, staging estático
- [x] **Fase 2:** dashboard local (Next.js + FastAPI) con preview, aprobar/rechazar, edición, cola de tareas, campañas y chat con el orquestador
- [ ] **Fase 2:** recorte que sigue la cara del hablante; traducción EN→ES de subtítulos
- [ ] **Fase 3:** subagente de tendencias y métricas por clip que retroalimentan al planner
