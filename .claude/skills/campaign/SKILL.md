---
name: campaign
description: Registra una campaña de clipping (Whop, Vyro, etc.) a partir de su link o del texto del brief. Úsalo cuando Carlo pegue un brief o diga "agrega esta campaña".
---

# /campaign <link o texto del brief>

1. Si Carlo pegó el texto del brief, úsalo. Si sólo dio un link, intenta leerlo con WebFetch; si la página pide sesión, pídele que pegue el texto.
2. Extrae a `campaigns/<slug>.yaml` siguiendo `campaigns/_plantilla.yaml`:
   - tarifa por 1K vistas, plataformas permitidas, duración mín/máx, idioma
   - links del material autorizado (`source_urls`)
   - hashtags, menciones y textos obligatorios
   - temas/palabras prohibidas y cualquier otra regla en `notes`
   - `account`: pregunta a Carlo en qué cuenta se publica si no es obvio por el nicho
3. Si algo del brief es ambiguo (ej. "no reuploads" sin decir qué cuenta como reupload), anótalo en `notes` y pregúntale.
4. Muestra un resumen de 5 líneas y, si la tarifa o el presupuesto restante se ven bajos frente a otras campañas activas (`clipforge campaign list`), dilo.
