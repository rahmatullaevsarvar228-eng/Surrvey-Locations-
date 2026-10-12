# Virtual Double-Track — demo

Bir yo‘lli temir yo‘lning raqamli egizagi (offline rejalashtirish vositasi).
**Mualliflar:** Saynatov Yodgor, Raxmatullayev Sarvar

> Barcha natijalar **sintetik** 12 bekatli uchastka modelida olingan (real ma’lumot emas).

## Ishga tushirish

```bash
pip install -r requirements.txt   # bir marta, internet bilan
./run.sh                          # http://localhost:8000 — internetsiz ishlaydi
```

`frontend/dist` (tayyor build) va `data/cache/*.json` (oldindan hisoblangan kesh) repoda saqlanadi,
shuning uchun sahnada Node.js ham, internet ham kerak emas.

## Tuzilma

| Papka | Mazmuni |
|---|---|
| `engine/` | hisob yadrosi: `model`, `fifo`, `optimizer` (CP-SAT), `validator`, `metrics`, `scenarios`, `investment`, `export`, `run` |
| `api/main.py` | FastAPI: `/api/scenarios`, `/api/scenarios/{nomi}`, `/api/solve`, `/api/simulate_fifo`, `/api/verify`, `/api/razyezd` (faqat kesh) |
| `scripts/precompute.py` | keshni yaratish: `oddiy` / `avariya` / `osish30` (seed 4, 120 s) + razyezd reytingi |
| `scripts/siding_cases.py` | «Yangi razyezd qayerda?»: nazorat guruhi bilan +1 yo‘l reytingi va oldin/keyin jadvallari → `data/cache/razyezd.json` |
| `scripts/experiment.py` | 10 seed tajribasi → `data/experiment.json` |
| `docs/` | jamoa uchun qo‘llanma va sahna nutqi (PDF, UZ / RU) |
| `frontend/` | React + Vite + TypeScript + Plotly.js; i18n: uz (asosiy) / ru / en |
| `tests/` | pytest: validator 0 xato, AI ≤ FIFO, seed 4 «avariya»da FIFO tupigi, keshdagi barcha jadvallar validatordan o‘tadi |

## Ssenariylar (seed 4)

* **oddiy** — 18 poyezd.
* **avariya** — S6–S7 peregoni 03:00–04:30 (180–270-daqiqa, 90 daqiqa) yopiq; FIFO tupikka tushadi (15 poyezd), AI yechim topadi.
* **osish30** — 24 poyezd (+30%).

## Buyruqlar

```bash
python3 -m pytest -q                               # testlar
python3 scripts/precompute.py                      # to‘liq kesh (~12 daq + razyezd reytingi ~20 daq)
python3 scripts/precompute.py --skip-investment    # faqat ssenariylar
python3 scripts/precompute.py --only-investment    # faqat razyezd reytingi
cd frontend && npm install && npm run build        # frontendni qayta yig‘ish
cd frontend && npm run dev                         # ishlab chiqish rejimi (API: ./run.sh)
```

## Ko‘rsatkichlar ta’rifi

* **Kechikish** = haqiqiy yetib kelish − to‘siqsiz yetib kelish.
* **Kutish to‘xtashlari** — oraliq bekatda rejadagidan uzoqroq turish holatlari.
* **Tiklanish vaqti** — hodisa joyidagi peregondan o‘tishi kerak bo‘lgan va to‘siqsiz rejada hodisa
  tugashidan oldin unga kirishi kerak bo‘lgan poyezdlar navbati to‘liq o‘tib bo‘lguncha, hodisa
  tugaganidan keyin o‘tgan daqiqalar. FIFO tupikda — «tiklanmaydi».
* **Poyezd buzilishi** — poyezd oraliq bekatda qo‘shimcha N daqiqa turib qoladi (minimal turish vaqti oshiriladi).

## Narxlar (taxminiy)

Ekranlardagi standart narxlar ochiq manbalardan olingan va «taxminiy» deb belgilangan (`frontend/src/costs.ts`):
1 km yo‘l ≈ 1 mln $ (O‘zbekistonda 0,8–11,4 mln $/km), razyezd ≈ 1,5 km yo‘l + strelka va signalizatsiya
(1,5 mln $ — manba topilmagan, taxmin) ≈ 3 mln $, poyezd-soat turib qolishi 300 $ (adabiyotda 200–1000+ $).
