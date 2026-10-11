"""aiogram 3 routerlari: onboarding (FSM), maslahat, sug‘orish yozuvi, demo, til."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.config import Settings
from app.db.repo import Repo
from app.services.demo_cache import CacheMissing, get_cache, list_caches
from app.services.texts import t
from app.services.weather import WeatherClient
from engine.suv_engine import CROPS, METHODS, SOILS, Field

from . import keyboards as kb
from . import service
from .parse import parse_area, parse_date, valid_last_irrigation, valid_planting

DEFAULT_LAT, DEFAULT_LON = 40.12, 67.84     # Jizzax


class Onboard(StatesGroup):
    crop = State()
    soil = State()
    method = State()
    planting = State()
    area = State()
    location = State()
    last = State()


def build_router(repo: Repo, wc: WeatherClient, st: Settings) -> Router:
    r = Router()
    tz = ZoneInfo(st.tz)

    def today() -> date:
        from datetime import datetime
        return datetime.now(tz).date()

    def lang_of(uid: int) -> str:
        return repo.lang(uid)

    async def send_reply(msg: Message, state: FSMContext, rep: service.Reply, lang: str) -> None:
        await state.update_data(last_why=rep.why)
        markup = kb.advice_kb(lang, rep.field_id) if rep.why else None
        await msg.answer(rep.text, reply_markup=markup)

    # ------------------------------------------------------------ onboarding
    @r.message(CommandStart())
    async def start(msg: Message, state: FSMContext) -> None:
        uid = msg.from_user.id if msg.from_user else 0
        repo.ensure_user(uid, "ru" if (msg.from_user and msg.from_user.language_code == "ru") else "uz")
        lang = lang_of(uid)
        await state.clear()
        await state.set_state(Onboard.crop)
        await msg.answer(t(lang, "bot.start"))
        await msg.answer(t(lang, "bot.ask_crop"), reply_markup=kb.choices(lang, "crop", tuple(CROPS)))

    async def pick(cb: CallbackQuery, state: FSMContext, key: str, nxt: State, prompt: str,
                   markup: Any = None) -> None:
        value = (cb.data or "").split(":", 1)[1]
        await state.update_data({key: value})
        await state.set_state(nxt)
        await cb.answer()
        if isinstance(cb.message, Message):
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.answer(prompt, reply_markup=markup)

    @r.callback_query(Onboard.crop, F.data.startswith("crop:"))
    async def on_crop(cb: CallbackQuery, state: FSMContext) -> None:
        lang = lang_of(cb.from_user.id)
        await pick(cb, state, "crop", Onboard.soil, t(lang, "bot.ask_soil"),
                   kb.choices(lang, "soil", tuple(SOILS), hint="soil_hint"))

    @r.callback_query(Onboard.soil, F.data.startswith("soil:"))
    async def on_soil(cb: CallbackQuery, state: FSMContext) -> None:
        lang = lang_of(cb.from_user.id)
        await pick(cb, state, "soil", Onboard.method, t(lang, "bot.ask_method"),
                   kb.choices(lang, "method", tuple(METHODS)))

    @r.callback_query(Onboard.method, F.data.startswith("method:"))
    async def on_method(cb: CallbackQuery, state: FSMContext) -> None:
        await pick(cb, state, "method", Onboard.planting, t(lang_of(cb.from_user.id), "bot.ask_planting"))

    @r.message(Onboard.planting, F.text)
    async def on_planting(msg: Message, state: FSMContext) -> None:
        lang = lang_of(msg.chat.id)
        d = parse_date(msg.text or "", today())
        if d is None or not valid_planting(d, today()):
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_planting"))
            return
        await state.update_data(planting=d.isoformat())
        await state.set_state(Onboard.area)
        await msg.answer(t(lang, "bot.ask_area"))

    @r.message(Onboard.area, F.text)
    async def on_area(msg: Message, state: FSMContext) -> None:
        lang = lang_of(msg.chat.id)
        a = parse_area(msg.text or "")
        if a is None:
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_area"))
            return
        await state.update_data(area=a)
        await state.set_state(Onboard.location)
        await msg.answer(t(lang, "bot.ask_location"), reply_markup=kb.location(lang))

    async def got_location(msg: Message, state: FSMContext, lat: float, lon: float) -> None:
        lang = lang_of(msg.chat.id)
        await state.update_data(lat=lat, lon=lon)
        await state.set_state(Onboard.last)
        await msg.answer(t(lang, "bot.ask_last_irrigation"), reply_markup=kb.today_kb(lang))

    @r.message(Onboard.location, F.location)
    async def on_loc(msg: Message, state: FSMContext) -> None:
        assert msg.location
        await got_location(msg, state, msg.location.latitude, msg.location.longitude)

    @r.message(Onboard.location, F.text)
    async def on_loc_default(msg: Message, state: FSMContext) -> None:
        await got_location(msg, state, DEFAULT_LAT, DEFAULT_LON)

    @r.message(Onboard.last, F.text)
    async def on_last(msg: Message, state: FSMContext) -> None:
        uid, lang = msg.chat.id, lang_of(msg.chat.id)
        data = await state.get_data()
        planting = date.fromisoformat(data["planting"])
        d = parse_date(msg.text or "", today())
        if d is None or not valid_last_irrigation(d, planting, today()):
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_last_irrigation"))
            return
        fld = Field(crop=data["crop"], soil=data["soil"], method=data["method"], planting=planting,
                    area_ha=float(data["area"]), lat=float(data["lat"]), lon=float(data["lon"]))
        repo.add_field(uid, fld, d)
        await state.clear()
        await msg.answer(t(lang, "bot.saved", hour=f"{st.advice_hour:02d}"), reply_markup=kb.REMOVE)
        rep = await asyncio.to_thread(service.advice_for_user, repo, wc, uid)
        await send_reply(msg, state, rep, lang)

    # ------------------------------------------------------------ kundalik buyruqlar
    @r.message(Command("maslahat"))
    async def cmd_advice(msg: Message, state: FSMContext) -> None:
        rep = await asyncio.to_thread(service.advice_for_user, repo, wc, msg.chat.id)
        await send_reply(msg, state, rep, lang_of(msg.chat.id))

    @r.message(Command("sugordim"))
    async def cmd_irrigated(msg: Message) -> None:
        await msg.answer(service.mark_irrigated(repo, msg.chat.id, today()))

    @r.callback_query(F.data == "irrigated")
    async def cb_irrigated(cb: CallbackQuery) -> None:
        await cb.answer()
        if isinstance(cb.message, Message):
            await cb.message.answer(service.mark_irrigated(repo, cb.from_user.id, today()))

    @r.callback_query(F.data == "why")
    async def cb_why(cb: CallbackQuery, state: FSMContext) -> None:
        why = (await state.get_data()).get("last_why")
        await cb.answer()
        if isinstance(cb.message, Message):
            lang = lang_of(cb.from_user.id)
            await cb.message.answer(f"❓ {t(lang, 'advice.why_title')}\n{why}" if why else t(lang, "errors.no_field"))

    @r.message(Command("dala"))
    async def cmd_field(msg: Message) -> None:
        await msg.answer(service.field_info(repo, msg.chat.id))

    @r.message(Command("demo"))
    async def cmd_demo(msg: Message) -> None:
        lang = lang_of(msg.chat.id)
        caches = list_caches(st.cache_dir, st.allow_synthetic)
        if not caches:
            await msg.answer(t(lang, "errors.no_cache"))
            return
        await msg.answer(t(lang, "bot.demo_pick"), reply_markup=kb.demo_kb(caches))

    @r.callback_query(F.data.startswith("demo:"))
    async def cb_demo(cb: CallbackQuery, state: FSMContext) -> None:
        lang = lang_of(cb.from_user.id)
        await cb.answer()
        if not isinstance(cb.message, Message):
            return
        try:
            cache = get_cache(st.cache_dir, (cb.data or "").split(":", 1)[1], st.allow_synthetic)
        except CacheMissing:
            await cb.message.answer(t(lang, "errors.no_cache"))
            return
        await send_reply(cb.message, state, service.demo_reply(cache, lang), lang)

    @r.message(Command("til"))
    async def cmd_lang(msg: Message) -> None:
        await msg.answer("Til / Язык", reply_markup=kb.lang_kb())

    @r.callback_query(F.data.startswith("lang:"))
    async def cb_lang(cb: CallbackQuery) -> None:
        lang = (cb.data or "lang:uz").split(":", 1)[1]
        repo.set_lang(cb.from_user.id, lang)
        await cb.answer()
        if isinstance(cb.message, Message):
            await cb.message.answer(t(lang, "bot.lang_set") + "\n\n" + t(lang, "bot.menu"))

    @r.message(Command("stats"))
    async def cmd_stats(msg: Message) -> None:
        if msg.from_user and msg.from_user.id in st.admin_ids:
            u, f, e = repo.stats()
            await msg.answer(t(lang_of(msg.chat.id), "bot.admin_stats", users=u, fields=f, events=e))

    @r.message(Command("help"))
    @r.message()
    async def fallback(msg: Message) -> None:
        await msg.answer(t(lang_of(msg.chat.id), "bot.menu"))

    return r
