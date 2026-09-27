# -*- coding: utf-8 -*-
"""Работа по дням: сколько анкет каждый интервьюер сделал в каждый день,
сколько из них засчитано (без брака) и выполнил ли он дневную норму.

Норма (например 6 анкет в день) задаётся руководителем в настройках
проекта: {"daily": {"min": 6, "team": ["Inter 01", ...]}}. Засчитываются
только интервью без брака: брак в норму не идёт. Технические записи не
считаются. Список команды необязателен — он нужен, чтобы увидеть и тех,
кто за весь период не прислал ни одной анкеты.
"""
import pandas as pd

from .review import final_state

OK, LOW, NONE = "GREEN", "YELLOW", "RED"


def table(result, cfg, decisions_by_pos, filters=None):
    """(строки по интервьюерам, дни, сводка по дням)."""
    df = result["df"]
    dec = {p: (d or {}).get("decision") for p, d in decisions_by_pos.items()}
    iv = df[~df["technical"] & df["start"].notna()].copy()
    for key in ("region", "city", "inter"):
        v = (filters or {}).get(key)
        if v:
            iv = iv[iv[key] == v]
    iv["state"] = [final_state(False, d, w, dec.get(p)) for d, w, p in zip(iv["is_defect"], iv["is_warning"], iv["pos"])]
    iv["day"] = iv["start"].dt.normalize()
    norm = int((cfg.get("daily") or {}).get("min") or 0)
    days = sorted(iv["day"].unique())
    team = [str(x).strip() for x in (cfg.get("daily") or {}).get("team") or [] if str(x).strip()]
    inters = sorted(set(iv["inter"].dropna()) | (set(team) if not (filters or {}).get("city") and not (filters or {}).get("region") else set()),
                    key=str)
    grp = iv.groupby(["inter", "day"])
    total = grp.size()
    brak = grp["state"].apply(lambda s: int((s == "brak").sum()))
    rows = []
    for inter in inters:
        cells, worked, low = [], 0, 0
        city = iv.loc[iv["inter"] == inter, "city"]
        for d in days:
            n = int(total.get((inter, d), 0))
            b = int(brak.get((inter, d), 0))
            ok = n - b
            st = NONE if n == 0 else (LOW if norm and ok < norm else OK)
            worked += n > 0
            low += st == LOW
            cells.append({"n": n, "brak": b, "ok": ok, "status": st})
        all_ok = sum(c["ok"] for c in cells)
        rows.append({"inter": inter, "city": city.mode().iloc[0] if len(city) else "—", "cells": cells,
                     "days_worked": worked, "days_low": low, "days_off": len(days) - worked,
                     "ok": all_ok, "brak": sum(c["brak"] for c in cells),
                     "avg": round(all_ok / worked, 1) if worked else 0.0})
    per_day = []
    for k, d in enumerate(days):
        cs = [r["cells"][k] for r in rows]
        per_day.append({"day": d, "worked": sum(1 for c in cs if c["n"]), "team": len(rows),
                        "norm_ok": sum(1 for c in cs if c["status"] == OK), "low": sum(1 for c in cs if c["status"] == LOW),
                        "off": sum(1 for c in cs if c["status"] == NONE),
                        "ok": sum(c["ok"] for c in cs), "brak": sum(c["brak"] for c in cs)})
    return rows, days, per_day, norm


def frame(result, cfg, decisions_by_pos):
    """Таблица для Excel: интервьюер × день, в ячейке «засчитано (брак)»."""
    rows, days, _, norm = table(result, cfg, decisions_by_pos)
    out = []
    for r in rows:
        rec = {"Интервьюер": r["inter"], "Город": r["city"]}
        for d, c in zip(days, r["cells"]):
            rec[pd.Timestamp(d).strftime("%d.%m")] = (f"{c['ok']}" + (f" (+{c['brak']} брак)" if c["brak"] else "")) if c["n"] else "—"
        rec.update({"Дней работал": r["days_worked"], "Не работал": r["days_off"],
                    f"Дней ниже нормы ({norm})" if norm else "Дней ниже нормы": r["days_low"],
                    "Засчитано всего": r["ok"], "Брак": r["brak"], "В среднем в день": r["avg"]})
        out.append(rec)
    return out
