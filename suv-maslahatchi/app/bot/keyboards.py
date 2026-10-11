from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.db.models import FieldRow
from app.services.demo_cache import DemoCache
from app.services.texts import t

from .regions import REGIONS, region_name

REMOVE = ReplyKeyboardRemove()
AREAS = ("1", "5", "10", "50")


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def choices(lang: str, group: str, keys: tuple[str, ...], hint: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    for k in keys:
        label = t(lang, f"{group}.{k}")
        if hint:
            label = f"{label} — {t(lang, f'{hint}.{k}')}"
        rows.append([_btn(label, f"{group}:{k}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def location(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text=t(lang, "bot.send_location"), request_location=True)],
        [KeyboardButton(text=t(lang, "bot.pick_region_btn"))],
    ])


def regions(lang: str) -> InlineKeyboardMarkup:
    keys = list(REGIONS)
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(region_name(k, lang), f"reg:{k}") for k in keys[i:i + 2]] for i in range(0, len(keys), 2)])


def areas(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(a, f"area:{a}") for a in AREAS], [_btn(t(lang, "bot.area_other"), "area:other")]])


def advice_kb(lang: str, field_id: int | None, demo: str | None = None) -> InlineKeyboardMarkup:
    """TZ: [✅ Sug‘ordim] [❓ Nega?] [📅 7 kunlik reja]. Callback dala/kesh id sini o‘zida saqlaydi."""
    ref = f"d:{demo}" if demo else str(field_id)
    row = []
    if field_id is not None and not demo:
        row.append(_btn(t(lang, "bot.irrigated_btn"), f"irr:{field_id}"))
    row.append(_btn(t(lang, "bot.why_btn"), f"why:{ref}"))
    return InlineKeyboardMarkup(inline_keyboard=[row, [_btn(t(lang, "bot.week_btn"), f"week:{ref}")]])


def fields_kb(lang: str, rows: list[FieldRow], active_id: int | None, places: list[str]) -> InlineKeyboardMarkup:
    kb = [[_btn(t(lang, "bot.field_btn", mark="✔ " if r.id == active_id else "", n=i + 1,
                 crop=t(lang, f"crop.{r.crop}"), area=f"{r.area_ha:g}", place=places[i]), f"fld:{r.id}")]
          for i, r in enumerate(rows)]
    kb.append([_btn(t(lang, "bot.new_field"), "fld:new")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def demo_kb(caches: list[DemoCache]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(f"{c.meta.place} · {c.meta.start.year}", f"demo:{c.meta.id}")] for c in caches])


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("O‘zbekcha", "lang:uz"), _btn("Русский", "lang:ru")]])
