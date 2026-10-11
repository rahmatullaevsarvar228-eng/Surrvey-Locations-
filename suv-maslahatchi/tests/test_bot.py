from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageReplyMarkup, SendMessage, TelegramMethod
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

UTC = timezone.utc

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
    assert "/start" in service.week_for_user(repo, wc, 1)
    f = Field(crop="paxta", soil="orta", method="egat", planting=date(2025, 4, 15), area_ha=2)
    fid = repo.add_field(1, f, TODAY - timedelta(days=17))
    rep = service.advice_for_user(repo, wc, 1)
    assert rep.field_id == fid and "SUG‘OR" in rep.text and rep.why and "FAO-56" in rep.why
    assert rep.week and "💧 sug‘oring" in rep.week and "Hafta bo‘yicha jami" in rep.week
    assert service.week_for_user(repo, wc, 1) == rep.week
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
    assert "2025-07-14" in rep.text and rep.week and len(rep.week.splitlines()) >= 8


def test_keyboards(real_like_cache: Path) -> None:
    m = kb.choices("uz", "soil", ("yengil", "orta"), hint="soil_hint")
    assert m.inline_keyboard[0][0].callback_data == "soil:yengil"
    assert "sochilib" in m.inline_keyboard[0][0].text
    assert callbacks(kb.advice_kb("uz", 3)) == ["irr:3", "why:3", "week:3"]
    assert callbacks(kb.advice_kb("ru", None, demo="x")) == ["why:d:x", "week:d:x"]
    assert len(callbacks(kb.regions("uz"))) == 13
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


def last_kb(h: Harness) -> Any:
    for m in reversed(h.session.sent):
        if isinstance(m, SendMessage) and m.reply_markup is not None:
            return m.reply_markup
    raise AssertionError("klaviatura yo‘q")


def callbacks(markup: Any) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def onboard(h: Harness, *, gps: bool = True, area: str = "10") -> list[str]:
    today = datetime.now().date()
    out = await h.text("/start")
    assert "Assalomu alaykum" in out[0] and "Dala qayerda" in out[1]
    if gps:
        out = await h.loc(40.5, 68.0)
    else:
        assert "Viloyatni tanlang" in (await h.text("🗺 Viloyatni tanlash"))[0]
        assert "reg:fargona" in callbacks(last_kb(h))
        out = await h.press("reg:fargona")
    assert "Qaysi ekin" in out[-1]
    assert "Tuprog‘ingiz" in (await h.press("crop:paxta"))[-1]
    assert any(isinstance(m, EditMessageReplyMarkup) for m in h.session.sent)
    assert "Qanday sug‘orasiz" in (await h.press("soil:orta"))[-1]
    assert "gektar" in (await h.press("method:egat"))[-1]
    assert callbacks(last_kb(h)) == ["area:1", "area:5", "area:10", "area:50", "area:other"]
    if area == "other":
        assert "gektarda yozing" in (await h.press("area:other"))[-1]
        assert "Tushunmadim" in (await h.text("-1"))[0]
        out = await h.text("2,5")
    else:
        out = await h.press(f"area:{area}")
    assert "Ekilgan sanani" in out[-1]
    planting = today - timedelta(days=90)
    # kalendar: oy almashtirish va kun tanlash
    prev = f"cal:plant:m:{planting.year}-{planting.month:02d}"
    await h.press(prev)
    assert any(isinstance(m, EditMessageReplyMarkup) and m.reply_markup for m in h.session.sent)
    out = await h.press(f"cal:plant:d:{planting.isoformat()}")
    assert "Oxirgi marta" in out[-1]
    assert f"cal:last:d:{today.isoformat()}" in callbacks(last_kb(h))
    return await h.press(f"cal:last:d:{(today - timedelta(days=5)).isoformat()}")


async def test_onboarding_and_commands(settings: Settings, tmp_path: Path) -> None:
    h = Harness(settings, tmp_path)
    out = await onboard(h)
    assert "Dala saqlandi" in out[-2] and "07:00" in out[-2]
    assert "Paxta" in out[-1] and "Zaxira" in out[-1]
    assert callbacks(last_kb(h))[1:] == [f"why:{h.repo.current_field(UID).id}",  # type: ignore[union-attr]
                                         f"week:{h.repo.current_field(UID).id}"]  # type: ignore[union-attr]
    row = h.repo.current_field(UID)
    assert row and row.area_ha == 10 and row.lat == 40.5 and row.planting == datetime.now().date() - timedelta(days=90)
    fid = row.id

    assert "Paxta" in (await h.text("/bugun"))[0]
    assert "Paxta" in (await h.text("/maslahat"))[0]
    assert "7 kunlik reja" in (await h.text("/hafta"))[0]
    assert "FAO-56" in (await h.press(f"why:{fid}"))[0]
    week = (await h.press(f"week:{fid}"))[0]
    assert "7 kunlik reja" in week and len(week.splitlines()) >= 8
    assert "/start" in (await h.press("why:999"))[0]
    assert "sug‘orildi" in (await h.press(f"irr:{fid}"))[0]
    assert "sug‘orildi" in (await h.text("/sugordim"))[0]
    assert "Ekilgan" in (await h.text("/dala"))[0]
    assert callbacks(last_kb(h)) == [f"fld:{fid}", "fld:new"]
    assert "Demo" in (await h.text("/demo"))[0]
    out = await h.press("demo:test_2025")
    assert "Namuna (sintetik)" in out[0]
    assert callbacks(last_kb(h)) == ["why:d:test_2025", "week:d:test_2025"]
    assert "FAO-56" in (await h.press("why:d:test_2025"))[0]
    assert "7 kunlik reja · Paxta · 10 ga" in (await h.press("week:d:test_2025"))[0]
    assert "make cache" in (await h.press("demo:yoq"))[0]
    assert "make cache" in (await h.press("week:d:yoq"))[0]
    assert "yordam" in (await h.text("/yordam"))[0]
    assert await h.press("cal:x") == []                        # bo‘sh tugma
    assert await h.press(f"cal:plant:d:{datetime.now().date().isoformat()}") == []   # onboarding tashqarisida

    # ikkinchi dala: viloyat va «Boshqa» maydon
    await h.press("fld:new")
    out = await onboard(h, gps=False, area="other")
    assert "#2 · Farg‘ona" in out[-1]
    rows = h.repo.fields_of(UID)
    assert len(rows) == 2 and rows[1].place == "fargona" and rows[1].area_ha == 2.5
    assert "Faol dala: 1." in (await h.press(f"fld:{fid}"))[0]
    assert h.repo.current_field(UID).id == fid  # type: ignore[union-attr]
    assert "/start" in (await h.press("fld:999"))[0]

    assert "Til" in (await h.text("/til"))[0]
    assert "русский" in (await h.press("lang:ru"))[0]
    assert "Команды" in (await h.text("salom"))[0]
    assert await h.text("/stats") == []            # admin emas


async def test_text_dates_and_no_cache(settings: Settings, tmp_path: Path) -> None:
    empty = settings.model_copy(update={"cache_dir": tmp_path / "bo‘sh", "allow_synthetic": False})
    h = Harness(empty, tmp_path)
    assert "make cache" in (await h.text("/demo"))[0]
    assert "/start" in (await h.text("/dala"))[0]
    today = datetime.now().date()
    await h.text("/start")
    await h.press("reg:yoq")                      # noto‘g‘ri viloyat — e’tiborsiz
    await h.loc(40.12, 67.84)
    await h.press("crop:bugdoy")
    await h.press("soil:ogir")
    await h.press("method:tomchi")
    await h.press("area:1")
    assert "Tushunmadim" in (await h.text("ertaga"))[0]
    await h.text((today - timedelta(days=30)).strftime("%d.%m.%Y"))
    assert "Tushunmadim" in (await h.text("01.01.1990"))[0]
    await h.text("bugun")
    row = h.repo.current_field(UID)
    assert row and row.crop == "bugdoy" and h.repo.last_irrigation(row.id) == today


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
    repo.add_field(12, f, TODAY - timedelta(days=1), place="jizzax")      # 2-dala ham alohida xabar oladi
    assert await scheduler.send_daily(bot, repo, wclient(tmp_path)) == 3
    texts = session.texts()
    assert len(texts) == 3 and texts[0].startswith("Paxta") is False and "#2 · Jizzax" in texts[2]
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
