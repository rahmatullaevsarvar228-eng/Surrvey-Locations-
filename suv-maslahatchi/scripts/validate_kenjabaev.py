#!/usr/bin/env python3
"""
TZ §6 validatsiyasini qayta hisoblash: mavsum ET0 = 863 mm ga normallashtiriladi (Kenjabaev va boshq., 2020,
Farg‘ona), mahalliy Kc bilan potensial ETc hisoblanadi va dala o‘lchovi (ETc 560 ± 50 mm) bilan solishtiriladi.
Mavsum shakli: keshdagi haqiqiy arxiv (bo‘lsa) yoki sintetik test fayli.
    python scripts/validate_kenjabaev.py [cache_id]
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.demo_cache import get_cache
from engine import suv_engine as se

ET0_MEASURED, ETC_MEASURED, ETC_SD = 863.0, 560.0, 50.0


def main(cache_id: str) -> None:
    st = get_settings()
    c = get_cache(st.cache_dir, cache_id, allow_synthetic=True)
    print(f"Mavsum shakli: {c.meta.place} ({c.meta.source})")
    for shift in (-5, 0, 10):
        planting = c.meta.planting + timedelta(days=shift)
        f = se.Field(crop="paxta", soil="orta", method="egat", planting=planting)
        win = c.window(planting, planting + timedelta(days=se.season_length("paxta") - 1))
        full = len(win) == se.season_length("paxta")
        k = ET0_MEASURED / sum(d.et0 for d in win)
        etc = se.potential_etc(f, [se.Day(d.date, d.et0 * k) for d in win])
        print(f"  ekish {planting}: {len(win)} kun, potensial ETc = {etc:.0f} mm "
              f"(ETc/ET0 = {etc / ET0_MEASURED:.2f}); o‘lchangan {ETC_MEASURED:.0f} ± {ETC_SD:.0f} mm "
              f"→ model {100 * (etc / ETC_MEASURED - 1):+.0f}%"
              + ("" if full else "  ⚠ mavsum to‘liq emas — natija ishonchsiz"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sintetik_2025")
