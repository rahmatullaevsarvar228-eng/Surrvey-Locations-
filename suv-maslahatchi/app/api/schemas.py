from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel
from pydantic import Field as PField

from engine.suv_engine import Field

Lang = Literal["uz", "ru"]


class FieldIn(BaseModel):
    crop: Literal["paxta", "bugdoy"] = "paxta"
    soil: Literal["yengil", "orta", "ogir"] = "orta"
    method: Literal["egat", "yomgir", "tomchi"] = "egat"
    planting: date | None = None             # bo‘sh → kesh namuna ekish sanasi
    area_ha: float = PField(1.0, gt=0, le=10_000)
    lat: float = PField(40.12, ge=-90, le=90)
    lon: float = PField(67.84, ge=-180, le=180)
    kc_set: Literal["uz", "fao"] = "uz"
    eff: float | None = PField(None, gt=0, le=1)
    kc_scale: float = PField(1.0, gt=0, le=2)

    def to_engine(self, default_planting: date | None = None) -> Field:
        planting = self.planting or default_planting
        if planting is None:
            raise ValueError("ekish sanasi kerak")
        return Field(crop=self.crop, soil=self.soil, method=self.method, planting=planting,
                     area_ha=self.area_ha, lat=self.lat, lon=self.lon, kc_set=self.kc_set,
                     eff=self.eff, kc_scale=self.kc_scale)


class AdviceIn(BaseModel):
    field: FieldIn
    last_irrigation: date
    lang: Lang = "uz"
    mode: Literal["live", "demo"] = "demo"
    cache_id: str | None = None
    today: date | None = None                 # demo «bugun»


class Habit(BaseModel):
    every_days: int = PField(ge=1, le=60)
    mm: float = PField(ge=0, le=500)


class SimulateIn(BaseModel):
    field: FieldIn
    cache_id: str
    habit: Habit | None = None
