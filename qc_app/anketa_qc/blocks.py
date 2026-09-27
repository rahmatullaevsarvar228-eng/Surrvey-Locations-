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


NAME_HINTS = ("тип", "type", "tur", "вид", "техн", "texn", "techn", "задани", "vazifa", "topshiriq",
              "запис", "формат", "video", "видео")
# Колонка с файлом видео/фото по заданию: если заполнена — это техническая запись.
MEDIA_NAME_HINTS = ("видео", "video", "техн", "texn", "задани", "vazifa", "topshiriq", "reklama yo", "нет рекламы")


def technical_candidates(raw):
    """Колонки, похожие на признак технической записи:
      - «тип записи: Интервью / Техническое задание (видео)» — режим values;
      - колонка файла видео по заданию, заполненная только у части строк —
        режим filled (заполнено → техническая запись).
    Возвращает [{"col", "mode", "values", "n", "sure"}]; sure — в названии
    колонки есть явный признак, такую можно применять автоматически."""
    out = []
    n_rows = max(len(raw), 1)
    for c in raw.columns:
        s = raw[c].dropna()
        if s.empty:
            continue
        name = str(c).lower()
        vals = s.astype(str).str.strip()
        vals = vals[vals != ""]
        uniq = vals.value_counts()
        name_hint = any(h in name for h in NAME_HINTS)
        if 2 <= len(uniq) <= 8:
            hits = [v for v in uniq.index if any(h in v.lower() for h in TECH_HINTS)]
            if hits and len(hits) < len(uniq):
                out.append({"col": str(c), "mode": "values", "values": hits, "n": int(uniq[hits].sum()),
                            "sure": name_hint, "score": int(uniq[hits].sum()) + (10_000 if name_hint else 0)})
                continue
        share = len(vals) / n_rows
        if any(h in name for h in MEDIA_NAME_HINTS) and 0 < share < 0.6 and len(uniq) > 0.5 * len(vals):
            # почти все значения разные (имена файлов) и заполнено не у всех
            out.append({"col": str(c), "mode": "filled", "values": [], "n": int(len(vals)),
                        "sure": True, "score": int(len(vals)) + 5_000})
    out.sort(key=lambda x: -x["score"])
    for x in out:
        x.pop("score")
    return out


def suggest_technical(raw, limit=3):
    return technical_candidates(raw)[:limit]


def resolve_technical(raw, cfg):
    """(маска технических записей, описание откуда она взялась или None).

    Если руководитель сам выбрал колонку — берём её. Иначе (auto, по
    умолчанию) — первую «уверенную» подсказку: колонку типа записи или
    колонку видео по заданию. Колонку ответа вроде «Где видели рекламу:
    видео в интернете» автоматически не берём — у неё нет признака в
    названии."""
    t = cfg.get("technical") or {}
    col, mode = t.get("col"), t.get("mode") or "values"
    values = [str(v).strip().lower() for v in t.get("values") or [] if str(v).strip()]
    auto = False
    if not col and t.get("auto", True):
        sure = [x for x in technical_candidates(raw) if x["sure"]]
        if sure:
            col, mode, values, auto = sure[0]["col"], sure[0]["mode"], [v.lower() for v in sure[0]["values"]], True
    if not col or col not in raw.columns or (mode == "values" and not values):
        return pd.Series(False, index=raw.index), None
    if mode == "filled":
        mask = raw[col].map(lambda v: pd.notna(v) and str(v).strip() != "")
    else:
        mask = raw[col].map(lambda v: str(v).strip().lower() in values if pd.notna(v) else False)
    mask = mask.astype(bool)
    return mask, {"col": str(col), "mode": mode, "values": sorted({str(v) for v in raw.loc[mask, col].dropna()})[:5]
                  if mode == "values" else [], "n": int(mask.sum()), "auto": auto}


def technical_mask(raw, cfg):
    return resolve_technical(raw, cfg)[0]
