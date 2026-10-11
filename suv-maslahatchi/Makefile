PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup test lint bot api web web-build demo cache qr clean

setup:            ## Python venv + npm paketlar
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements-dev.txt
	cd web && npm ci
	@test -f .env || (cp .env.example .env && echo ".env yaratildi — BOT_TOKEN ni yozing")

lint:
	$(BIN)/ruff check .
	$(BIN)/mypy --strict engine
	cd web && npx tsc -b

test: lint        ## ruff + mypy (engine) + pytest (engine ≥ 90%)
	$(BIN)/pytest --cov=engine --cov=app --cov-report=term-missing --cov-fail-under=90

bot:              ## Telegram bot (internet kerak)
	$(BIN)/python -m app.bot.main

api:              ## faqat API (dev)
	$(BIN)/uvicorn app.api.main:app --reload --port 8000

web:              ## Vite dev server (API bilan: boshqa oynada make api)
	cd web && npm run dev

web-build:
	cd web && npm run build

demo: web-build   ## Sahna: API + yig‘ilgan veb, oflayn → http://127.0.0.1:8000/?stage=1
	$(BIN)/uvicorn app.api.main:app --host 127.0.0.1 --port 8000

cache:            ## Haqiqiy Open-Meteo arxivini data/cache ga yozish (internet kerak)
	$(BIN)/python scripts/build_demo_cache.py

qr:               ## make qr BOT=SuvMaslahatchiBot
	$(BIN)/python scripts/make_qr.py $(BOT)

clean:
	rm -rf web/dist .pytest_cache .mypy_cache .ruff_cache .coverage
