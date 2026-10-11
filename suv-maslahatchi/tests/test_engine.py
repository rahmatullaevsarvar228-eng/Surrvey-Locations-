"""FAO-56 yadrosi testlari. Ob-havo qiymatlari — qo‘lda hisoblash uchun tanlangan sun’iy sonlar."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pytest

from engine import suv_engine as se
from engine.suv_engine import Day, Field

PLANT = date(2025, 4, 15)


def days(start: date, n: int, et0: float = 6.0, rain: float = 0.0) -> list[Day]:
    return [Day(date=start + timedelta(days=i), et0=et0, rain=rain) for i in range(n)]


def fld(**kw: Any) -> Field:
    base: dict[str, Any] = dict(crop="paxta", soil="orta", method="egat", planting=PLANT)
    base.update(kw)
    return Field(**base)


# ---------------------------------------------------------------- parametrlar va Field
def test_field_validation() -> None:
    for bad in (dict(crop="olma"), dict(soil="tosh"), dict(method="qo‘l"), dict(kc_set="xx"),
                dict(eff=0.0), dict(eff=1.5), dict(area_ha=0), dict(kc_scale=0)):
        with pytest.raises(ValueError):
            fld(**bad)


def test_stage_bounds_and_season() -> None:
    assert se.stage_bounds("paxta") == (30, 80, 140, 195)
    assert se.season_length("bugdoy") == 240


# ---------------------------------------------------------------- Kc egri chizig‘i
def test_kc_curve_uz_paxta() -> None:
    f = fld()
    assert se.kc_on(f, -1) == 0.0
    assert se.kc_on(f, 0) == 0.15
    assert se.kc_on(f, 29) == 0.15
    assert se.kc_on(f, 55) == pytest.approx(0.15 + 25 / 50 * (1.15 - 0.15))
    assert se.kc_on(f, 100) == 1.15
    assert se.kc_on(f, 140) == 1.15
    assert se.kc_on(f, 194) == pytest.approx(1.15 + 54 / 55 * (0.45 - 1.15))
    assert se.kc_on(f, 195) == 0.0


def test_adjust_kc_eq62() -> None:
    assert se.adjust_kc(1.15, None, 30, 1.2) == 1.15
    # u2=2, RHmin=45 → tuzatish 0
    assert se.adjust_kc(1.15, 2.0, 45.0, 1.2) == pytest.approx(1.15)
    # u2=4, RHmin=25: (0.08 + 0.08)·(0.4)^0.3
    assert se.adjust_kc(1.15, 4.0, 25.0, 1.2) == pytest.approx(1.15 + 0.16 * 0.4 ** 0.3)
    # chegaralar: u2>6 → 6, RHmin<20 → 20
    assert se.adjust_kc(1.0, 10.0, 5.0, 3.0) == pytest.approx(1.0 + 0.16 + 0.1)


def test_climate_adjustment_only_for_fao_set() -> None:
    uz, fao = fld(), fld(kc_set="fao")
    assert se.kc_on(uz, 100, 4.0, 25.0) == se.kc_on(uz, 100)
    assert se.kc_on(fao, 100, 4.0, 25.0) > se.kc_on(fao, 100)
    # paxta Kc_end (0.60) > 0.45 → tuzatiladi; bug‘doy Kc_end (0.325) → tuzatilmaydi
    assert se.kc_on(fao, 194, 4.0, 25.0) > se.kc_on(fao, 194)
    w = fld(crop="bugdoy", kc_set="fao")
    end_day = se.season_length("bugdoy") - 1
    mid_adj = se.adjust_kc(1.15, 4.0, 25.0, 1.0)
    expected = mid_adj + (end_day - 210) / 30 * (0.325 - mid_adj)
    assert se.kc_on(w, end_day, 4.0, 25.0) == pytest.approx(expected)


def test_stage_names() -> None:
    assert [se.stage_of("paxta", d) for d in (-1, 0, 30, 80, 140, 195)] == [
        "ekilmagan", "boshlangich", "rivojlanish", "orta", "kechki", "tugagan"]


# ---------------------------------------------------------------- ildiz va tuproq
def test_root_depth_and_taw() -> None:
    f = fld()
    assert se.root_depth(f, 0) == 0.2
    assert se.root_depth(f, 30) == 0.2
    assert se.root_depth(f, 55) == pytest.approx(0.2 + 0.5 * 0.8)
    assert se.root_depth(f, 80) == 1.0
    taw, raw = se.taw_raw(f, 100)
    assert (taw, raw) == (170.0, pytest.approx(0.65 * 170))


def test_efficiency_and_trigger() -> None:
    assert se.efficiency(fld()) == 0.60
    assert se.efficiency(fld(eff=0.5)) == 0.5
    assert se.trigger(fld(), 100) == pytest.approx(110.5)           # egat: RAW
    assert se.trigger(fld(method="tomchi"), 100) == 25               # me’yor < RAW
    assert se.trigger(fld(method="tomchi"), 0) == pytest.approx(0.65 * 34)              # RAW < me’yor
    assert se.trigger(fld(method="yomgir", soil="yengil"), 0) == pytest.approx(0.65 * 18)


def test_effective_rain() -> None:
    assert se.effective_rain(1.0, 6.0) == 0.0
    assert se.effective_rain(1.3, 6.0) == 1.3


def test_etc_and_kc_scale() -> None:
    d = Day(date=PLANT + timedelta(days=100), et0=7.0)
    assert se.etc_of(fld(), d) == pytest.approx(1.15 * 7)
    assert se.etc_of(fld(kc_scale=0.9), d) == pytest.approx(0.9 * 1.15 * 7)


def test_step_depletion_clamps() -> None:
    f = fld()
    d = Day(date=PLANT + timedelta(days=100), et0=7.0, rain=50.0)
    assert se.step_depletion(f, 10.0, d) == 0.0
    d2 = Day(date=PLANT + timedelta(days=100), et0=7.0)
    assert se.step_depletion(f, 169.0, d2) == 170.0


# ---------------------------------------------------------------- simulyatsiya
def test_simulate_advice_mode_water_balance() -> None:
    f = fld()
    ds = days(PLANT, 195)
    r = se.simulate(f, ds)
    assert len(r["rows"]) == 195
    assert r["stress_kunlari"] == 0
    assert r["sugorishlar"] > 0
    # brutto = netto/eff; balans: jami ETc ≈ jami netto + oxirgi Dr (yomg‘irsiz, boshlanishda Dr=0)
    net = sum(x["netto_mm"] for x in r["rows"])
    last_dr = r["rows"][-1]["tanqislik_mm"]
    assert net + last_dr == pytest.approx(r["etc_mm"], abs=2)
    assert r["suv_m3_ga"] == pytest.approx(net / 0.6 * 10, rel=0.01)
    # FAO rejimida chuqur o‘tish yo‘q; yo‘qotish = qo‘llash yo‘qotishi
    assert r["chuqur_m3_ga"] == 0
    assert r["yoqotish_m3_ga"] == pytest.approx(r["suv_m3_ga"] * 0.4, rel=0.01)


def test_simulate_fixed_schedule_overwatering_and_stress() -> None:
    f = fld()
    ds = days(PLANT, 195)
    habit = se.simulate(f, ds, fixed_schedule=(5, 150.0))   # ko‘p suv → chuqur o‘tish
    assert habit["chuqur_m3_ga"] > 0
    assert habit["sugorishlar"] == 39
    dry = se.simulate(f, ds, fixed_schedule=(40, 50.0))     # kam suv → stress
    assert dry["stress_kunlari"] > 0
    assert any(row["stress"] for row in dry["rows"])
    with pytest.raises(ValueError):
        se.simulate(f, ds, fixed_schedule=(0, 10.0))


def test_simulate_out_of_season_and_rain() -> None:
    f = fld()
    pre = days(PLANT - timedelta(days=5), 5, rain=20)
    r = se.simulate(f, pre)
    assert r["sugorishlar"] == 0 and r["etc_mm"] == 0
    assert r["rows"][0]["bosqich"] == "ekilmagan"


def test_tomchi_triggers_more_often_smaller_doses() -> None:
    ds = days(PLANT, 195)
    egat = se.simulate(fld(), ds)
    tomchi = se.simulate(fld(method="tomchi"), ds)
    assert tomchi["sugorishlar"] > egat["sugorishlar"]
    assert tomchi["suv_m3_ga"] < egat["suv_m3_ga"]          # samaradorlik 0.9 vs 0.6


# ---------------------------------------------------------------- maslahat
def test_depletion_since() -> None:
    f = fld()
    start = PLANT + timedelta(days=100)
    hist = days(start, 10, et0=5.0)
    assert se.depletion_since(f, start + timedelta(days=4), hist) == pytest.approx(5 * 1.15 * 5)


def _adv(f: Field, last_days_ago: int, et0: float = 7.0, rain: float = 0.0,
         today_das: int = 100, fc_rain: float = 0.0) -> se.Advice:
    today = PLANT + timedelta(days=today_das)
    hist = days(today - timedelta(days=30), 30, et0=et0, rain=rain)
    fc = days(today, 7, et0=et0, rain=fc_rain)
    return se.advice(f, today - timedelta(days=last_days_ago), hist, fc)


def test_advice_today() -> None:
    a = _adv(fld(area_ha=2.5), last_days_ago=14)
    # 13 kun × 8.05 = 104.65 → bugun + 8.05 = 112.7 ≥ 110.5
    assert a["holat"] == "bugun" and a["kun"] == 0
    assert a["netto_mm"] == pytest.approx(112.7, abs=0.1)
    assert a["m3_ga"] == round(112.7 / 0.6 * 10)
    assert a["m3_jami"] == round(a["m3_ga"] * 2.5)
    assert a["tanqislik_mm"] == pytest.approx(104.65, abs=0.1)
    assert a["zaxira"] == pytest.approx(1 - 104.65 / 170, abs=1e-3)
    assert a["sarf_kunlar"] == 7 and a["sarf_mm"] == pytest.approx(7 * 8.05, abs=0.1)
    assert a["tarix_yetarli"] and a["bolib_kun"] is None


def test_advice_soon_and_not_needed() -> None:
    soon = _adv(fld(), last_days_ago=10)
    assert soon["holat"] == "tez_orada" and soon["kun"] == 4
    ok = _adv(fld(), last_days_ago=1, et0=2.0)
    assert ok["holat"] == "kerak_emas" and ok["m3_ga"] == 0 and ok["kun"] is None
    rainy = _adv(fld(), last_days_ago=1, fc_rain=4.0)
    assert rainy["yomgir3_mm"] == 12.0


def test_advice_out_of_season() -> None:
    a = _adv(fld(), last_days_ago=3, today_das=250)
    assert a["holat"] == "mavsum_yoq" and a["zaxira"] is None and a["bosqich"] == "tugagan"


def test_advice_season_ends_inside_forecast() -> None:
    a = _adv(fld(), last_days_ago=1, et0=2.0, today_das=192)
    assert a["holat"] == "kerak_emas"


def test_advice_drip_split() -> None:
    a = _adv(fld(method="tomchi"), last_days_ago=10)
    assert a["holat"] == "bugun"
    assert a["bolib_kun"] == pytest.approx(int(-(-a["netto_mm"] // 25)))


def test_advice_history_gap_flag() -> None:
    a = _adv(fld(), last_days_ago=60)
    assert not a["tarix_yetarli"]
    with pytest.raises(ValueError):
        se.advice(fld(), PLANT, [], [])


def test_bar() -> None:
    assert se.bar(0.6) == "▰▰▰▰▰▰▱▱▱▱"
    assert se.bar(-1) == "▱" * 10 and se.bar(2) == "▰" * 10


# ---------------------------------------------------------------- uyushma paneli
def test_demand_forecast() -> None:
    today = PLANT + timedelta(days=100)
    hist = days(today - timedelta(days=30), 30)
    fc = days(today, 7)
    a = (fld(area_ha=10), today - timedelta(days=14), hist)
    b = (fld(area_ha=5, method="tomchi"), today - timedelta(days=2), hist)
    c = (fld(planting=today + timedelta(days=30)), today, hist)     # hali ekilmagan
    out = se.demand_forecast([a, b, c], fc)
    assert [x["sana"] for x in out] == [d.date.isoformat() for d in fc]
    # ETc = 1.15·6 = 6.9 mm/kun. b (tomchi): tarixda 1 kun → 2-kuni 4·6.9 = 27.6 ≥ 25.
    # a (egat): tarixda 13 kun → 3-kuni 17·6.9 = 117.3 ≥ 110.5.
    assert out[0]["dalalar"] == out[1]["dalalar"] == 0
    assert out[2] == {"sana": out[2]["sana"], "m3": round(27.6 / 0.9 * 10 * 5), "dalalar": 1}
    assert out[3]["dalalar"] == 1 and out[3]["m3"] == round(117.3 / 0.6 * 10 * 10)
    assert out[6]["dalalar"] == 1                                      # tomchi: 4·6.9 ≥ 25 yana


# ---------------------------------------------------------------- ob-havo (tarmoqsiz)
SAMPLE: dict[str, Any] = {"daily": {"time": ["2025-06-01", "2025-06-02"],
                                    "et0_fao_evapotranspiration": [6.1, None],
                                    "precipitation_sum": [None, 3.0]}}


def test_parse_and_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    ds = se.parse_open_meteo(SAMPLE)
    assert ds == [Day(date(2025, 6, 1), 6.1, 0.0), Day(date(2025, 6, 2), 0.0, 3.0)]
    assert "past_days=30" in se.forecast_url(40.123, 67.84)
    assert "latitude=40.12" in se.archive_url(40.123, 67.84, date(2025, 4, 1), date(2025, 10, 1))
    h, f = se.split_history(ds, date(2025, 6, 2))
    assert len(h) == 1 and len(f) == 1


def test_fetch_helpers_use_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(se, "_get", lambda url, timeout=20: SAMPLE)
    assert len(se.fetch_archive(40, 67, date(2025, 6, 1), date(2025, 6, 2))) == 2
    h, f = se.fetch_weather(40, 67)
    assert len(h) + len(f) == 2


def test_get_reads_json(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    class R(io.BytesIO):
        def __enter__(self) -> R:
            return self

        def __exit__(self, *a: object) -> None:
            pass

    monkeypatch.setattr(se.urllib.request, "urlopen",
                        lambda url, timeout: R(json.dumps(SAMPLE).encode()))
    assert se._get("https://x")["daily"]["time"][0] == "2025-06-01"
