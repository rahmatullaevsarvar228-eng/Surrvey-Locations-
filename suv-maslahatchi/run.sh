#!/usr/bin/env bash
# Sahna demosi: ./run.sh  → brauzerda http://127.0.0.1:8000/?stage=1
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || make setup
ls data/cache/*.json >/dev/null 2>&1 || echo "⚠️  data/cache bo‘sh — internetli kompyuterda 'make cache' ni ishga tushiring."
[ -f web/dist/index.html ] || make web-build
( sleep 2; command -v xdg-open >/dev/null && xdg-open "http://127.0.0.1:8000/?stage=1" || \
  command -v open >/dev/null && open "http://127.0.0.1:8000/?stage=1" ) >/dev/null 2>&1 &
exec .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000
