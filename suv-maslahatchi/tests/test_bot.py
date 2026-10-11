from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Location, Message, Update, User

from app.bot import keyboards as kb
from app.bot import scheduler, service
from app.bot.handlers import build_router
from app.bot.parse import parse_area, parse_date, valid_last_irrigation, valid_planting
from app.core.config import Settings
from app.db.repo import Repo
from app.services.demo_cache import get_cache
from app.services.weather import WeatherClient
from engine.suv_engine import Field

TODAY = date(2025, 7, 10)


def om(today: date) -> dict[str, Any]:
    ds = [today - timedelta(days=60) + timedelta(days=i) for i in range(67)]
    return {"daily": {"time": [d.isoformat() for d in ds], "et0_fao_evapotranspiration": [6.5] * 67,
                      "precipitation_sum": [0.0] * 67}}


def wclient(tmp: Path, ok: bool = True, today: date = TODAY) -> WeatherClient:
    def get(url: str) -> Any:
        if not ok:
            raise OSError("oflayn")
        return om(today)
    return WeatherClient(tmp / "w", getter=get, sleep=lambda s: None, today=lambda: today)


# ---------------------------------------------------------------- parse
def test_parse_date() -> None:
    assert parse_date("15.04.2025", TODAY) == date(2025, 4, 15)
    assert parse_date("15/04/25", TODAY) == date(2025, 4, 15)
    assert parse_date("2025-04-15", TODAY) == date(2025, 4, 15)
    assert parse_date(" Bugun ", TODAY) == TODAY and parse_date("сегодня", TODAY) == TODAY
    assert parse_date("kecha", TODAY) == TODAY - timedelta(days=1)
    assert parse_date("05.07", TODAY) == date(2025, 7, 5)
    assert parse_date("20.12", TODAY) == date(2024, 12, 20)
    assert parse_date("31.02", TODAY) is None and parse_date("salom", TODAY) is None


def test_parse_area_and_validators() -> None:
    assert parse_area("2,5") == 2.5 and parse_area("3 ga") == 3.0 and parse_area("4га") == 4.0
    assert parse_area("0") is None and parse_area("abc") is None
    assert valid_planting(date(2025, 4, 15), TODAY) and not valid_planting(date(2020, 1, 1), TODAY)
    assert valid_last_irrigation(date(2025, 7, 1), date(2025, 4, 15), TODAY)
    assert not valid_last_irrigation(date(2025, 7, 11), date(2025, 4, 15), TODAY)


# ---------------------------------------------------------------- service
def test_service(settings: Settings, tmp_path: Path) -> None:
    repo = Repo(settings.db_url)
    wc = wclient(tmp_path)
    assert "/start" in service.advice_for_user(repo, wc, 1).text
    assert "/start" in service.field_info(repo, 1)
    assert "/start" in service.mark_irrigated(repo, 1, TODAY)
    f = Field(crop="paxta", soil="orta", method="egat", planting=date(2025, 4, 15), area_ha=2)
    fid = repo.add_field(1, f, TODAY - timedelta(days=17))
    rep = service.advice_for_user(repo, wc, 1)
    assert rep.field_id == fid and "SUG‘OR" in rep.text and rep.why and "FAO-56" in rep.why
    assert "Paxta" in service.field_info(repo, 1)
    assert "10.07.2025" in service.mark_irrigated(repo, 1, TODAY)
    assert "SHART EMAS" in service.advice_for_user(repo, wc, 1).text
    # internet yo‘q va zaxira yo‘q → muloyim xato
    off = service.advice_for_user(repo, wclient(tmp_path / "x", ok=False), 1)
    assert "Ob-havo" in off.text and off.why is None
    # zaxira fayl eskirgan → ogohlantirish
    stale = WeatherClient(tmp_path / "w", ttl_s=0, getter=lambda u: (_ for _ in ()).throw(OSError()),
                          sleep=lambda s: None, today=lambda: TODAY)
    assert "eskirgan" in service.advice_for_user(repo, stale, 1).text


def test_demo_reply(real_like_cache: Path) -> None:
    rep = service.demo_reply(get_cache(real_like_cache, "test_2025"), "uz")
    assert "Namuna (sintetik)" in rep.text and "Demo" in rep.text and rep.why


def test_keyboards(real_like_cache: Path) -> None:
    m = kb.choices("uz", "soil", ("yengil", "orta"), hint="soil_hint")
    assert m.inline_keyboard[0][0].callback_data == "soil:yengil"
    assert "sochilib" in m.inline_keyboard[0][0].text
    assert len(kb.advice_kb("uz", None).inline_keyboard[0]) == 1
    assert len(kb.advice_kb("ru", 3).inline_keyboard[0]) == 2
    assert kb.demo_kb([get_cache(real_like_cache, "test_2025")]).inline_keyboard[0][0].callback_data == "demo:test_2025"
    assert kb.location("uz").keyboard[0][0].request_location


# ---------------------------------------------------------------- aiogram oqimi (tarmoqsiz)
class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[TelegramMethod[Any]] = []

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        self.sent.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=len(self.sent), date=datetime.now(UTC),
                           chat=Chat(id=int(method.chat_id), type="private"), text=method.text)
        return True

    async def stream_content(self, *a: Any, **k: Any) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        yield b""

    async def close(self) -> None:
        pass

    def texts(self) -> list[str]:
        return [m.text for m in self.sent if isinstance(m, SendMessage)]


UID = 501
USER = User(id=UID, is_bot=False, first_name="Sinov", language_code="uz")
CHAT = Chat(id=UID, type="private")


class Harness:
    def __init__(self, settings: Settings, tmp: Path) -> None:
        self.session = RecordingSession()
        self.bot = Bot("123:abc", session=self.session)
        self.repo = Repo(settings.db_url)
        real_today = datetime.now().date()
        self.dp = Dispatcher()
        self.dp.include_router(build_router(self.repo, wclient(tmp, today=real_today), settings))
        self.n = 0

    async def text(self, s: str) -> list[str]:
        return await self._feed(message=Message(message_id=self._id(), date=datetime.now(UTC), chat=CHAT,
                                                from_user=USER, text=s))

    async def loc(self, lat: float, lon: float) -> list[str]:
        return await self._feed(message=Message(message_id=self._id(), date=datetime.now(UTC), chat=CHAT,
                                                from_user=USER, location=Location(latitude=lat, longitude=lon)))

    async def press(self, data: str) -> list[str]:
        msg = Message(message_id=self._id(), date=datetime.now(UTC), chat=CHAT, text="…")
        return await self._feed(callback_query=CallbackQuery(id=str(self._id()), from_user=USER,
                                                             chat_instance="c", message=msg, data=data))

    def _id(self) -> int:
        self.n += 1
        return self.n

    async def _feed(self, **kw: Any) -> list[str]:
        before = len(self.session.sent)
        await self.dp.feed_update(self.bot, Update(update_id=self._id(), **kw))
        return [m.text for m in self.session.sent[before:] if isinstance(m, SendMessage)]


async def test_onboarding_and_commands(settings: Settings, tmp_path: Path) -> None:
    h = Harness(settings, tmp_path)
    today = datetime.now().date()
    out = await h.text("/start")
    assert "Assalomu alaykum" in out[0] and "Qaysi ekin" in out[1]
    assert "Tuprog‘ingiz" in (await h.press("crop:paxta"))[0]
    assert any(isinstance(m, EditMessageReplyMarkup) for m in h.session.sent)
    assert any(isinstance(m, AnswerCallbackQuery) for m in h.session.sent)
    assert "Qanday sug‘orasiz" in (await h.press("soil:orta"))[0]
    assert "Ekilgan sana" in (await h.press("method:egat"))[0]
    assert "Tushunmadim" in (await h.text("ertaga"))[0]
    planting = today - timedelta(days=90)
    assert "gektar" in (await h.text(planting.strftime("%d.%m.%Y")))[0]
    assert "Tushunmadim" in (await h.text("-1"))[0]
    assert "joylashuv" in (await h.text("2,5"))[0].lower()
    assert "Oxirgi marta" in (await h.loc(40.5, 68.0))[0]
    assert "Tushunmadim" in (await h.text("01.01.1990"))[0]
    out = await h.text((today - timedelta(days=5)).strftime("%d.%m.%Y"))
    assert "Dala saqlandi" in out[0] and "07:00" in out[0] and len(out) == 2
    row = h.repo.current_field(UID)
    assert row and row.area_ha == 2.5 and row.lat == 40.5 and row.planting == planting

    assert "Paxta" in (await h.text("/maslahat"))[0]
    assert "FAO-56" in (await h.press("why"))[0]
    assert "sug‘orildi" in (await h.press("irrigated"))[0]
    assert "sug‘orildi" in (await h.text("/sugordim"))[0]
    assert "Ekilgan" in (await h.text("/dala"))[0]
    assert "Demo" in (await h.text("/demo"))[0]
    out = await h.press("demo:test_2025")
    assert "Namuna (sintetik)" in out[0]
    assert "make cache" in (await h.press("demo:yoq"))[0]
    assert "Til" in (await h.text("/til"))[0]
    assert "русский" in (await h.press("lang:ru"))[0]
    assert "Команды" in (await h.text("salom"))[0]
    assert await h.text("/stats") == []            # admin emas


async def test_default_location_and_demo_no_cache(settings: Settings, tmp_path: Path) -> None:
    empty = settings.model_copy(update={"cache_dir": tmp_path / "bo‘sh", "allow_synthetic": False})
    h = Harness(empty, tmp_path)
    assert "make cache" in (await h.text("/demo"))[0]
    await h.text("/start")
    await h.press("crop:bugdoy")
    await h.press("soil:ogir")
    await h.press("method:tomchi")
    await h.text((datetime.now().date() - timedelta(days=30)).strftime("%d.%m.%Y"))
    await h.text("1")
    await h.text("📍 Jizzax (standart)")
    await h.text("bugun")
    row = h.repo.current_field(UID)
    assert row and (row.lat, row.lon) == (40.12, 67.84)


async def test_admin_stats(settings: Settings, tmp_path: Path) -> None:
    h = Harness(settings.model_copy(update={"admin_ids": [UID]}), tmp_path)
    assert "Foydalanuvchilar" in (await h.text("/stats"))[0]


async def test_send_daily(settings: Settings, tmp_path: Path) -> None:
    session = RecordingSession()
    bot = Bot("123:abc", session=session)
    repo = Repo(settings.db_url)
    f = Field(crop="paxta", soil="orta", method="egat", planting=date(2025, 4, 15))
    repo.add_field(11, f, TODAY - timedelta(days=3))
    repo.add_field(12, f, TODAY - timedelta(days=12))
    assert await scheduler.send_daily(bot, repo, wclient(tmp_path)) == 2
    assert len(session.texts()) == 2
    sch = scheduler.make_scheduler(bot, repo, wclient(tmp_path), settings)
    job = sch.get_job("daily_advice")
    assert job and "hour='7'" in str(job.trigger)


async def test_send_daily_survives_errors(settings: Settings, tmp_path: Path) -> None:
    class Boom(RecordingSession):
        async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
            raise RuntimeError("telegram xato")
    repo = Repo(settings.db_url)
    repo.add_field(11, Field(crop="paxta", soil="orta", method="egat", planting=date(2025, 4, 15)), None)
    assert await scheduler.send_daily(Bot("123:abc", session=Boom()), repo, wclient(tmp_path)) == 0


@pytest.mark.parametrize("token", [""])
def test_main_requires_token(token: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.bot import main
    monkeypatch.setattr(main, "get_settings", lambda: Settings(bot_token=token))
    with pytest.raises(SystemExit, match="BOT_TOKEN"):
        asyncio.run(main.run())
