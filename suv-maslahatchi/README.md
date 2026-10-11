# Suv Maslahatchi

Sug‘orish maslahatchisi: Telegram bot va sahna demosi (FAO-56 kunlik tuproq-suv balansi).
**Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar**

## Tez boshlash

```bash
make setup          # .venv + npm paketlar, .env.example → .env
make cache          # HAQIQIY ob-havo keshi (Open-Meteo arxivi) → data/cache/*.json  [internet kerak]
make test           # ruff + mypy --strict engine + tsc + pytest (qamrov ≥ 90%)
./run.sh            # sahna demosi, oflayn: http://127.0.0.1:8000/?stage=1
make bot            # Telegram bot (.env da BOT_TOKEN; internet kerak)
```

Dev rejim: `make api` (port 8000) va boshqa oynada `make web` (Vite, port 5173, `/api` proksi).

## Sahna noutbukiga tayyorlash (internetsiz)

1. Internetli kompyuterda: `make setup && make cache && make web-build`.
2. Butun papkani (`data/cache/`, `web/dist/`, `.venv` bilan) noutbukka ko‘chiring yoki shu buyruqlarni noutbukda internet borida bajaring.
3. Sahnada: `./run.sh` → brauzer `?stage=1` (katta shrift, dev elementlar yashirin).
4. Bot QR-kodi: `make qr BOT=<bot_username> && make web-build` → «Ilmiy asos» sahifasida chiqadi.

## Tuzilma

```
engine/suv_engine.py      FAO-56 yadrosi — barcha agronomik hisob faqat shu yerda
app/core/config.py        sozlamalar (.env)
app/services/             weather (Open-Meteo: 0,1° setka, 3 soat TTL, qayta urinish, fayl zaxirasi),
                          demo_cache (oflayn kesh), advisor, texts (i18n), demo_fields (namuna, sintetik)
app/db/                   SQLAlchemy 2 + SQLite: users, fields, irrigation_events
app/bot/                  aiogram 3: onboarding FSM, /maslahat /sugordim /dala /demo /til /stats, 07:00 rejalashtiruvchi
app/api/                  FastAPI: /api/advice /api/simulate /api/demand /api/demo + yig‘ilgan veb
web/                      Vite + React + TS + Tailwind + ECharts (shriftlar @fontsource, CDN yo‘q)
i18n/uz.json, ru.json     foydalanuvchiga ko‘rinadigan barcha matnlar
scripts/                  build_demo_cache.py, make_synthetic_fixture.py, seed_demo_fields.py, make_qr.py
tests/                    pytest: engine, servislar, API, bot oqimi (tarmoqsiz)
```

## Halollik qoidalari

- Ob-havo keshi — faqat haqiqiy Open-Meteo arxivi. `tests/fixtures/sintetik_2025.json` — **sun’iy**, faqat testlar uchun;
  `data/cache` ga tushsa ham yuklanmaydi. UI uni faqat `SUV_ALLOW_SYNTHETIC=1` bilan va qizil «SINTETIK OB-HAVO» belgisi bilan ko‘rsatadi.
- Uyushma panelidagi dalalar — «Namuna (sintetik)». Odatiy jadval va narxlar — foydalanuvchi to‘ldiradigan bo‘sh maydonlar.
- Har bir maslahatda «Nega?» izohi bor; cheklovlar «Ilmiy asos» sahifasida.

## Sozlamalar (.env)

| O‘zgaruvchi | Ma’nosi |
|---|---|
| `BOT_TOKEN` | @BotFather tokeni (hech qachon commit qilinmaydi) |
| `ADMIN_IDS` | vergul bilan Telegram ID lar (`/stats`) |
| `TZ` | `Asia/Tashkent` |
| `SUV_ALLOW_SYNTHETIC` | `1` — sintetik sinov ob-havosini ko‘rsatish (faqat dev) |
| `SUV_DB_URL`, `SUV_CACHE_DIR`, `SUV_WEB_DIST` | yo‘llarni o‘zgartirish (ixtiyoriy) |
