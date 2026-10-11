"""Botni ishga tushirish: python -m app.bot.main  (make bot)."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.core.config import get_settings
from app.db.repo import Repo
from app.services.weather import WeatherClient

from .handlers import build_router
from .scheduler import make_scheduler

COMMANDS = [("maslahat", "Bugungi maslahat"), ("sugordim", "Bugun sug‘ordim"), ("dala", "Dala ma’lumotlari"),
            ("demo", "Demo (arxiv ob-havo)"), ("til", "Til / Язык"), ("start", "Yangi dala")]


async def run() -> None:
    st = get_settings()
    if not st.bot_token:
        sys.exit("BOT_TOKEN yo‘q: .env.example dan nusxa olib, .env ga tokenni yozing.")
    repo = Repo(st.db_url)
    wc = WeatherClient(st.weather_dir, ttl_s=st.weather_ttl_s)
    bot = Bot(st.bot_token)
    dp = Dispatcher()
    dp.include_router(build_router(repo, wc, st))
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    sch = make_scheduler(bot, repo, wc, st)
    sch.start()
    try:
        await dp.start_polling(bot)
    finally:
        sch.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
