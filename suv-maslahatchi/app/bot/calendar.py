"""Inline kalendar (TZ: sanalar kalendar tugmalari bilan). Callback: cal:<maqsad>:<amal>:<qiymat>."""
from __future__ import annotations

import calendar as _cal
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.texts import load, t

NOOP = "cal:x"


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    m = year * 12 + (month - 1) + delta
    return m // 12, m % 12 + 1


def month_kb(purpose: str, year: int, month: int, lang: str, min_d: date, max_d: date) -> InlineKeyboardMarkup:
    months: list[str] = load(lang)["bot"]["months"]
    days: list[str] = load(lang)["bot"]["weekdays"]
    rows: list[list[InlineKeyboardButton]] = []
    py, pm = _shift(year, month, -1)
    ny, nm = _shift(year, month, 1)
    can_prev = date(year, month, 1) > min_d
    can_next = date(ny, nm, 1) <= max_d
    prev_cb = f"cal:{purpose}:m:{py}-{pm:02d}" if can_prev else NOOP
    next_cb = f"cal:{purpose}:m:{ny}-{nm:02d}" if can_next else NOOP
    rows.append([
        InlineKeyboardButton(text="‹" if can_prev else " ", callback_data=prev_cb),
        InlineKeyboardButton(text=f"{months[month - 1]} {year}", callback_data=NOOP),
        InlineKeyboardButton(text="›" if can_next else " ", callback_data=next_cb),
    ])
    rows.append([InlineKeyboardButton(text=d, callback_data=NOOP) for d in days])
    for week in _cal.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for d in week:
            if d == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data=NOOP))
                continue
            day = date(year, month, d)
            ok = min_d <= day <= max_d
            row.append(InlineKeyboardButton(text=str(d) if ok else "·",
                                            callback_data=f"cal:{purpose}:d:{day.isoformat()}" if ok else NOOP))
        rows.append(row)
    if min_d <= max_d and purpose == "last":
        today_cb = f"cal:{purpose}:d:{max_d.isoformat()}"
        rows.append([InlineKeyboardButton(text=t(lang, "bot.today_word"), callback_data=today_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse(data: str) -> tuple[str, str, str] | None:
    parts = data.split(":", 3)
    if len(parts) != 4 or parts[0] != "cal":
        return None
    return parts[1], parts[2], parts[3]
