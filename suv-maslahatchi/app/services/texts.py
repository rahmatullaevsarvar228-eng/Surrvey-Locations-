"""i18n yuklash va engine natijasini foydalanuvchi matniga aylantirish."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.suv_engine import Advice, SimResult, bar

I18N_DIR = Path(__file__).resolve().parents[2] / "i18n"
LANGS = ("uz", "ru")


@lru_cache
def load(lang: str) -> dict[str, Any]:
    if lang not in LANGS:
        lang = "uz"
    data: dict[str, Any] = json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    return data


def t(lang: str, key: str, **kw: Any) -> str:
    """t("uz", "advice.bugun", crop=...) — topilmasa, o‘zbekchaga qaytadi, keyin kalitning o‘zi."""
    for lg in (lang, "uz"):
        node: Any = load(lg)
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, str):
            return node.format(**kw) if kw else node
    return key


def _num(x: float) -> str:
    return f"{x:g}"


def _pct(x: float) -> str:
    return f"{x:.0%}"


def advice_text(a: Advice, crop: str, area_ha: float, lang: str = "uz") -> str:
    """Telegram / ekran uchun asosiy maslahat matni."""
    crop_name = t(lang, f"crop.{crop}")
    if a["holat"] == "mavsum_yoq":
        return t(lang, "advice.mavsum_yoq", crop=crop_name, stage=t(lang, f"stage.{a['bosqich']}"))
    z = a["zaxira"] or 0.0
    common = dict(crop=crop_name, bar=bar(z), zaxira=_pct(z), m3_ga=a["m3_ga"])
    lines: list[str] = []
    if a["holat"] == "bugun":
        lines.append(t(lang, "advice.bugun", area=_num(area_ha), m3_jami=a["m3_jami"], **common))
        if a["bolib_kun"]:
            lines.append(t(lang, "advice.split", n=a["bolib_kun"]))
    elif a["holat"] == "tez_orada":
        lines.append(t(lang, "advice.tez_orada", k=a["kun"], **common))
    else:
        lines.append(t(lang, "advice.kerak_emas", **common))
        if a["yomgir3_mm"] >= 5:
            lines.append(t(lang, "advice.rain3", mm=f"{a['yomgir3_mm']:.0f}"))
    if not a["tarix_yetarli"]:
        lines.append(t(lang, "advice.history_gap"))
    return "\n".join(lines)


def why_text(a: Advice, crop: str, lang: str = "uz") -> str:
    """«Nega?» — maslahat qaysi raqamlardan kelib chiqqanini tushuntiradi."""
    if a["holat"] == "mavsum_yoq":
        return t(lang, "advice.why_model")
    z = a["zaxira"] or 0.0
    body = t(lang, "advice.why", days=a["oxirgi_sugorish_kun"], n=a["sarf_kunlar"],
             crop_l=t(lang, f"crop.{crop}").lower(), used=f"{a['sarf_mm']:.0f}",
             rain=f"{a['yomgir_mm']:.0f}", taw=f"{a['taw_mm']:.0f}", raw=f"{a['raw_mm']:.0f}",
             dr=f"{a['tanqislik_mm']:.0f}", bar=bar(z), zaxira=_pct(z),
             stage=t(lang, f"stage.{a['bosqich']}"))
    return f"{body}\n{t(lang, 'advice.why_model')}"


def week_text(plan: SimResult, crop: str, area_ha: float, lang: str = "uz") -> str:
    """/hafta: har kun — sug‘orish (m³/ga) yoki kutish (zaxira foizi)."""
    wd: list[str] = load(lang)["bot"]["weekdays"]
    lines = [t(lang, "bot.week_title", crop=t(lang, f"crop.{crop}"), area=_num(area_ha))]
    total = 0.0
    n = 0
    for r in plan["rows"]:
        d = date.fromisoformat(r["sana"])
        day = f"{d:%d.%m} {wd[d.weekday()]}"
        if r["etc"] == 0:
            lines.append(t(lang, "bot.week_off", day=day))
        elif r["sugorish_mm"] > 0:
            m3 = round(r["sugorish_mm"] * 10)
            total += m3 * area_ha
            n += 1
            lines.append(t(lang, "bot.week_irrigate", day=day, m3=m3))
        else:
            lines.append(t(lang, "bot.week_wait", day=day, zaxira=_pct(r["zaxira"])))
    if n:
        lines.append(t(lang, "bot.week_total", m3=round(total), n=n))
    return "\n".join(lines)
