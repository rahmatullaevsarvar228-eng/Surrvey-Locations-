"""Bot uchun biznes-logika (aiogram’siz, test qilinadi)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.db.models import FieldRow
from app.db.repo import Repo, to_engine
from app.services import advisor
from app.services.demo_cache import DemoCache
from app.services.texts import t, week_text
from app.services.weather import WeatherClient, WeatherUnavailable
from engine.suv_engine import Field

from .regions import region_name


@dataclass(frozen=True)
class Reply:
    text: str
    why: str | None = None
    field_id: int | None = None
    week: str | None = None


def _last(repo: Repo, row: FieldRow) -> date:
    return repo.last_irrigation(row.id) or row.planting


def advice_for_field(repo: Repo, wc: WeatherClient, row: FieldRow, lang: str, multi: bool = False) -> Reply:
    fld = to_engine(row)
    last = _last(repo, row)
    try:
        out, w = advisor.advise_live(fld, last, wc, lang)
        plan, _ = advisor.week_live(fld, last, wc)
    except WeatherUnavailable:
        return Reply(t(lang, "errors.weather"), field_id=row.id)
    text = out.text
    if multi:
        text = f"#{field_no(repo, row)} · {field_place(row, lang)}\n{text}"
    if w.stale:
        hours = max(1, round((wc.clock() - w.fetched_at) / 3600))
        text += "\n" + t(lang, "advice.source_stale", hours=hours)
    return Reply(text, out.why, row.id, week_text(plan, row.crop, row.area_ha, lang))


def advice_for_user(repo: Repo, wc: WeatherClient, uid: int) -> Reply:
    lang = repo.lang(uid)
    row = repo.current_field(uid)
    if row is None:
        return Reply(t(lang, "errors.no_field"))
    return advice_for_field(repo, wc, row, lang, multi=len(repo.fields_of(uid)) > 1)


def week_for_user(repo: Repo, wc: WeatherClient, uid: int) -> str:
    rep = advice_for_user(repo, wc, uid)
    return rep.week or rep.text


def demo_reply(cache: DemoCache, lang: str) -> Reply:
    """/demo: namuna dala (o‘rta tuproq, egat), kesh ekish sanasi + 90 kun (iyul), 10 kun oldin sug‘orilgan."""
    today = cache.meta.planting + timedelta(days=90)
    fld = Field(crop=cache.meta.crop, soil="orta", method="egat", planting=cache.meta.planting,
                lat=cache.meta.lat, lon=cache.meta.lon, area_ha=10)
    last = today - timedelta(days=10)
    out = advisor.advise_demo(fld, last, cache, today, lang)
    head = f"🧪 {t(lang, 'app.sample_label')} · {cache.meta.place}\n"
    src = t(lang, "advice.source_demo", place=cache.meta.place, date=today.isoformat())
    week = week_text(advisor.week_demo(fld, last, cache, today), fld.crop, fld.area_ha, lang)
    return Reply(f"{head}{out.text}\n\n{src}", out.why, week=week)


def field_place(row: FieldRow, lang: str) -> str:
    return region_name(row.place, lang) if row.place else f"{row.lat:.2f}, {row.lon:.2f}"


def field_no(repo: Repo, row: FieldRow) -> int:
    return [f.id for f in repo.fields_of(row.user_id)].index(row.id) + 1


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


def mark_irrigated(repo: Repo, uid: int, today: date, field_id: int | None = None) -> str:
    lang = repo.lang(uid)
    row = repo.current_field(uid)
    if field_id is not None:
        row = next((f for f in repo.fields_of(uid) if f.id == field_id), row)
    if row is None:
        return t(lang, "errors.no_field")
    repo.add_irrigation(row.id, today)
    return t(lang, "bot.irrigated_ok", date=today.strftime("%d.%m.%Y"))
