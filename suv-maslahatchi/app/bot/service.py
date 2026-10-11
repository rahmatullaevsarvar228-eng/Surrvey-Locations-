"""Bot uchun biznes-logika (aiogram’siz, test qilinadi)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.db.repo import Repo, to_engine
from app.services import advisor
from app.services.demo_cache import DemoCache
from app.services.texts import t
from app.services.weather import WeatherClient, WeatherUnavailable
from engine.suv_engine import Field


@dataclass(frozen=True)
class Reply:
    text: str
    why: str | None = None
    field_id: int | None = None


def advice_for_user(repo: Repo, wc: WeatherClient, uid: int) -> Reply:
    lang = repo.lang(uid)
    row = repo.current_field(uid)
    if row is None:
        return Reply(t(lang, "errors.no_field"))
    fld = to_engine(row)
    last = repo.last_irrigation(row.id) or fld.planting
    try:
        out, w = advisor.advise_live(fld, last, wc, lang)
    except WeatherUnavailable:
        return Reply(t(lang, "errors.weather"), field_id=row.id)
    text = out.text
    if w.stale:
        hours = max(1, round((wc.clock() - w.fetched_at) / 3600))
        text += "\n" + t(lang, "advice.source_stale", hours=hours)
    return Reply(text, out.why, row.id)


def demo_reply(cache: DemoCache, lang: str) -> Reply:
    """/demo: namuna dala (o‘rta tuproq, egat), kesh ekish sanasi + 90 kun, 10 kun oldin sug‘orilgan."""
    today = cache.meta.planting + timedelta(days=90)
    fld = Field(crop=cache.meta.crop, soil="orta", method="egat", planting=cache.meta.planting,
                lat=cache.meta.lat, lon=cache.meta.lon)
    out = advisor.advise_demo(fld, today - timedelta(days=10), cache, today, lang)
    head = f"🧪 {t(lang, 'app.sample_label')} · {cache.meta.place}\n"
    src = t(lang, "advice.source_demo", place=cache.meta.place, date=today.isoformat())
    return Reply(f"{head}{out.text}\n\n{src}", out.why)


def field_info(repo: Repo, uid: int) -> str:
    lang = repo.lang(uid)
    row = repo.current_field(uid)
    if row is None:
        return t(lang, "errors.no_field")
    last = repo.last_irrigation(row.id)
    return t(lang, "bot.field_info", crop=t(lang, f"crop.{row.crop}"), soil=t(lang, f"soil.{row.soil}"),
             method=t(lang, f"method.{row.method}"), planting=row.planting.strftime("%d.%m.%Y"),
             area=f"{row.area_ha:g}", lat=f"{row.lat:.2f}", lon=f"{row.lon:.2f}",
             last=last.strftime("%d.%m.%Y") if last else "—")


def mark_irrigated(repo: Repo, uid: int, today: date) -> str:
    lang = repo.lang(uid)
    row = repo.current_field(uid)
    if row is None:
        return t(lang, "errors.no_field")
    repo.add_irrigation(row.id, today)
    return t(lang, "bot.irrigated_ok", date=today.strftime("%d.%m.%Y"))
