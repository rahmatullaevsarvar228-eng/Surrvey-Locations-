"""
Oflayn demo keshi: data/cache/*.json — scripts/build_demo_cache.py yozgan haqiqiy Open-Meteo arxivi.
Sintetik sinov fayli (tests/fixtures) faqat SUV_ALLOW_SYNTHETIC=1 bo‘lsa va ochiq belgi bilan yuklanadi.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from engine import suv_engine as se
from engine.suv_engine import Day

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class CacheMissing(LookupError):
    pass


@dataclass(frozen=True)
class CacheMeta:
    id: str
    place: str
    lat: float
    lon: float
    start: date
    end: date
    crop: str               # qaysi ekin mavsumi uchun yig‘ilgan
    planting: date          # namuna ekish sanasi (sozlanadi)
    source: str
    fetched_at: str
    synthetic: bool

    def to_json(self) -> dict[str, Any]:
        return dict(id=self.id, place=self.place, lat=self.lat, lon=self.lon,
                    start=self.start.isoformat(), end=self.end.isoformat(), crop=self.crop,
                    planting=self.planting.isoformat(), source=self.source,
                    fetched_at=self.fetched_at, synthetic=self.synthetic)


@dataclass(frozen=True)
class DemoCache:
    meta: CacheMeta
    days: list[Day]

    def window(self, start: date, end: date) -> list[Day]:
        return [d for d in self.days if start <= d.date <= end]

    def history_forecast(self, today: date, past: int = 92,
                         ahead: int = 7) -> tuple[list[Day], list[Day]]:
        """Demo «bugun»: oldingi kunlar — tarix, keyingi `ahead` kun — prognoz o‘rnida kuzatuv."""
        hist = [d for d in self.days if d.date < today][-past:]
        fc = [d for d in self.days if d.date >= today][:ahead]
        return hist, fc


def _read(path: Path) -> DemoCache:
    js = json.loads(path.read_text(encoding="utf-8"))
    m = js["meta"]
    meta = CacheMeta(id=m["id"], place=m["place"], lat=float(m["lat"]), lon=float(m["lon"]),
                     start=date.fromisoformat(m["start"]), end=date.fromisoformat(m["end"]),
                     crop=m["crop"], planting=date.fromisoformat(m["planting"]),
                     source=m["source"], fetched_at=m["fetched_at"],
                     synthetic=bool(m.get("synthetic", False)))
    return DemoCache(meta=meta, days=se.parse_open_meteo(js))


def list_caches(cache_dir: Path, allow_synthetic: bool = False) -> list[DemoCache]:
    files = sorted(cache_dir.glob("*.json")) if cache_dir.exists() else []
    out = [_read(p) for p in files]
    out = [c for c in out if not c.meta.synthetic]      # data/cache ga faqat haqiqiy ma’lumot
    if allow_synthetic and FIXTURES.exists():
        out += [_read(p) for p in sorted(FIXTURES.glob("sintetik_*.json"))]
    return out


def get_cache(cache_dir: Path, cache_id: str, allow_synthetic: bool = False) -> DemoCache:
    for c in list_caches(cache_dir, allow_synthetic):
        if c.meta.id == cache_id:
            return c
    raise CacheMissing(cache_id)
