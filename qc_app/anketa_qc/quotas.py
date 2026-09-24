# -*- coding: utf-8 -*-
"""Квоты выборки: план по ячейкам (город × пол × возраст × …) против того,
что реально засчитано.

Настройки проекта ("quotas"):
    by_city  — делить ли план по городам (колонка города из «Колонок»);
    dims     — [{"label": "Пол", "column": "Пол респондента", "bins": ""},
                {"label": "Возраст", "column": "Сколько вам полных лет?", "bins": "18-24,25-34,35+"}]
               bins — возрастные/числовые интервалы через запятую; пусто — значение как есть;
    plan     — [{"keys": {"Город": "Ташкент", "Пол": "Женский", ...}, "target": 50}, ...]

Считаются только завершённые интервью (скринауты в квоту не идут).
Засчитано = принято руководителем или без замечаний системы; брак и
нерешённые подозрительные в «засчитано» не входят — сразу видно, сколько
добирать взамен.
"""
import re

import numpy as np
import pandas as pd

from .engine import clean_str

CITY = "Город"


def parse_bins(text):
    """«18-24, 25-34, 60+» → [(18, 24, '18-24'), (25, 34, '25-34'), (60, inf, '60+')]."""
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)", part)
        if m:
            out.append((float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")), part))
            continue
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*\+", part)
        if m:
            out.append((float(m.group(1).replace(",", ".")), np.inf, part))
            continue
        raise ValueError(f"Непонятный интервал «{part}». Пример: 18-24, 25-34, 60+")
    return out


def _bin_value(v, bins):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    for lo, hi, label in bins:
        if lo <= x <= hi:
            return label
    return None


def dim_labels(cfg):
    q = cfg.get("quotas") or {}
    labels = [CITY] if q.get("by_city", True) else []
    return labels + [d["label"] for d in q.get("dims") or [] if d.get("label") and d.get("column")]


def cell_values(result, cfg):
    """Для каждой завершённой анкеты — значения всех измерений квоты.
    Возвращает DataFrame (index = pos) с колонками-измерениями."""
    q = cfg.get("quotas") or {}
    df, raw = result["df"], result["raw"]
    done = df[df["completed"]].set_index("pos")
    out = pd.DataFrame(index=done.index)
    if q.get("by_city", True):
        out[CITY] = done["city"]
    for d in q.get("dims") or []:
        col, label = d.get("column"), d.get("label")
        if not col or not label or col not in raw.columns:
            continue
        bins = parse_bins(d.get("bins"))
        vals = raw.loc[out.index, col]
        out[label] = vals.map(lambda v: _bin_value(v, bins)) if bins else vals.map(clean_str)
    return out


def anketa_state(result, decisions_by_pos):
    """pos → 'ok' (засчитано) / 'brak' / 'pending' (подозрительная без решения или на перезвон)."""
    state = {}
    for x in result["df"].itertuples():
        d = (decisions_by_pos.get(x.pos) or {}).get("decision")
        if d == "Брак":
            state[x.pos] = "brak"
        elif d == "Принять" or (not d and not x.is_defect):
            state[x.pos] = "ok"
        else:
            state[x.pos] = "pending"
    return state


def compute(result, cfg, decisions_by_pos):
    q = cfg.get("quotas") or {}
    labels = dim_labels(cfg)
    plan = [p for p in q.get("plan") or [] if isinstance(p.get("keys"), dict)]
    if not labels or (not plan and not q.get("dims")):
        return {"enabled": False}
    cells = cell_values(result, cfg)
    state = anketa_state(result, decisions_by_pos)
    cells["_state"] = [state.get(p, "pending") for p in cells.index]
    counts = {}
    for key, g in cells.groupby([cells[lbl].fillna("—") for lbl in labels], dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        vc = g["_state"].value_counts()
        counts[tuple(str(k) for k in key)] = {"total": len(g), "ok": int(vc.get("ok", 0)),
                                              "pending": int(vc.get("pending", 0)), "brak": int(vc.get("brak", 0))}
    rows, seen = [], set()
    for p in plan:
        key = tuple(str(p["keys"].get(lbl, "")).strip() for lbl in labels)
        seen.add(key)
        c = counts.get(key, {"total": 0, "ok": 0, "pending": 0, "brak": 0})
        target = int(p.get("target") or 0)
        left = target - c["ok"]
        # GREEN — ячейка набрана, RED — перебор (лишние анкеты), YELLOW — ещё добирать
        status = "RED" if left < 0 else ("GREEN" if target and left == 0 else "YELLOW")
        rows.append({**dict(zip(labels, key)), "План": target, "Засчитано": c["ok"], "Под вопросом": c["pending"],
                     "Брак": c["brak"], "Всего": c["total"], "Осталось": max(left, 0),
                     "Перебор": max(-left, 0), "%": round(c["ok"] / target * 100) if target else None,
                     "Статус": status})
    extra = [{**dict(zip(labels, k)), **v} for k, v in counts.items() if k not in seen]
    total_plan = sum(r["План"] for r in rows)
    total_ok = sum(min(r["Засчитано"], r["План"]) for r in rows)
    return {
        "enabled": True, "labels": labels, "rows": rows,
        "outside_plan": sorted(extra, key=lambda r: -r["total"]),
        "summary": {"plan": total_plan, "ok": sum(r["Засчитано"] for r in rows),
                    "left": sum(r["Осталось"] for r in rows), "over": sum(r["Перебор"] for r in rows),
                    "pct": round(total_ok / total_plan * 100) if total_plan else 0,
                    "cells_done": sum(1 for r in rows if r["Статус"] == "GREEN"), "cells": len(rows)},
    }


def template(result, cfg, existing=None):
    """Строки плана из того, что уже есть в данных (плюс уже заданные
    цели сохраняются) — чтобы не вбивать город × пол × возраст руками."""
    labels = dim_labels(cfg)
    cells = cell_values(result, cfg)
    old = {tuple(str(p["keys"].get(lbl, "")) for lbl in labels): p.get("target", 0) for p in existing or []}
    keys = set(old)
    if len(cells):
        for key in cells[labels].fillna("—").astype(str).drop_duplicates().itertuples(index=False):
            keys.add(tuple(key))
    return [{"keys": dict(zip(labels, k)), "target": int(old.get(k, 0) or 0)} for k in sorted(keys)]


def plan_from_frame(df, labels):
    """План из Excel: колонки-измерения (как названы в настройках квот) и «План»."""
    cols = {str(c).strip().lower(): c for c in df.columns}
    target_col = next((cols[k] for k in cols if k in ("план", "plan", "квота", "target", "цель")), None)
    if target_col is None:
        raise ValueError("В файле нужна колонка «План»")
    missing = [lbl for lbl in labels if lbl.lower() not in cols]
    if missing:
        raise ValueError("В файле нет колонок: " + ", ".join(missing))
    plan = []
    for _, r in df.iterrows():
        try:
            target = int(float(str(r[target_col]).replace(",", ".")))
        except ValueError:
            continue
        keys = {lbl: re.sub(r"^г\.\s*", "", clean_str(r[cols[lbl.lower()]]) or "") for lbl in labels}
        plan.append({"keys": keys, "target": target})
    if not plan:
        raise ValueError("В файле нет строк с числом в колонке «План»")
    return plan


def plan_from_geo(cfg):
    """План по городам из плана GPS-точек (поле total, как в geo_app.py)."""
    plan = (cfg.get("geo") or {}).get("plan") or {}
    return [{"keys": {CITY: city}, "target": int(data["total"])} for city, data in plan.items() if data.get("total")]
