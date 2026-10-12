#!/usr/bin/env bash
# Levanta la API (puerto 8000) y el dashboard (puerto 3000). Ctrl+C detiene ambos.
# Uso: ./scripts/dev.sh          → sólo en esta PC
#      ./scripts/dev.sh --lan    → también accesible desde tu celular en la misma red Wi-Fi
set -euo pipefail
cd "$(dirname "$0")/.."

HOST=127.0.0.1
API_URL=http://localhost:8000
if [[ "${1:-}" == "--lan" ]]; then
  HOST=0.0.0.0
  IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo localhost)
  API_URL="http://${IP}:8000"
  echo "Desde el celular abre: http://${IP}:3000"
fi

[[ -d dashboard/node_modules ]] || (cd dashboard && npm install)

clipforge serve --host "$HOST" --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd dashboard
NEXT_PUBLIC_API_URL="$API_URL" npx next dev -H "$HOST" -p 3000
