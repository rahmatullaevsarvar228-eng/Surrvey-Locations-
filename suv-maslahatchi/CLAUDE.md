# CLAUDE.md — Suv Maslahatchi

Authors: **Saynatov Yodgor, Raxmatullayev Sarvar**. University startup competition demo.
Full spec (Uzbek): `SUV_MASLAHATCHI_TZ.md`. Read it fully before coding.

## What we build
1. **Telegram bot** (aiogram 3): daily irrigation advice for a farmer's field ("irrigate today ≈ N m³/ha" / "wait K days" / "not needed").
2. **Web app** (FastAPI + React/Vite/TS): stage demo — "Tuproq stakani" (soil-water bucket) season animation, season simulator, water-users-association demand panel, science page.

## Non-negotiable rules
- **All agronomy math goes through `engine/suv_engine.py`** (FAO-56). Never re-implement formulas in the bot or UI. If the engine needs a change, change it there and add a test.
- **Never invent numbers.** No fake farmers, no fake savings %, no fake prices. Demo fields are labelled "Namuna (sintetik)". Cost inputs are empty fields the user fills.
- **Offline-first demo.** The stage laptop may have no internet: `scripts/build_demo_cache.py` stores real Open-Meteo archive weather to `data/cache/*.json`; the web demo and `/demo` read the cache.
- **Uzbek (Latin) first.** All user-facing strings in `i18n/uz.json` (+ `ru.json`). Use proper characters: o‘ g‘ (U+2018), ’ (U+2019). Every screen footer: "Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar".
- **Secrets** only in `.env` (`BOT_TOKEN`, `ADMIN_IDS`). Ship `.env.example`. Never commit `.env`.
- Explain, don't overclaim: every advice has a "Nega?" explanation; the science page states the validation gap honestly (see TZ §6).

## Architecture
```
engine/suv_engine.py      pure functions, no I/O except fetch_* helpers
app/core/config.py        pydantic-settings
app/services/weather.py   Open-Meteo client: grid cache (round lat/lon to 0.1°), 3h TTL, retry w/ backoff, file fallback
app/services/advisor.py   builds Field/Day objects, calls engine
app/db/                   SQLAlchemy 2 + SQLite (users, fields, irrigation_events)
app/bot/                  aiogram 3: routers, FSM onboarding, keyboards, texts, APScheduler 07:00 Asia/Tashkent
app/api/                  FastAPI: /api/advice /api/simulate /api/demand /api/demo
web/                      Vite + React + TypeScript + Tailwind + ECharts; fonts bundled (@fontsource), no CDN
scripts/                  build_demo_cache.py, seed_demo_fields.py, make_qr.py
tests/                    pytest (engine ≥ 90% coverage), API tests with httpx
```

## Commands (create them)
- `make setup` · `make test` (ruff + mypy engine + pytest) · `make bot` · `make web` · `make demo` (API + built web, offline) · `./run.sh` = demo.

## Quality bar (senior)
- Type hints everywhere; `ruff` clean; `mypy --strict` on `engine/`.
- Small modules, pure core, side effects at the edges. Graceful errors in Uzbek ("Ob-havo ma’lumoti hozir olinmadi, 1 soatdan keyin qayta urinamiz").
- Accessibility: contrast ≥ 4.5:1, keyboard focus, `prefers-reduced-motion`.
- Projector mode: `?stage=1` → larger type (base 20px, KPI 64px), hides dev UI.

## Design tokens (web)
Palette (light / dark): `--bg #F4F7F6 / #0E1513`, `--surface #FFFFFF / #16201D`, `--ink #14201C / #E6EEEB`, `--muted #5B6B66 / #93A5A0`,
`--water #1F6FB2 / #5AA2E0` (advice, water), `--soil #8A5A3B / #C08B66` (soil, habit), `--leaf #3C8D4F / #6CC283` (OK state),
`--sun #D9922E / #F0B45A` (heat, ET0), `--alert #C2413A / #F06A62` (stress, loss).
Type: IBM Plex Sans (UI), IBM Plex Mono (numbers, `tabular-nums`). Scale 14/16/20/28/40/64. Radius 10. Shadows only on the bucket card.
Signature visual: **Tuproq stakani** — a vertical soil column: water level = root-zone reserve, dashed line = RAW threshold, roots grow with Zr, drops below the roots = deep percolation (loss, `--alert`).
