"""Foydalanuvchi kiritgan matnni tahlil qilish (sof funksiyalar)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

TODAY_WORDS = {"bugun", "сегодня", "today"}
YESTERDAY_WORDS = {"kecha", "вчера", "yesterday"}


def parse_date(text: str, today: date) -> date | None:
    s = text.strip().lower()
    if s in TODAY_WORDS:
        return today
    if s in YESTERDAY_WORDS:
        return today - timedelta(days=1)
    s = re.sub(r"[/\-\s]", ".", s)
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", s)
    if m:
        try:
            d = date(today.year, int(m[2]), int(m[1]))
        except ValueError:
            return None
        return d if d <= today else d.replace(year=today.year - 1)
    return None


def parse_area(text: str) -> float | None:
    s = text.strip().replace(",", ".").lower().removesuffix("ga").removesuffix("га").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    return v if 0 < v <= 10_000 else None


def valid_planting(d: date, today: date) -> bool:
    return today - timedelta(days=400) <= d <= today + timedelta(days=60)


def valid_last_irrigation(d: date, planting: date, today: date) -> bool:
    return d <= today and d >= planting - timedelta(days=30)
