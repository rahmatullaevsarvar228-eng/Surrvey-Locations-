from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.db.repo import Repo, to_engine
from app.services import advisor, texts
from app.services.demo_cache import CacheMissing, get_cache, list_caches
from app.services.weather import WeatherClient, WeatherUnavailable, grid_key
from engine import suv_engine as se
from engine.suv_engine import Field

TODAY = date(2025, 7, 10)


def om(start: date, n: int, et0: float = 6.0) -> dict[str, Any]:
    ds = [start + timedelta(days=i) for i in range(n)]
    return {"daily": {"time": [d.isoformat() for d in ds], "et0_fao_evapotranspiration": [et0] * n,
                      "precipitation_sum": [0.0] * n}}


# ---------------------------------------------------------------- config
def test_settings_admin_ids(settings: Settings) -> None:
    assert settings.admin_ids == [1, 2]
    assert Settings(admin_ids="").admin_ids == []


# ---------------------------------------------------------------- weather client
class FakeNet:
    def __init__(self, fail: int = 0) -> None:
        self.calls = 0
        self.fail = fail

    def __call__(self, url: str) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail:
            raise OSError("tarmoq yo‘q")
        assert "latitude=40.10&longitude=67.80" in url      # setka: 0.1°
        return om(TODAY - timedelta(days=30), 37)


def client(tmp_path: Path, net: FakeNet, now: list[float]) -> WeatherClient:
    sleeps: list[float] = []
    c = WeatherClient(tmp_path, ttl_s=100, retries=3, backoff_s=1, getter=net,
                      sleep=sleeps.append, clock=lambda: now[0], today=lambda: TODAY)
    c.sleeps = sleeps  # type: ignore[attr-defined]
    return c


def test_grid_key() -> None:
    assert grid_key(40.123, 67.849) == "40.1_67.8"


def test_weather_ttl_and_retry(tmp_path: Path) -> None:
    now = [1000.0]
    net = FakeNet(fail=2)
    c = client(tmp_path, net, now)
    w = c.get(40.12, 67.84)
    assert net.calls == 3 and c.sleeps == [1, 2]  # type: ignore[attr-defined]
    assert len(w.history) == 30 and len(w.forecast) == 7 and not w.stale
    c.get(40.14, 67.81)                      # o‘sha setka katagi, TTL ichida → tarmoqsiz
    assert net.calls == 3
    now[0] += 101
    c.get(40.12, 67.84)
    assert net.calls == 4


def test_weather_file_fallback(tmp_path: Path) -> None:
    now = [1000.0]
    client(tmp_path, FakeNet(), now).get(40.12, 67.84)
    now[0] += 500
    dead = client(tmp_path, FakeNet(fail=99), now)
    w = dead.get(40.12, 67.84)
    assert w.stale and w.fetched_at == 1000.0
    with pytest.raises(WeatherUnavailable):
        dead.get(41.0, 69.0)


def test_weather_too_old_fallback(tmp_path: Path) -> None:
    now = [1000.0]
    c = client(tmp_path, FakeNet(), now)
    c.get(40.12, 67.84)
    late = WeatherClient(tmp_path, getter=FakeNet(fail=99), sleep=lambda s: None,
                         today=lambda: TODAY + timedelta(days=30))
    with pytest.raises(WeatherUnavailable):
        late.get(40.12, 67.84)


# ---------------------------------------------------------------- demo cache
def test_cache_ignores_synthetic_in_data_dir(real_like_cache: Path) -> None:
    ids = [c.meta.id for c in list_caches(real_like_cache)]
    assert ids == ["test_2025"]
    ids2 = [c.meta.id for c in list_caches(real_like_cache, allow_synthetic=True)]
    assert ids2 == ["test_2025", "sintetik_2025"]
    assert list_caches(real_like_cache / "yoq") == []
    with pytest.raises(CacheMissing):
        get_cache(real_like_cache, "sintetik_2025")


def test_cache_history_forecast(real_like_cache: Path) -> None:
    c = get_cache(real_like_cache, "test_2025")
    h, f = c.history_forecast(TODAY)
    assert len(f) == 7 and f[0].date == TODAY and h[-1].date == TODAY - timedelta(days=1)
    assert len(h) == 92


# ---------------------------------------------------------------- texts
def test_t_fallbacks() -> None:
    assert texts.t("ru", "crop.paxta") == "Хлопчатник"
    assert texts.t("xx", "crop.paxta") == "Paxta"
    assert texts.t("uz", "yoq.kalit") == "yoq.kalit"
    assert texts.load("de") == texts.load("uz")


def test_i18n_keys_match() -> None:
    def keys(d: dict[str, Any], p: str = "") -> set[str]:
        out: set[str] = set()
        for k, v in d.items():
            out |= keys(v, f"{p}{k}.") if isinstance(v, dict) else {p + k}
        return out
    assert keys(texts.load("uz")) == keys(texts.load("ru"))


def test_i18n_uses_proper_apostrophes() -> None:
    raw = (texts.I18N_DIR / "uz.json").read_text(encoding="utf-8")
    for bad in ("o'", "g'", "O'", "G'", "o`", "g`"):
        assert bad not in raw, bad


def _adv(holat: str, **kw: Any) -> se.Advice:
    base: dict[str, Any] = dict(holat=holat, kun=None, netto_mm=0.0, m3_ga=0, m3_jami=0, zaxira=0.4,
                                bosqich="orta", das=90, bolib_kun=None, oxirgi_sugorish_kun=12,
                                sarf_mm=55.0, sarf_kunlar=7, yomgir_mm=0.0, yomgir3_mm=0.0, taw_mm=170,
                                raw_mm=110.5, tanqislik_mm=102.0, tarix_yetarli=True)
    base.update(kw)
    return se.Advice(**base)  # type: ignore[typeddict-item]


def test_advice_text_variants() -> None:
    s = texts.advice_text(_adv("bugun", kun=0, m3_ga=1880, m3_jami=4700, bolib_kun=5), "paxta", 2.5)
    assert "BUGUN SUG‘ORING" in s and "1880 m³/ga" in s and "4700 m³" in s and "5 kunga" in s
    assert "▰▰▰▰▱▱▱▱▱▱ 40%" in s
    s = texts.advice_text(_adv("tez_orada", kun=3, m3_ga=1500), "paxta", 1, "ru")
    assert "ЧЕРЕЗ 3 ДН." in s
    s = texts.advice_text(_adv("kerak_emas", yomgir3_mm=7.0, tarix_yetarli=False), "bugdoy", 1)
    assert "SHART EMAS" in s and "7 mm" in s and "to‘liq emas" in s
    s = texts.advice_text(_adv("mavsum_yoq", bosqich="tugagan", zaxira=None), "paxta", 1)
    assert "mavsum tugagan" in s
    w = texts.why_text(_adv("bugun"), "paxta")
    assert "12 kun" in w and "55 mm" in w and "FAO-56" in w and "170 mm" in w
    assert texts.why_text(_adv("mavsum_yoq"), "paxta").startswith("Model")


# ---------------------------------------------------------------- advisor
def test_advisor_demo_and_season(real_like_cache: Path) -> None:
    c = get_cache(real_like_cache, "test_2025")
    f = Field(crop="paxta", soil="orta", method="egat", planting=c.meta.planting, area_ha=3)
    out = advisor.advise_demo(f, TODAY - timedelta(days=12), c, TODAY)
    assert out.advice["holat"] in {"bugun", "tez_orada", "kerak_emas"}
    assert out.text and "FAO-56" in out.why
    with pytest.raises(ValueError):
        advisor.advise_demo(f, TODAY, c, date(2030, 1, 1))
    pair = advisor.simulate_pair(f, c, (7, 120.0))
    assert pair["fao"] and len(pair["fao"]["rows"]) == 195
    assert pair["habit"] and pair["habit"]["sugorishlar"] > 0
    assert advisor.simulate_pair(f, c, None)["habit"] is None
    d = advisor.demand(c, TODAY)
    assert len(d["days"]) == 7 and len(d["fields"]) == 8 and d["total_area_ha"] == 84.0


def test_advisor_live(tmp_path: Path) -> None:
    c = client(tmp_path, FakeNet(), [0.0])
    f = Field(crop="paxta", soil="orta", method="egat", planting=date(2025, 4, 15), lat=40.12, lon=67.84)
    out, w = advisor.advise_live(f, TODAY - timedelta(days=5), c, "ru")
    assert out.text and not w.stale
    assert advisor.past_days_needed(TODAY - timedelta(days=40), TODAY) == 41


# ---------------------------------------------------------------- repo
def test_repo_roundtrip(settings: Settings) -> None:
    r = Repo(settings.db_url)
    f = Field(crop="paxta", soil="ogir", method="tomchi", planting=date(2025, 4, 20), area_ha=2.0)
    fid = r.add_field(77, f, date(2025, 7, 1))
    assert r.lang(77) == "uz" and r.lang(999) == "uz"
    r.set_lang(77, "ru")
    assert r.lang(77) == "ru"
    r.set_lang(78, "ru")
    row = r.current_field(77)
    assert row and row.id == fid and to_engine(row) == f
    assert r.last_irrigation(fid) == date(2025, 7, 1)
    r.add_irrigation(fid, date(2025, 7, 9), 400)
    assert r.last_irrigation(fid) == date(2025, 7, 9)
    fid2 = r.add_field(77, f, None)
    assert r.last_irrigation(fid2) is None
    assert [x.id for x in r.latest_field_per_user()] == [fid2]
    assert len(r.all_fields()) == 2 and r.stats() == (2, 2, 2)
    assert r.current_field(5) is None
    Repo("sqlite:///:memory:")


def test_fixture_is_marked_synthetic() -> None:
    js = json.loads((Path(__file__).parent / "fixtures" / "sintetik_2025.json").read_text(encoding="utf-8"))
    assert js["meta"]["synthetic"] is True and "SINTETIK" in js["meta"]["source"]
