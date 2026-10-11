#!/usr/bin/env python3
"""
Sahna demosi uchun HAQIQIY ob-havo keshini yig‘adi (Open-Meteo Historical Weather API).
Internetli kompyuterda ishga tushiring:  make cache   (yoki: python scripts/build_demo_cache.py)
Natija: data/cache/<id>.json — keyin bu papkani sahna noutbukiga ko‘chiring.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import suv_engine as se

OUT = Path(__file__).resolve().parents[1] / "data" / "cache"

# id, joy, lat, lon, boshlanish, tugash, ekin, namuna ekish sanasi
SCENARIOS: list[tuple[str, str, float, float, str, str, str, str]] = [
    ("jizzax_2025", "Jizzax", 40.12, 67.84, "2025-03-01", "2025-10-31", "paxta", "2025-04-15"),
    ("fargona_2025", "Farg‘ona", 40.39, 71.78, "2025-03-01", "2025-10-31", "paxta", "2025-04-15"),
    ("qarshi_2025", "Qarshi", 38.86, 65.79, "2025-03-01", "2025-10-31", "paxta", "2025-04-10"),
    ("jizzax_2024", "Jizzax", 40.12, 67.84, "2024-03-01", "2024-10-31", "paxta", "2024-04-15"),
    ("jizzax_bugdoy_2025", "Jizzax", 40.12, 67.84, "2024-09-15", "2025-06-30", "bugdoy", "2024-10-10"),
]


def build(only: set[str] | None, retries: int = 4) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for sid, place, lat, lon, start, end, crop, planting in SCENARIOS:
        if only and sid not in only:
            continue
        url = se.archive_url(lat, lon, date.fromisoformat(start), date.fromisoformat(end))
        for attempt in range(retries):
            try:
                js = se._get(url, timeout=60)
                days = se.parse_open_meteo(js)
                break
            except Exception as e:
                print(f"  {sid}: urinish {attempt + 1}/{retries} — {e}", file=sys.stderr)
                time.sleep(2 ** (attempt + 1))
        else:
            failed += 1
            continue
        missing = sum(1 for t, e in zip(js["daily"]["time"], js["daily"]["et0_fao_evapotranspiration"],
                                        strict=True) if e is None)
        doc = {
            "meta": {
                "id": sid, "place": place, "lat": lat, "lon": lon, "start": start, "end": end,
                "crop": crop, "planting": planting,
                "source": "Open-Meteo Historical Weather API (ERA5/ERA5-Land qayta tahlil)",
                "url": url, "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "synthetic": False, "missing_et0_days": missing,
            },
            "daily": js["daily"],
        }
        (OUT / f"{sid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        et0 = sum(d.et0 for d in days)
        print(f"✓ {sid}: {len(days)} kun, ΣET0 = {et0:.0f} mm, bo‘sh ET0 kunlari: {missing}")
    return failed


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="faqat shu id lar (bo‘sh = hammasi)")
    sys.exit(1 if build(set(ap.parse_args().ids) or None) else 0)
