#!/usr/bin/env python3
"""
SINTETIK (sun’iy) ob-havo — faqat avtomatik testlar va internetsiz UI tekshiruvi uchun.
Haqiqiy kuzatuv EMAS: silliq sinus egri chizig‘i + qo‘lda qo‘yilgan bir nechta yomg‘ir kuni.
Fayl tests/fixtures/ ga yoziladi; ilova uni faqat SUV_ALLOW_SYNTHETIC=1 bilan va qizil belgi bilan ko‘rsatadi.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sintetik_2025.json"
START, END = date(2025, 3, 1), date(2025, 10, 31)
RAIN_DAYS = {"2025-03-12": 8.0, "2025-03-28": 12.0, "2025-04-09": 6.0, "2025-04-22": 15.0,
             "2025-05-06": 4.0, "2025-05-19": 9.0, "2025-06-14": 3.0, "2025-09-25": 6.0,
             "2025-10-12": 10.0}


def main() -> None:
    n = (END - START).days + 1
    times, et0, rain = [], [], []
    for i in range(n):
        d = START + timedelta(days=i)
        doy = d.timetuple().tm_yday
        # sinus: ~1.6 mm (mart) … ~7.6 mm (iyul), haftalik kichik tebranish
        val = 4.6 + 3.0 * math.sin(2 * math.pi * (doy - 105) / 365) + 0.4 * math.sin(i * 0.9)
        times.append(d.isoformat())
        et0.append(round(max(0.5, val), 2))
        rain.append(RAIN_DAYS.get(d.isoformat(), 0.0))
    doc = {"meta": {"id": "sintetik_2025", "place": "SINTETIK (sinov)", "lat": 40.12, "lon": 67.84,
                    "start": START.isoformat(), "end": END.isoformat(), "crop": "paxta",
                    "planting": "2025-04-15", "source": "SINTETIK — haqiqiy ob-havo emas",
                    "fetched_at": "—", "synthetic": True},
           "daily": {"time": times, "et0_fao_evapotranspiration": et0, "precipitation_sum": rain}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"yozildi: {OUT}")


if __name__ == "__main__":
    main()
