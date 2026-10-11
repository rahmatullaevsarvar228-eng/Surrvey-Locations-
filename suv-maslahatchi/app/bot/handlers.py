"""aiogram 3 routerlari (TZ 5.1): onboarding (faqat tugmalar), maslahat, haftalik reja, dalalar, demo, til."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.core.config import Settings
from app.db.repo import Repo
from app.services.demo_cache import CacheMissing, DemoCache, get_cache, list_caches
from app.services.texts import t
from app.services.weather import WeatherClient
from engine.suv_engine import CROPS, METHODS, SOILS, Field

from . import calendar as cal
from . import keyboards as kb
from . import service
from .parse import parse_area, parse_date, valid_last_irrigation, valid_planting
from .regions import REGIONS, region_name


class Onboard(StatesGroup):
    location = State()
    crop = State()
    soil = State()
    method = State()
    area = State()
    area_other = State()
    planting = State()
    last = State()


def build_router(repo: Repo, wc: WeatherClient, st: Settings) -> Router:
    r = Router()
    tz = ZoneInfo(st.tz)

    def today() -> date:
        return datetime.now(tz).date()

    def lang_of(uid: int) -> str:
        return repo.lang(uid)

    async def answer(target: Message | CallbackQuery, text: str, markup: Any = None) -> None:
        if isinstance(target, CallbackQuery):
            await target.answer()
            if isinstance(target.message, Message):
                await target.message.answer(text, reply_markup=markup)
        else:
            await target.answer(text, reply_markup=markup)

    async def close_choice(cb: CallbackQuery, value: str) -> None:
        """Tanlangan tugmani olib tashlab, tanlovni matnda qoldiradi."""
        await cb.answer()
        if isinstance(cb.message, Message):
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.answer(t(lang_of(cb.from_user.id), "bot.picked", value=value))

    async def send_advice(target: Message | CallbackQuery, uid: int) -> None:
        rep = await asyncio.to_thread(service.advice_for_user, repo, wc, uid)
        markup = kb.advice_kb(lang_of(uid), rep.field_id) if rep.why else None
        await answer(target, rep.text, markup)

    def cache_or_none(cid: str) -> DemoCache | None:
        try:
            return get_cache(st.cache_dir, cid, st.allow_synthetic)
        except CacheMissing:
            return None

    # ------------------------------------------------------------ onboarding (TZ: ≤ 60 s, tugmalar)
    async def begin(target: Message | CallbackQuery, state: FSMContext, uid: int) -> None:
        lang = lang_of(uid)
        await state.clear()
        await state.set_state(Onboard.location)
        await answer(target, t(lang, "bot.ask_location"), kb.location(lang))

    @r.message(CommandStart())
    async def start(msg: Message, state: FSMContext) -> None:
        uid = msg.chat.id
        repo.ensure_user(uid, "ru" if (msg.from_user and msg.from_user.language_code == "ru") else "uz")
        await msg.answer(t(lang_of(uid), "bot.start"))
        await begin(msg, state, uid)

    async def after_location(target: Message | CallbackQuery, state: FSMContext, uid: int) -> None:
        lang = lang_of(uid)
        await state.set_state(Onboard.crop)
        if isinstance(target, Message):
            await target.answer("👍", reply_markup=kb.REMOVE)
        await answer(target, t(lang, "bot.ask_crop"), kb.choices(lang, "crop", tuple(CROPS)))

    @r.message(Onboard.location, F.location)
    async def on_gps(msg: Message, state: FSMContext) -> None:
        assert msg.location
        await state.update_data(lat=msg.location.latitude, lon=msg.location.longitude, place=None)
        await after_location(msg, state, msg.chat.id)

    @r.message(Onboard.location, F.text)
    async def on_region_request(msg: Message) -> None:
        lang = lang_of(msg.chat.id)
        await msg.answer(t(lang, "bot.pick_region"), reply_markup=kb.regions(lang))

    @r.callback_query(Onboard.location, F.data.startswith("reg:"))
    async def on_region(cb: CallbackQuery, state: FSMContext) -> None:
        key = (cb.data or "").split(":", 1)[1]
        if key not in REGIONS:
            await cb.answer()
            return
        _, _, lat, lon = REGIONS[key]
        await state.update_data(lat=lat, lon=lon, place=key)
        await close_choice(cb, region_name(key, lang_of(cb.from_user.id)))
        await after_location(cb, state, cb.from_user.id)

    async def pick(cb: CallbackQuery, state: FSMContext, key: str, nxt: State, prompt: str, markup: Any) -> None:
        value = (cb.data or "").split(":", 1)[1]
        await state.update_data({key: value})
        await state.set_state(nxt)
        await close_choice(cb, t(lang_of(cb.from_user.id), f"{key}.{value}"))
        await answer(cb, prompt, markup)

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
        lang = lang_of(cb.from_user.id)
        await pick(cb, state, "method", Onboard.area, t(lang, "bot.ask_area"), kb.areas(lang))

    def planting_cal(lang: str, month: date | None = None) -> InlineKeyboardMarkup:
        m = month or today()
        return cal.month_kb("plant", m.year, m.month, lang, today() - timedelta(days=400), today() + timedelta(days=60))

    def last_cal(lang: str, planting: date, month: date | None = None) -> InlineKeyboardMarkup:
        m = month or today()
        return cal.month_kb("last", m.year, m.month, lang, planting - timedelta(days=30), today())

    async def area_done(target: Message | CallbackQuery, state: FSMContext, uid: int, area: float) -> None:
        lang = lang_of(uid)
        await state.update_data(area=area)
        await state.set_state(Onboard.planting)
        await answer(target, t(lang, "bot.ask_planting"), planting_cal(lang))

    @r.callback_query(Onboard.area, F.data.startswith("area:"))
    async def on_area(cb: CallbackQuery, state: FSMContext) -> None:
        value = (cb.data or "").split(":", 1)[1]
        lang = lang_of(cb.from_user.id)
        if value == "other":
            await state.set_state(Onboard.area_other)
            await close_choice(cb, t(lang, "bot.area_other"))
            await answer(cb, t(lang, "bot.ask_area_other"))
            return
        await close_choice(cb, f"{value} ga")
        await area_done(cb, state, cb.from_user.id, float(value))

    @r.message(Onboard.area_other, F.text)
    async def on_area_text(msg: Message, state: FSMContext) -> None:
        a = parse_area(msg.text or "")
        if a is None:
            lang = lang_of(msg.chat.id)
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_area_other"))
            return
        await area_done(msg, state, msg.chat.id, a)

    async def finish(target: Message | CallbackQuery, state: FSMContext, uid: int, last: date) -> None:
        lang = lang_of(uid)
        data = await state.get_data()
        fld = Field(crop=data["crop"], soil=data["soil"], method=data["method"],
                    planting=date.fromisoformat(data["planting"]), area_ha=float(data["area"]),
                    lat=float(data["lat"]), lon=float(data["lon"]))
        repo.add_field(uid, fld, last, place=data.get("place"))
        await state.clear()
        await answer(target, t(lang, "bot.saved", hour=f"{st.advice_hour:02d}"))
        await send_advice(target, uid)

    async def set_planting(target: Message | CallbackQuery, state: FSMContext, uid: int, d: date) -> None:
        lang = lang_of(uid)
        await state.update_data(planting=d.isoformat())
        await state.set_state(Onboard.last)
        await answer(target, t(lang, "bot.ask_last_irrigation"), last_cal(lang, d))

    @r.callback_query(F.data.startswith("cal:"))
    async def on_calendar(cb: CallbackQuery, state: FSMContext) -> None:
        parsed = cal.parse(cb.data or "")
        uid, lang = cb.from_user.id, lang_of(cb.from_user.id)
        cur = await state.get_state()
        if parsed is None:
            await cb.answer()
            return
        purpose, action, value = parsed
        expected = Onboard.planting.state if purpose == "plant" else Onboard.last.state
        if cur != expected:
            await cb.answer()
            return
        data = await state.get_data()
        planting = date.fromisoformat(data["planting"]) if "planting" in data else today()
        if action == "m":
            y, m = (int(x) for x in value.split("-"))
            first = date(y, m, 1)
            markup = planting_cal(lang, first) if purpose == "plant" else last_cal(lang, planting, first)
            await cb.answer()
            if isinstance(cb.message, Message):
                await cb.message.edit_reply_markup(reply_markup=markup)
            return
        d = date.fromisoformat(value)
        await close_choice(cb, d.strftime("%d.%m.%Y"))
        if purpose == "plant":
            await set_planting(cb, state, uid, d)
        else:
            await finish(cb, state, uid, d)

    # matn bilan kiritish ham qabul qilinadi (kalendar o‘rniga)
    @r.message(Onboard.planting, F.text)
    async def on_planting_text(msg: Message, state: FSMContext) -> None:
        d = parse_date(msg.text or "", today())
        if d is None or not valid_planting(d, today()):
            lang = lang_of(msg.chat.id)
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_planting"),
                             reply_markup=planting_cal(lang))
            return
        await set_planting(msg, state, msg.chat.id, d)

    @r.message(Onboard.last, F.text)
    async def on_last_text(msg: Message, state: FSMContext) -> None:
        planting = date.fromisoformat((await state.get_data())["planting"])
        d = parse_date(msg.text or "", today())
        if d is None or not valid_last_irrigation(d, planting, today()):
            lang = lang_of(msg.chat.id)
            await msg.answer(t(lang, "errors.bad_input") + "\n" + t(lang, "bot.ask_last_irrigation"),
                             reply_markup=last_cal(lang, planting))
            return
        await finish(msg, state, msg.chat.id, d)

    # ------------------------------------------------------------ kundalik buyruqlar
    @r.message(Command("bugun", "maslahat"))
    async def cmd_today(msg: Message) -> None:
        await send_advice(msg, msg.chat.id)

    @r.message(Command("hafta"))
    async def cmd_week(msg: Message) -> None:
        await msg.answer(await asyncio.to_thread(service.week_for_user, repo, wc, msg.chat.id))

    @r.message(Command("sugordim"))
    async def cmd_irrigated(msg: Message) -> None:
        await msg.answer(service.mark_irrigated(repo, msg.chat.id, today()))

    @r.callback_query(F.data.startswith("irr:"))
    async def cb_irrigated(cb: CallbackQuery) -> None:
        fid = int((cb.data or "irr:0").split(":", 1)[1])
        await answer(cb, service.mark_irrigated(repo, cb.from_user.id, today(), fid))

    async def explain(cb: CallbackQuery, kind: str) -> None:
        """why:<field_id> | why:d:<cache_id>, week:… — xabar eskirgan bo‘lsa ham qayta hisoblanadi."""
        uid, lang = cb.from_user.id, lang_of(cb.from_user.id)
        ref = (cb.data or "").split(":", 1)[1]
        if ref.startswith("d:"):
            c = cache_or_none(ref[2:])
            if c is None:
                await answer(cb, t(lang, "errors.no_cache"))
                return
            rep = service.demo_reply(c, lang)
        else:
            row = next((f for f in repo.fields_of(uid) if str(f.id) == ref), None)
            if row is None:
                await answer(cb, t(lang, "errors.no_field"))
                return
            rep = await asyncio.to_thread(service.advice_for_field, repo, wc, row, lang)
        if kind == "why":
            await answer(cb, f"❓ {t(lang, 'advice.why_title')}\n{rep.why}" if rep.why else rep.text)
        else:
            await answer(cb, rep.week or rep.text)

    @r.callback_query(F.data.startswith("why:"))
    async def cb_why(cb: CallbackQuery) -> None:
        await explain(cb, "why")

    @r.callback_query(F.data.startswith("week:"))
    async def cb_week(cb: CallbackQuery) -> None:
        await explain(cb, "week")

    # ------------------------------------------------------------ dalalar
    @r.message(Command("dala"))
    async def cmd_fields(msg: Message) -> None:
        uid, lang = msg.chat.id, lang_of(msg.chat.id)
        rows = repo.fields_of(uid)
        if not rows:
            await msg.answer(t(lang, "errors.no_field"))
            return
        cur = repo.current_field(uid)
        places = [service.field_place(x, lang) for x in rows]
        await msg.answer(service.field_info(repo, uid))
        await msg.answer(t(lang, "bot.fields_title"),
                         reply_markup=kb.fields_kb(lang, rows, cur.id if cur else None, places))

    @r.callback_query(F.data.startswith("fld:"))
    async def cb_field(cb: CallbackQuery, state: FSMContext) -> None:
        uid, lang = cb.from_user.id, lang_of(cb.from_user.id)
        value = (cb.data or "").split(":", 1)[1]
        if value == "new":
            await cb.answer()
            await begin(cb, state, uid)
            return
        if repo.set_active(uid, int(value)):
            row = repo.current_field(uid)
            assert row
            await answer(cb, t(lang, "bot.field_active", n=service.field_no(repo, row),
                               crop=t(lang, f"crop.{row.crop}"), area=f"{row.area_ha:g}"))
        else:
            await answer(cb, t(lang, "errors.no_field"))

    # ------------------------------------------------------------ demo, til, yordam
    @r.message(Command("demo"))
    async def cmd_demo(msg: Message) -> None:
        lang = lang_of(msg.chat.id)
        caches = list_caches(st.cache_dir, st.allow_synthetic)
        if not caches:
            await msg.answer(t(lang, "errors.no_cache"))
            return
        await msg.answer(t(lang, "bot.demo_pick"), reply_markup=kb.demo_kb(caches))

    @r.callback_query(F.data.startswith("demo:"))
    async def cb_demo(cb: CallbackQuery) -> None:
        lang = lang_of(cb.from_user.id)
        cid = (cb.data or "").split(":", 1)[1]
        c = cache_or_none(cid)
        if c is None:
            await answer(cb, t(lang, "errors.no_cache"))
            return
        rep = service.demo_reply(c, lang)
        await answer(cb, rep.text, kb.advice_kb(lang, None, demo=cid))

    @r.message(Command("til"))
    async def cmd_lang(msg: Message) -> None:
        await msg.answer("Til / Язык", reply_markup=kb.lang_kb())

    @r.callback_query(F.data.startswith("lang:"))
    async def cb_lang(cb: CallbackQuery) -> None:
        lang = (cb.data or "lang:uz").split(":", 1)[1]
        repo.set_lang(cb.from_user.id, lang)
        await answer(cb, t(lang, "bot.lang_set") + "\n\n" + t(lang, "bot.menu"))

    @r.message(Command("stats"))
    async def cmd_stats(msg: Message) -> None:
        if msg.from_user and msg.from_user.id in st.admin_ids:
            u, f, e = repo.stats()
            await msg.answer(t(lang_of(msg.chat.id), "bot.admin_stats", users=u, fields=f, events=e))

    @r.message(Command("yordam", "help"))
    async def cmd_help(msg: Message) -> None:
        lang = lang_of(msg.chat.id)
        await msg.answer(t(lang, "bot.help", hour=f"{st.advice_hour:02d}") + "\n\n" + t(lang, "bot.menu"))

    @r.message()
    async def fallback(msg: Message) -> None:
        await msg.answer(t(lang_of(msg.chat.id), "bot.menu"))

    return r
