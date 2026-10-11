#!/usr/bin/env python3
"""
Bazaga NAMUNA (SINTETIK) dalalarni yozadi — botning /stats va kundalik yuborishni sinash uchun.
Telegram ID sifatida berilgan admin ID ishlatiladi (xabarlar faqat sizga boradi):
    python scripts/seed_demo_fields.py <telegram_id> [cache_id]
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.repo import Repo
from app.services.demo_fields import SAMPLE_FIELDS
from engine.suv_engine import Field


def main(uid: int) -> None:
    st = get_settings()
    repo = Repo(st.db_url)
    today = date.today()
    base = date(today.year, 4, 15)
    for s in SAMPLE_FIELDS:
        f = Field(crop=s.crop, soil=s.soil, method=s.method, planting=s.planting(base), area_ha=s.area_ha)
        repo.add_field(uid, f, today - timedelta(days=s.last_irrigation_ago))
    print(f"{len(SAMPLE_FIELDS)} ta namuna dala yozildi (user {uid}). Faol dala — oxirgisi ({SAMPLE_FIELDS[-1].id}).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(int(sys.argv[1]))
