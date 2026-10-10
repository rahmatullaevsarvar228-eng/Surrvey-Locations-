#!/usr/bin/env bash
# Virtual Double-Track — bitta buyruq bilan ishga tushirish (internetsiz).
# Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8000}"

python3 -c "import ortools, fastapi, uvicorn, pydantic" 2>/dev/null || {
  echo "Python kutubxonalari topilmadi. Bir marta (internet bilan) o'rnating:"
  echo "  pip install -r requirements.txt"; exit 1; }

# Frontend: tayyor build (frontend/dist) repoda saqlanadi; node bo'lsa va build yo'q bo'lsa — yig'amiz.
if [ ! -f frontend/dist/index.html ]; then
  if command -v npm >/dev/null; then (cd frontend && npm install && npm run build); else
    echo "frontend/dist topilmadi va npm yo'q"; exit 1; fi
fi

# Kesh: yo'q bo'lsa tez (qisqa) hisob bilan yaratamiz; to'liq kesh: python3 scripts/precompute.py
if [ ! -f data/cache/oddiy.json ]; then
  echo "Kesh yo'q — qisqa hisob (har biri 10 s)..."
  python3 scripts/precompute.py --time-limit 10 --skip-investment
fi
mkdir -p frontend/dist/cache && cp data/cache/*.json frontend/dist/cache/ 2>/dev/null || true

echo "Virtual Double-Track: http://localhost:${PORT}"
( sleep 2; command -v xdg-open >/dev/null && xdg-open "http://localhost:${PORT}" >/dev/null 2>&1 || \
  command -v open >/dev/null && open "http://localhost:${PORT}" >/dev/null 2>&1 || true ) &
exec python3 -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT"
