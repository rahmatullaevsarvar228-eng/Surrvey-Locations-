from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.services.demo_cache import DemoCache
from app.services.texts import t

REMOVE = ReplyKeyboardRemove()


def choices(lang: str, group: str, keys: tuple[str, ...], hint: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    for k in keys:
        label = t(lang, f"{group}.{k}")
        if hint:
            label = f"{label} — {t(lang, f'{hint}.{k}')}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{group}:{k}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def location(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[
        [KeyboardButton(text=t(lang, "bot.send_location"), request_location=True)],
        [KeyboardButton(text=t(lang, "bot.default_location"))],
    ])


def today_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                               keyboard=[[KeyboardButton(text=t(lang, "bot.today_word"))]])


def advice_kb(lang: str, field_id: int | None) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=t(lang, "bot.why_btn"), callback_data="why")]
    if field_id is not None:
        row.append(InlineKeyboardButton(text=t(lang, "bot.irrigated_btn"), callback_data="irrigated"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def demo_kb(caches: list[DemoCache]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{c.meta.place} · {c.meta.start.year}", callback_data=f"demo:{c.meta.id}")]
        for c in caches])


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="O‘zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="Русский", callback_data="lang:ru")]])
