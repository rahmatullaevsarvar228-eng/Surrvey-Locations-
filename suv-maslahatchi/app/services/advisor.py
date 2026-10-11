"""Field/Day obyektlarini yig‘ib, engine’ni chaqiradi. Formulalar faqat engine/suv_engine.py da."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from engine import suv_engine as se
from engine.suv_engine import Advice, Day, Field

from .demo_cache import DemoCache
from .demo_fields import SAMPLE_FIELDS
from .texts import advice_text, why_text
from .weather import Weather, WeatherClient


@dataclass(frozen=True)
class AdviceOut:
    advice: Advice
    text: str
    why: str

    def to_json(self) -> dict[str, Any]:
        return dict(advice=self.advice, text=self.text, why=self.why)


def render(fld: Field, a: Advice, lang: str) -> AdviceOut:
    return AdviceOut(advice=a, text=advice_text(a, fld.crop, fld.area_ha, lang),
                     why=why_text(a, fld.crop, lang))


def past_days_needed(last_irrigation: date, today: date) -> int:
    return max(7, (today - last_irrigation).days + 1)


def advise_live(fld: Field, last_irrigation: date, client: WeatherClient,
                lang: str = "uz") -> tuple[AdviceOut, Weather]:
    w = client.get(fld.lat, fld.lon, past_days=past_days_needed(last_irrigation, client.today()))
    return render(fld, se.advice(fld, last_irrigation, w.history, w.forecast), lang), w


def week_live(fld: Field, last_irrigation: date, client: WeatherClient) -> tuple[se.SimResult, Weather]:
    w = client.get(fld.lat, fld.lon, past_days=past_days_needed(last_irrigation, client.today()))
    return se.week_plan(fld, last_irrigation, w.history, w.forecast), w


def week_demo(fld: Field, last_irrigation: date, cache: DemoCache, today: date) -> se.SimResult:
    hist, fc = cache.history_forecast(today)
    return se.week_plan(fld, last_irrigation, hist, fc)


def advise_demo(fld: Field, last_irrigation: date, cache: DemoCache, today: date,
                lang: str = "uz") -> AdviceOut:
    hist, fc = cache.history_forecast(today)
    if not fc:
        raise ValueError("demo sanasi kesh oralig‘idan tashqarida")
    return render(fld, se.advice(fld, last_irrigation, hist, fc), lang)


def season_days(fld: Field, cache: DemoCache) -> list[Day]:
    end = fld.planting + timedelta(days=se.season_length(fld.crop) - 1)
    return cache.window(fld.planting, end)


def simulate_pair(fld: Field, cache: DemoCache,
                  habit: tuple[int, float] | None) -> dict[str, se.SimResult | None]:
    ds = season_days(fld, cache)
    return dict(fao=se.simulate(fld, ds),
                habit=se.simulate(fld, ds, fixed_schedule=habit) if habit else None)


def demand(cache: DemoCache, today: date) -> dict[str, Any]:
    hist, fc = cache.history_forecast(today)
    base = cache.meta.planting
    rows = []
    state: list[tuple[Field, date, list[Day]]] = []
    for s in SAMPLE_FIELDS:
        f = Field(crop=s.crop, soil=s.soil, method=s.method, planting=s.planting(base),
                  area_ha=s.area_ha, lat=cache.meta.lat, lon=cache.meta.lon)
        last = today - timedelta(days=s.last_irrigation_ago)
        state.append((f, last, hist))
        a = se.advice(f, last, hist, fc) if fc else None
        rows.append(dict(id=s.id, crop=s.crop, soil=s.soil, method=s.method, area_ha=s.area_ha,
                         planting=f.planting.isoformat(), last_irrigation=last.isoformat(),
                         holat=a["holat"] if a else None, kun=a["kun"] if a else None,
                         m3_jami=a["m3_jami"] if a else 0, zaxira=a["zaxira"] if a else None))
    return dict(days=se.demand_forecast(state, fc), fields=rows,
                total_area_ha=sum(s.area_ha for s in SAMPLE_FIELDS))
