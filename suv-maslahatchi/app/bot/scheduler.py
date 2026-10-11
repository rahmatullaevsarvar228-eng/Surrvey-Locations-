"""Har kuni soat 07:00 (Asia/Tashkent) har bir dala uchun maslahat yuborish (TZ 3.4: qaror paytida turtki)."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import Settings
from app.db.repo import Repo
from app.services.weather import WeatherClient

from . import keyboards as kb
from . import service

log = logging.getLogger(__name__)


async def send_daily(bot: Bot, repo: Repo, wc: WeatherClient) -> int:
    sent = 0
    rows = repo.all_fields()
    per_user: dict[int, int] = {}
    for row in rows:
        per_user[row.user_id] = per_user.get(row.user_id, 0) + 1
    for row in rows:
        try:
            lang = repo.lang(row.user_id)
            rep = await asyncio.to_thread(service.advice_for_field, repo, wc, row, lang, per_user[row.user_id] > 1)
            markup = kb.advice_kb(lang, rep.field_id) if rep.why else None
            await bot.send_message(row.user_id, rep.text, reply_markup=markup)
            sent += 1
        except Exception:   # bitta foydalanuvchi xatosi qolganlarni to‘xtatmasin
            log.exception("kundalik xabar yuborilmadi: user=%s field=%s", row.user_id, row.id)
        await asyncio.sleep(0.05)   # Telegram limitlari
    log.info("kundalik maslahat: %s ta yuborildi", sent)
    return sent


def make_scheduler(bot: Bot, repo: Repo, wc: WeatherClient, st: Settings) -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone=st.tz)
    sch.add_job(send_daily, CronTrigger(hour=st.advice_hour, minute=0, timezone=st.tz),
                args=[bot, repo, wc], id="daily_advice", misfire_grace_time=3600, coalesce=True)
    return sch
