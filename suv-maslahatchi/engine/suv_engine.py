"""
SUV MASLAHATCHI — sug‘orish maslahati hisob yadrosi (v3)
Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar

Ilmiy asos — FAO-56 (Allen, Pereira, Raes, Smith, 1998) kunlik tuproq-suv balansi:
  ETc  = Kc × ET0                                   ekin suv iste’moli, mm/kun
  Dr_i = Dr_(i-1) − Pe_i − I_i + ETc_i              ildiz zonasidagi suv tanqisligi, mm
  TAW  = θ_foydali (mm/m) × Zr (m)                  umumiy foydali suv
  RAW  = p × TAW                                    ekin stresssiz foydalanadigan suv
  Sug‘orish: Dr ≥ chegara (RAW yoki usulning bir martalik me’yori). Netto = Dr, brutto = Dr / samaradorlik.
  1 mm = 10 m³/ga.

Parametrlar:
  * Kc — ikki to‘plam:
      "uz"  : Farg‘ona vodiysida o‘lchangan (Kenjabaev va boshq., 2020; 2009–2011 dala tajribalari):
              paxta 0,15 / 1,15 / 0,45; kuzgi bug‘doy 0,26 / 1,03 / 0,56.  ← ASOSIY (mahalliy)
      "fao" : FAO-56, 12-jadval (paxta 0,35 / 1,15–1,20 / 0,70–0,50; kuzgi bug‘doy 0,7 / 1,15 / 0,25–0,4).
  * Kc_mid iqlim tuzatmasi — FAO-56, 62-tenglama (shamol u2 va RHmin bo‘lsa). Faqat "fao" to‘plamiga
    qo‘llanadi: "uz" qiymatlari mahalliy iqlimda o‘lchangan, qayta tuzatish ikki marta hisoblash bo‘ladi.
  * Bosqich davomiyligi — FAO-56, 11-jadval (O‘zbekiston uchun qator yo‘q → pilotda kalibrlanadi).
  * Ildiz chuqurligi Zr va p — FAO-56, 22-jadval; Zr rivojlanish bosqichida chiziqli o‘sadi.
  * Tuproq foydali suvi — FAO-56, 36-misol: 90 / 170 / 120 mm/m.
Ob-havo: Open-Meteo (prognoz va arxiv): et0_fao_evapotranspiration, precipitation_sum.

Yadro sof funksiyalardan iborat; foydalanuvchiga ko‘rinadigan matnlar i18n/ da (app/services/texts.py).
Yagona I/O — fetch_* yordamchilari (Open-Meteo).
"""
from __future__ import annotations

import json
import math
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal, TypedDict

# ------------------------------------------------------------------ parametrlar
CropKey = Literal["paxta", "bugdoy"]
SoilKey = Literal["yengil", "orta", "ogir"]
MethodKey = Literal["egat", "yomgir", "tomchi"]
KcSetKey = Literal["uz", "fao"]
StageKey = Literal["ekilmagan", "boshlangich", "rivojlanish", "orta", "kechki", "tugagan"]
Holat = Literal["bugun", "tez_orada", "kerak_emas", "mavsum_yoq"]


class CropParams(TypedDict):
    stages: tuple[int, int, int, int]   # boshlang‘ich, rivojlanish, o‘rta, kechki (kun)
    zr_max: float                       # maksimal ildiz chuqurligi, m
    p: float                            # stresssiz tugatish ulushi
    h: float                            # o‘rtacha bo‘y, m


class SoilParams(TypedDict):
    taw_per_m: float                    # foydali suv, mm/m


class MethodParams(TypedDict):
    eff: float                          # qo‘llash samaradorligi (tipik, sozlanadi)
    max_net_mm: float | None            # bir martalik netto me’yor


KC_SETS: dict[str, dict[str, tuple[float, float, float]]] = {
    "uz": {"paxta": (0.15, 1.15, 0.45), "bugdoy": (0.26, 1.03, 0.56)},
    "fao": {"paxta": (0.35, 1.175, 0.60), "bugdoy": (0.70, 1.15, 0.325)},
}
CROPS: dict[str, CropParams] = {
    "paxta": CropParams(stages=(30, 50, 60, 55), zr_max=1.0, p=0.65, h=1.2),
    "bugdoy": CropParams(stages=(30, 140, 40, 30), zr_max=1.5, p=0.55, h=1.0),
}
ZR_MIN = 0.20   # boshlang‘ich ildiz chuqurligi, m
SOILS: dict[str, SoilParams] = {
    "yengil": SoilParams(taw_per_m=90),
    "orta": SoilParams(taw_per_m=170),
    "ogir": SoilParams(taw_per_m=120),
}
METHODS: dict[str, MethodParams] = {
    "egat": MethodParams(eff=0.60, max_net_mm=None),
    "yomgir": MethodParams(eff=0.75, max_net_mm=40),
    "tomchi": MethodParams(eff=0.90, max_net_mm=25),
}
MM_TO_M3_HA = 10.0


@dataclass(frozen=True)
class Field:
    crop: str
    soil: str
    method: str
    planting: date
    area_ha: float = 1.0
    lat: float = 40.12
    lon: float = 67.84
    kc_set: str = "uz"
    eff: float | None = None              # foydalanuvchi o‘z samaradorligini kiritsa
    kc_scale: float = 1.0                 # hududiy kalibrlash koeffitsienti (pilotda aniqlanadi)

    def __post_init__(self) -> None:
        if self.crop not in CROPS:
            raise ValueError(f"noma’lum ekin: {self.crop}")
        if self.soil not in SOILS:
            raise ValueError(f"noma’lum tuproq: {self.soil}")
        if self.method not in METHODS:
            raise ValueError(f"noma’lum usul: {self.method}")
        if self.kc_set not in KC_SETS:
            raise ValueError(f"noma’lum Kc to‘plami: {self.kc_set}")
        if self.eff is not None and not 0 < self.eff <= 1:
            raise ValueError("samaradorlik 0 dan katta va 1 dan oshmasligi kerak")
        if self.area_ha <= 0:
            raise ValueError("maydon musbat bo‘lishi kerak")
        if self.kc_scale <= 0:
            raise ValueError("kc_scale musbat bo‘lishi kerak")


@dataclass(frozen=True)
class Day:
    date: date
    et0: float
    rain: float = 0.0
    u2: float | None = None               # 2 m dagi o‘rtacha shamol, m/s (ixtiyoriy)
    rhmin: float | None = None            # minimal nisbiy namlik, % (ixtiyoriy)


# ------------------------------------------------------------------ FAO-56 funksiyalari
def stage_bounds(crop: str) -> tuple[int, int, int, int]:
    """Bosqichlar tugaydigan kunlar (ekilgandan keyin): b1, b2, b3, b4."""
    l1, l2, l3, l4 = CROPS[crop]["stages"]
    return l1, l1 + l2, l1 + l2 + l3, l1 + l2 + l3 + l4


def season_length(crop: str) -> int:
    return stage_bounds(crop)[3]


def adjust_kc(kc_tab: float, u2: float | None, rhmin: float | None, h: float) -> float:
    """FAO-56 62-tenglama: Kc = Kc_tab + [0,04(u2−2) − 0,004(RHmin−45)](h/3)^0,3.
    Chegaralar: 1 ≤ u2 ≤ 6 m/s, 20 ≤ RHmin ≤ 80 %."""
    if u2 is None or rhmin is None:
        return kc_tab
    u2 = min(max(u2, 1.0), 6.0)
    rhmin = min(max(rhmin, 20.0), 80.0)
    return kc_tab + (0.04 * (u2 - 2) - 0.004 * (rhmin - 45)) * float((h / 3) ** 0.3)


def kc_on(fld: Field, das: int, u2: float | None = None, rhmin: float | None = None) -> float:
    """Ekilgandan keyingi kun (das) uchun Kc (FAO-56 chiziqli egri chiziq). Mavsumdan tashqarida 0."""
    ini, mid, end = KC_SETS[fld.kc_set][fld.crop]
    if fld.kc_set == "fao":
        h = CROPS[fld.crop]["h"]
        mid = adjust_kc(mid, u2, rhmin, h)
        if end > 0.45:
            end = adjust_kc(end, u2, rhmin, h)
    b1, b2, b3, b4 = stage_bounds(fld.crop)
    if das < 0 or das >= b4:
        return 0.0
    if das < b1:
        return ini
    if das < b2:
        return ini + (das - b1) / (b2 - b1) * (mid - ini)
    if das < b3:
        return mid
    return mid + (das - b3) / (b4 - b3) * (end - mid)


def stage_of(crop: str, das: int) -> StageKey:
    b1, b2, b3, b4 = stage_bounds(crop)
    if das < 0:
        return "ekilmagan"
    if das < b1:
        return "boshlangich"
    if das < b2:
        return "rivojlanish"
    if das < b3:
        return "orta"
    if das < b4:
        return "kechki"
    return "tugagan"


def root_depth(fld: Field, das: int) -> float:
    """Zr boshlang‘ich bosqichda ZR_MIN, rivojlanishda chiziqli o‘sadi, keyin Zr_max."""
    b1, b2, _, _ = stage_bounds(fld.crop)
    zmax = CROPS[fld.crop]["zr_max"]
    if das <= b1:
        return ZR_MIN
    if das >= b2:
        return zmax
    return ZR_MIN + (das - b1) / (b2 - b1) * (zmax - ZR_MIN)


def taw_raw(fld: Field, das: int) -> tuple[float, float]:
    taw = SOILS[fld.soil]["taw_per_m"] * root_depth(fld, das)
    return taw, CROPS[fld.crop]["p"] * taw


def efficiency(fld: Field) -> float:
    return fld.eff if fld.eff is not None else METHODS[fld.method]["eff"]


def trigger(fld: Field, das: int) -> float:
    """Sug‘orish chegarasi: RAW yoki usulning bir martalik netto me’yori (qaysi kichik bo‘lsa)."""
    _, raw = taw_raw(fld, das)
    m = METHODS[fld.method]["max_net_mm"]
    return min(raw, m) if m else raw


def effective_rain(p_mm: float, et0: float) -> float:
    """Soddalashtirilgan: kichik yomg‘ir (< 0,2·ET0) bug‘lanib ketadi, hisobga olinmaydi."""
    return p_mm if p_mm >= 0.2 * et0 else 0.0


def etc_of(fld: Field, d: Day) -> float:
    return fld.kc_scale * kc_on(fld, (d.date - fld.planting).days, d.u2, d.rhmin) * d.et0


def step_depletion(fld: Field, dr: float, d: Day) -> float:
    """Bir kunlik balans (sug‘orishsiz): Dr ← clamp(Dr + ETc − Pe, 0, TAW)."""
    taw, _ = taw_raw(fld, (d.date - fld.planting).days)
    return min(taw, max(0.0, dr + etc_of(fld, d) - effective_rain(d.rain, d.et0)))


# ------------------------------------------------------------------ mavsum simulyatsiyasi
class SimRow(TypedDict):
    sana: str
    das: int
    bosqich: StageKey
    et0: float
    etc: float
    yomgir: float
    sugorish_mm: float        # brutto berilgan suv
    netto_mm: float           # ildiz zonasiga yetgan suv
    chuqur_mm: float          # ildizdan pastga o‘tgan suv (yo‘qotish)
    tanqislik_mm: float       # kun oxiridagi Dr
    taw_mm: float
    raw_mm: float
    zr_m: float
    stress: bool


class SimResult(TypedDict):
    rows: list[SimRow]
    suv_m3_ga: int
    yoqotish_m3_ga: int
    chuqur_m3_ga: int
    stress_kunlari: int
    sugorishlar: int
    etc_mm: int


def simulate(fld: Field, days: list[Day], start_depletion: float = 0.0,
             fixed_schedule: tuple[int, float] | None = None) -> SimResult:
    """
    fixed_schedule=None    → FAO-56 maslahati bo‘yicha sug‘orish.
    fixed_schedule=(n, mm) → fermer odati: mavsumda har n kunda brutto mm.
    Natija: kunlik qatorlar + jamlar (suv, yo‘qotish, stress kunlari, ETc).
    """
    if fixed_schedule is not None and (fixed_schedule[0] < 1 or fixed_schedule[1] < 0):
        raise ValueError("odat jadvali: n ≥ 1 kun, mm ≥ 0")
    eff = efficiency(fld)
    dr = start_depletion
    rows: list[SimRow] = []
    gross_t = loss_t = deep_t = etc_t = 0.0
    stress = events = 0
    for d in days:
        das = (d.date - fld.planting).days
        taw, raw = taw_raw(fld, das)
        etc = etc_of(fld, d)
        pe = effective_rain(d.rain, d.et0)
        net = gross = 0.0
        in_season = etc > 0
        if fixed_schedule is not None:
            n, mm = fixed_schedule
            if in_season and das % n == 0:
                gross, net = mm, mm * eff
        elif in_season and dr + etc - pe >= trigger(fld, das):
            net = dr + etc - pe
            gross = net / eff
        dr_new = dr - pe - net + etc
        deep = max(0.0, -dr_new)
        dr = min(max(0.0, dr_new), taw)
        is_stress = in_season and dr > raw
        stress += int(is_stress)
        gross_t += gross
        deep_t += deep
        loss_t += deep + (gross - net)
        etc_t += etc
        events += int(gross > 0)
        rows.append(SimRow(sana=d.date.isoformat(), das=das, bosqich=stage_of(fld.crop, das),
                           et0=round(d.et0, 2), etc=round(etc, 2), yomgir=round(d.rain, 1),
                           sugorish_mm=round(gross, 1), netto_mm=round(net, 1),
                           chuqur_mm=round(deep, 1), tanqislik_mm=round(dr, 1),
                           taw_mm=round(taw, 1), raw_mm=round(raw, 1),
                           zr_m=round(root_depth(fld, das), 2), stress=is_stress))
    return SimResult(rows=rows, suv_m3_ga=round(gross_t * MM_TO_M3_HA),
                     yoqotish_m3_ga=round(loss_t * MM_TO_M3_HA),
                     chuqur_m3_ga=round(deep_t * MM_TO_M3_HA),
                     stress_kunlari=stress, sugorishlar=events, etc_mm=round(etc_t))


# ------------------------------------------------------------------ bugungi maslahat
def depletion_since(fld: Field, last_irrigation: date, history: list[Day]) -> float:
    """Oxirgi sug‘orishdan keyin tuproq to‘la (Dr = 0); bugungacha sug‘orishsiz hisob."""
    dr = 0.0
    for d in history:
        if d.date > last_irrigation:
            dr = step_depletion(fld, dr, d)
    return dr


class Advice(TypedDict):
    holat: Holat
    kun: int | None           # necha kundan keyin (0 = bugun)
    netto_mm: float
    m3_ga: int
    m3_jami: int
    zaxira: float | None      # 0..1, ildiz zonasidagi foydali suv ulushi
    bosqich: StageKey
    das: int
    bolib_kun: int | None     # tomchilatishda me’yor katta bo‘lsa, necha kunga bo‘lish
    # "Nega?" uchun dalillar
    oxirgi_sugorish_kun: int
    sarf_mm: float            # so‘nggi kunlardagi ETc yig‘indisi
    sarf_kunlar: int
    yomgir_mm: float          # so‘nggi kunlardagi yomg‘ir
    yomgir3_mm: float         # yaqin 3 kun prognozidagi yomg‘ir
    taw_mm: float
    raw_mm: float
    tanqislik_mm: float
    tarix_yetarli: bool       # ob-havo tarixi oxirgi sug‘orishdan boshlab to‘liqmi


def advice(fld: Field, last_irrigation: date, history: list[Day], forecast: list[Day]) -> Advice:
    """Bugungi maslahat. forecast[0] — bugun. Matnga aylantirish app/services/texts.py da."""
    if not forecast:
        raise ValueError("prognoz bo‘sh")
    today = forecast[0]
    das = (today.date - fld.planting).days
    days_since = (today.date - last_irrigation).days
    covered = days_since <= 1 or (bool(history)
                                  and history[0].date <= last_irrigation + timedelta(days=1))
    out = Advice(holat="mavsum_yoq", kun=None, netto_mm=0.0, m3_ga=0, m3_jami=0, zaxira=None,
                 bosqich=stage_of(fld.crop, das), das=das, bolib_kun=None,
                 oxirgi_sugorish_kun=days_since, sarf_mm=0.0, sarf_kunlar=0, yomgir_mm=0.0,
                 yomgir3_mm=round(sum(x.rain for x in forecast[:3]), 1),
                 taw_mm=0.0, raw_mm=0.0, tanqislik_mm=0.0, tarix_yetarli=covered)
    if kc_on(fld, das) == 0:
        return out
    eff = efficiency(fld)
    dr0 = depletion_since(fld, last_irrigation, history)
    taw0, raw0 = taw_raw(fld, das)
    recent = [d for d in history if d.date > last_irrigation][-7:]
    out["holat"] = "kerak_emas"
    out["zaxira"] = 1 - dr0 / taw0
    out["sarf_mm"] = round(sum(etc_of(fld, d) for d in recent), 1)
    out["sarf_kunlar"] = len(recent)
    out["yomgir_mm"] = round(sum(d.rain for d in recent), 1)
    out["taw_mm"], out["raw_mm"], out["tanqislik_mm"] = round(taw0, 1), round(raw0, 1), round(dr0, 1)
    d = dr0
    for k, day in enumerate(forecast):
        d_das = (day.date - fld.planting).days
        if kc_on(fld, d_das) == 0:
            break
        d = step_depletion(fld, d, day)
        if d >= trigger(fld, d_das):
            m3_ga = round(d / eff * MM_TO_M3_HA)
            mx = METHODS[fld.method]["max_net_mm"]
            out["holat"] = "bugun" if k == 0 else "tez_orada"
            out["kun"], out["netto_mm"] = k, round(d, 1)
            out["m3_ga"], out["m3_jami"] = m3_ga, round(m3_ga * fld.area_ha)
            out["bolib_kun"] = math.ceil(d / mx) if (k == 0 and mx and d > mx * 1.2) else None
            break
    return out


def bar(fraction: float, width: int = 10) -> str:
    """Tuproq suv zaxirasi indikatori: ▰▰▰▰▰▰▱▱▱▱"""
    k = max(0, min(width, round(fraction * width)))
    return "▰" * k + "▱" * (width - k)


# ------------------------------------------------------------------ tizimli yondashuv: uyushma paneli
class DemandDay(TypedDict):
    sana: str
    m3: int
    dalalar: int


def demand_forecast(fields_with_state: list[tuple[Field, date, list[Day]]],
                    forecast: list[Day]) -> list[DemandDay]:
    """
    Suv iste’molchilari uyushmasi / kanal uchun: keyingi kunlarda qaysi kuni qancha suv
    so‘ralishini yig‘adi (har bir dala uchun advice-simulyatsiya). fields_with_state:
    [(Field, last_irrigation, history)]. Bu — dispetcherga suvni oldindan rejalash imkonini beradi.
    """
    by_day = {d.date.isoformat(): 0.0 for d in forecast}
    count = {d.date.isoformat(): 0 for d in forecast}
    for fld, last_irr, hist in fields_with_state:
        dr = depletion_since(fld, last_irr, hist)
        eff = efficiency(fld)
        for day in forecast:
            das = (day.date - fld.planting).days
            if kc_on(fld, das) == 0:
                continue
            dr = step_depletion(fld, dr, day)
            if dr >= trigger(fld, das):
                key = day.date.isoformat()
                by_day[key] += dr / eff * MM_TO_M3_HA * fld.area_ha
                count[key] += 1
                dr = 0.0
    return [DemandDay(sana=k, m3=round(v), dalalar=count[k]) for k, v in by_day.items()]


# ------------------------------------------------------------------ ob-havo
DAILY_VARS = "et0_fao_evapotranspiration,precipitation_sum"


def _get(url: str, timeout: float = 20) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def parse_open_meteo(js: dict[str, Any]) -> list[Day]:
    d = js["daily"]
    return [Day(date=date.fromisoformat(t), et0=float(e or 0.0), rain=float(p or 0.0))
            for t, e, p in zip(d["time"], d["et0_fao_evapotranspiration"], d["precipitation_sum"],
                               strict=True)]


def forecast_url(lat: float, lon: float, past_days: int = 30, forecast_days: int = 7) -> str:
    return ("https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.2f}&longitude={lon:.2f}&daily={DAILY_VARS}"
            f"&timezone=Asia%2FTashkent&past_days={past_days}&forecast_days={forecast_days}")


def archive_url(lat: float, lon: float, start: date, end: date) -> str:
    return ("https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat:.2f}&longitude={lon:.2f}&start_date={start}&end_date={end}"
            f"&daily={DAILY_VARS}&timezone=Asia%2FTashkent")


def split_history(days: list[Day], today: date) -> tuple[list[Day], list[Day]]:
    return [x for x in days if x.date < today], [x for x in days if x.date >= today]


def fetch_weather(lat: float, lon: float, past_days: int = 30,
                  forecast_days: int = 7) -> tuple[list[Day], list[Day]]:
    """Prognoz API: o‘tgan kunlar + 7 kunlik prognoz. (history, forecast) qaytaradi."""
    days = parse_open_meteo(_get(forecast_url(lat, lon, past_days, forecast_days)))
    return split_history(days, date.today())


def fetch_archive(lat: float, lon: float, start: date, end: date) -> list[Day]:
    """Arxiv API (demo rejim va mavsum simulyatori uchun)."""
    return parse_open_meteo(_get(archive_url(lat, lon, start, end)))
