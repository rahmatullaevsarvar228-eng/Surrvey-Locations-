# -*- coding: utf-8 -*-
"""Блоки анкеты и технические записи.

Блок — часть анкеты (например «Знание банков», «Реклама», «Паспортичка»).
Нужен, чтобы у каждого брака было видно, в каком именно блоке ошибка.
Блоки берутся:
  1. из настроек проекта: [{"name", "start"}] — блок начинается с колонки
     start и идёт до начала следующего блока (в порядке колонок выгрузки);
  2. иначе — из групп Kobo в заголовках («grp_bank/q1» → «grp bank»).
Проблемы, которые не относятся к вопросам (время, устройство, GPS), идут
в служебные разделы.

Техническая запись — анкета, где интервьюер не проводит опрос, а выполняет
задание (например, снимает видео, что рядом нет рекламы). Её не проверяют
как интервью: длительность, интервалы, «конвейер», зондаж и правила к ней
не применяются, в квоты она не идёт.
"""
import re

import pandas as pd

TIME = "Время интервью"
DEVICE = "Устройство и интервьюер"
GPS = "GPS и место опроса"
CONTACTS = "Контакты респондента"
OPEN = "Открытые вопросы"
LOGIC = "Логика анкеты"

CODE_AREA = {
    "no_device": DEVICE, "device_multi_inter": DEVICE, "inter_multi_device": DEVICE,
    "too_long": TIME, "too_short": TIME, "start_gap": TIME, "no_rest": TIME, "conveyor": TIME,
    "overlap": TIME, "mass_open": TIME, "night": TIME,
    "no_gps": GPS, "geo_far": GPS, "geo_cluster": GPS, "geo_same": GPS, "geo_jump": GPS, "geo_city": GPS,
    "probe_low_avg": OPEN,
}


def _pretty_group(prefix):
    name = prefix.rsplit("/", 1)[-1]
    name = re.sub(r"^(grp|group|gr|block|blok)[_\- ]*", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").strip()
    return name[:1].upper() + name[1:] if name else prefix


def build_sections(columns, cfg):
    """[{"name", "columns", "required", "grid"}] в порядке анкеты."""
    columns = [str(c) for c in columns]
    configured = [s for s in cfg.get("sections") or [] if s.get("name") and s.get("start") in columns]
    if configured:
        pos = {c: i for i, c in enumerate(columns)}
        configured = sorted(configured, key=lambda s: pos[s["start"]])
        out = []
        for k, s in enumerate(configured):
            a = pos[s["start"]]
            b = pos[configured[k + 1]["start"]] if k + 1 < len(configured) else len(columns)
            out.append({"name": s["name"].strip(), "columns": columns[a:b],
                        "required": bool(s.get("required")), "grid": bool(s.get("grid"))})
        return out
    # группы Kobo в заголовках
    out = []
    for c in columns:
        if "/" not in c:
            continue
        name = _pretty_group(c.rsplit("/", 1)[0])
        if out and out[-1]["name"] == name:
            out[-1]["columns"].append(c)
        else:
            out.append({"name": name, "columns": [c], "required": False, "grid": False, "auto": True})
    return out


def section_of(sections):
    m = {}
    for s in sections:
        for c in s["columns"]:
            m.setdefault(c, s["name"])
    return m


def issue_block(code, text, cfg, sec_of):
    """Блок анкеты, к которому относится проблема."""
    if code in CODE_AREA:
        return CODE_AREA[code]
    mapping = cfg["mapping"]
    if code in ("dup_phone", "dup_name"):
        col = mapping.get("phone" if code == "dup_phone" else "name")
        return sec_of.get(col) or CONTACTS
    if code in ("block_empty", "grid_same"):
        return text.split("»")[0].split("«")[-1] if "«" in text else LOGIC
    if code == "probe_depth":
        label = text.split(":")[0]
        for b in cfg["probing"].get("blocks") or []:
            if (b.get("label") or "Блок") == label:
                for c in b.get("columns") or []:
                    if c in sec_of:
                        return sec_of[c]
        return label or OPEN
    if code.startswith("rule:"):
        name = code[5:]
        rule = next((r for r in cfg.get("rules") or [] if (r.get("name") or "").strip() == name), None)
        if rule:
            for c in (rule.get("then_col"), rule.get("if_col")):
                if c in sec_of:
                    return sec_of[c]
        return LOGIC
    return LOGIC


# ─────────────────────────────────────────────────────────────────────────
# Технические записи
# ─────────────────────────────────────────────────────────────────────────
TECH_HINTS = ("тех", "texn", "techn", "видео", "video", "фото", "photo", "задани", "vazifa", "topshiriq",
              "съёмк", "съемк", "suratga", "ролик")


def technical_mask(raw, cfg):
    t = cfg.get("technical") or {}
    col, values = t.get("col"), [str(v).strip().lower() for v in t.get("values") or [] if str(v).strip()]
    if not col or col not in raw.columns or not values:
        return pd.Series(False, index=raw.index)
    return raw[col].map(lambda v: str(v).strip().lower() in values if pd.notna(v) else False).astype(bool)


def suggest_technical(raw, limit=3):
    """Колонки, похожие на «тип записи: интервью / техническое задание».
    Возвращает [{"col", "values", "n"}] — для подсказки в настройке."""
    out = []
    for c in raw.columns:
        s = raw[c].dropna()
        if s.empty:
            continue
        vals = s.astype(str).str.strip()
        uniq = vals.value_counts()
        if not 2 <= len(uniq) <= 8:
            continue
        hits = [v for v in uniq.index if any(h in v.lower() for h in TECH_HINTS)]
        if not hits or len(hits) == len(uniq):
            continue
        n = int(uniq[hits].sum())
        name_hint = any(h in str(c).lower() for h in TECH_HINTS + ("тип", "type", "tur", "вид"))
        out.append({"col": str(c), "values": hits, "n": n, "score": n + (10_000 if name_hint else 0)})
    out.sort(key=lambda x: -x["score"])
    for x in out:
        x.pop("score")
    return out[:limit]
