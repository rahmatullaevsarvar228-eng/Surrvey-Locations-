"""
Open-Meteo mijozi: setka keshi (lat/lon 0,1° ga yaxlitlanadi), 3 soat TTL,
qayta urinish (eksponensial kutish) va fayl zaxirasi (internet bo‘lmasa, oxirgi olingan ma’lumot).
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from engine import suv_engine as se
from engine.suv_engine import Day

log = logging.getLogger(__name__)
MAX_PAST_DAYS = 92          # Open-Meteo forecast API chegarasi


class WeatherUnavailable(RuntimeError):
    """Ob-havo olinmadi va zaxira fayl ham yo‘q."""


@dataclass(frozen=True)
class Weather:
    history: list[Day]
    forecast: list[Day]
    fetched_at: float
    stale: bool              # zaxira fayldan, TTL o‘tgan


def grid_key(lat: float, lon: float) -> str:
    return f"{round(lat, 1):.1f}_{round(lon, 1):.1f}"


class WeatherClient:
    def __init__(self, cache_dir: Path, ttl_s: int = 3 * 3600, retries: int = 3,
                 backoff_s: float = 1.0, getter: Callable[[str], Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.time,
                 today: Callable[[], date] = date.today) -> None:
        self.cache_dir = cache_dir
        self.ttl_s = ttl_s
        self.retries = retries
        self.backoff_s = backoff_s
        self.getter = getter or se._get
        self.sleep = sleep
        self.clock = clock
        self.today = today
        self._mem: dict[str, tuple[float, dict[str, Any]]] = {}

    def _file(self, key: str, past_days: int) -> Path:
        return self.cache_dir / f"{key}_p{past_days}.json"

    def _fetch_with_retry(self, url: str) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                data: dict[str, Any] = self.getter(url)
                return data
            except Exception as e:  # tarmoq, JSON, HTTP — hammasi qayta urinishga
                last = e
                log.warning("Open-Meteo xato (%s/%s): %s", attempt + 1, self.retries, e)
                if attempt + 1 < self.retries:
                    self.sleep(self.backoff_s * 2 ** attempt)
        raise WeatherUnavailable(str(last))

    def get(self, lat: float, lon: float, past_days: int = 30, forecast_days: int = 7) -> Weather:
        past_days = max(1, min(MAX_PAST_DAYS, past_days))
        key = grid_key(lat, lon)
        mkey = f"{key}_p{past_days}"
        now = self.clock()
        hit = self._mem.get(mkey)
        stale = False
        if hit and now - hit[0] < self.ttl_s:
            ts, js = hit
        else:
            path = self._file(key, past_days)
            glat, glon = (float(x) for x in key.split("_"))
            try:
                js = self._fetch_with_retry(se.forecast_url(glat, glon, past_days, forecast_days))
                ts = now
                self._mem[mkey] = (ts, js)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"fetched_at": ts, "data": js}), encoding="utf-8")
            except WeatherUnavailable:
                if not path.exists():
                    raise
                saved = json.loads(path.read_text(encoding="utf-8"))
                ts, js = float(saved["fetched_at"]), saved["data"]
                stale = now - ts >= self.ttl_s
        history, forecast = se.split_history(se.parse_open_meteo(js), self.today())
        if not forecast:
            raise WeatherUnavailable("prognoz kunlari yo‘q (zaxira juda eski)")
        return Weather(history=history, forecast=forecast, fetched_at=ts, stale=stale)
