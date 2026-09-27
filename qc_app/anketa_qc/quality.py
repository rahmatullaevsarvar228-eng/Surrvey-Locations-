# -*- coding: utf-8 -*-
"""Проверки из международной практики контроля качества опросов.

1. Почти одинаковые анкеты («percent match», Kuriakose & Robbins, 2016 —
   метод Pew Research и Всемирного банка): у каждой анкеты ищется самая
   похожая другая анкета. Если совпадает 85%+ ответов — вероятна копия.
2. Необычные ответы интервьюера: распределение ответов его респондентов
   сильно отличается от остальных, много «не знаю», слишком одинаковые
   ответы у разных респондентов (интервьюер «придумывает» респондентов).
3. Время по блокам: если в форме Kobo есть поля-отметки времени (calculate
   с now() в начале блоков), считаем, сколько занял каждый блок, и отмечаем
   блоки, пройденные намного быстрее обычного (вопросы не зачитывали).
"""
import re

import numpy as np
import pandas as pd

META = re.compile(r"^(_|start$|end$|today$|deviceid$|subscriberid$|simserial$|phonenumber$|username$|"
                  r"audit|instanceid|meta/|__version__|formhub|источник$)", re.IGNORECASE)
GPS_PART = re.compile(r"(_latitude|_longitude|_altitude|_precision|geopoint|широта|долгота|kenglik|uzunlik)",
                      re.IGNORECASE)


def _norm(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().lower()
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s or None


def answer_columns(raw, df, cfg):
    # raw — таблица в том же порядке строк, что и df (raw_sorted движка)
    """Содержательные вопросы анкеты: без служебных полей, координат,
    телефона/ФИО, дат и почти уникального свободного текста."""
    from .blocks import TECH_SHEET_COL
    skip = {c for c in cfg["mapping"].values() if c} | {TECH_SHEET_COL}
    for key in ("technical", "rejected"):
        col = (cfg.get(key) or {}).get("col")
        if col:
            skip.add(col)
    base = raw.loc[df.index[~df["technical"] & ~df["rejected"]]]   # raw выровнен с df по строкам
    n = max(len(base), 1)
    out = []
    for c in raw.columns:
        name = str(c)
        if c in skip or META.search(name) or GPS_PART.search(name):
            continue
        col = base[c]
        filled = col.notna() & (col.astype(str).str.strip() != "")
        if filled.sum() < 0.3 * n:
            continue
        vals = col[filled]
        if pd.api.types.is_datetime64_any_dtype(vals) or _looks_like_time(vals):
            continue
        if vals.nunique() > 0.9 * len(vals) and len(vals) > 20:
            continue                          # ID, свободный текст — у всех разное
        out.append(c)
    return out


def _looks_like_time(vals):
    sample = vals.astype(str).head(30)
    return sample.str.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}").mean() > 0.8


# ─────────────────────────────────────────────────────────────────────────
# 1. Почти одинаковые анкеты
# ─────────────────────────────────────────────────────────────────────────
def near_duplicates(df, raw_sorted, cols, threshold=0.85, min_questions=15):
    """{индекс строки df: (доля совпадений, индекс самой похожей, сравнено вопросов)}
    для анкет, у которых самая похожая совпадает ≥ threshold."""
    rows = np.flatnonzero((~df["technical"] & ~df["rejected"]).to_numpy())
    if len(rows) < 2 or len(cols) < min_questions:
        return {}
    codes = np.full((len(rows), len(cols)), -1, dtype=np.int32)
    for j, c in enumerate(cols):
        vals = raw_sorted[c].iloc[rows].map(_norm)
        cat, uniq = pd.factorize(vals, use_na_sentinel=True)
        codes[:, j] = cat
    valid = codes >= 0
    out = {}
    chunk = max(1, 4_000_000 // max(len(rows) * len(cols), 1))
    for a in range(0, len(rows), chunk):
        A, VA = codes[a:a + chunk], valid[a:a + chunk]
        both = VA[:, None, :] & valid[None, :, :]
        same = both & (A[:, None, :] == codes[None, :, :])
        n_both = both.sum(axis=2)
        ratio = np.where(n_both >= min_questions, same.sum(axis=2) / np.maximum(n_both, 1), 0.0)
        for k in range(len(A)):
            ratio[k, a + k] = 0.0                # сама с собой
        best = ratio.argmax(axis=1)
        for k, b in enumerate(best):
            r = ratio[k, b]
            if r >= threshold:
                out[int(rows[a + k])] = (float(r), int(rows[b]), int(n_both[k, b]))
    return out


# ─────────────────────────────────────────────────────────────────────────
# 2. Необычные ответы интервьюера
# ─────────────────────────────────────────────────────────────────────────
def _chi2_sf(x, k):
    """P(χ²_k ≥ x), приближение Уилсона–Хилферти (без scipy)."""
    import math
    if k <= 0:
        return 1.0
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return 0.5 * math.erfc(z / math.sqrt(2))


def answer_patterns(df, raw_sorted, cols, answer_filter, min_n=15, tvd_limit=0.3, alpha=0.001, min_score=0.6):
    """[{inter, city, n, score, notes: [...]}] — интервьюеры, у чьих
    респондентов ответы заметно отличаются от остальных."""
    base = df[df["completed"] & df["inter"].notna()]
    if len(base) < 2 * min_n:
        return []
    cat_cols = []
    for c in cols:
        v = raw_sorted.loc[base.index, c].map(_norm)
        k = v.nunique()
        if 2 <= k <= 12 and v.notna().mean() >= 0.5:
            cat_cols.append(c)
    out = []
    inters = base["inter"].value_counts()
    for inter, n in inters.items():
        if n < min_n:
            continue
        mine = base.index[base["inter"] == inter]
        rest = base.index[base["inter"] != inter]
        if len(rest) < 2 * min_n:
            continue
        notes, score = [], 0.0
        modal_mine, modal_rest = [], []
        for c in cat_cols:
            vm = raw_sorted.loc[mine, c].map(_norm).dropna()
            vr = raw_sorted.loc[rest, c].map(_norm).dropna()
            if len(vm) < min_n or len(vr) < 2 * min_n:
                continue
            pm, pr = vm.value_counts(normalize=True), vr.value_counts(normalize=True)
            allk = pm.index.union(pr.index)
            diff = (pm.reindex(allk, fill_value=0) - pr.reindex(allk, fill_value=0))
            tvd = 0.5 * diff.abs().sum()
            modal_mine.append(pm.iloc[0])
            modal_rest.append(pr.iloc[0])
            # отличие должно быть и заметным, и неслучайным: χ² против
            # распределения остальных, с поправкой на число вопросов
            exp = pr.reindex(allk, fill_value=0) * len(vm)
            obs = vm.value_counts().reindex(allk, fill_value=0)
            ok = exp > 0
            chi2 = float((((obs - exp) ** 2)[ok] / exp[ok]).sum()) + float(obs[~ok].sum()) * 10
            p = _chi2_sf(chi2, max(int(ok.sum()) - 1, 1))
            if tvd >= tvd_limit and p < alpha / max(len(cat_cols), 1):
                opt = diff.abs().idxmax()
                raw_opt = raw_sorted.loc[mine.union(rest), c].dropna()
                from .engine import clean_str
                label = next((clean_str(x) for x in raw_opt if _norm(x) == opt), opt)
                notes.append((tvd, f"«{c}»: ответ «{label}» — у него {pm.get(opt, 0) * 100:.0f}%, "
                                   f"у остальных {pr.get(opt, 0) * 100:.0f}%"))
                score += tvd
        # слишком одинаковые ответы у разных респондентов
        if len(modal_mine) >= 5:
            mm, mr = float(np.mean(modal_mine)), float(np.mean(modal_rest))
            if mm - mr >= 0.2:
                notes.append((mm - mr, f"ответы его респондентов слишком похожи друг на друга: самый частый "
                                       f"вариант в среднем у {mm * 100:.0f}% (у остальных {mr * 100:.0f}%)"))
                score += mm - mr
        # «не знаю» / отказы
        if cols:
            def dk_share(idx):
                vals = raw_sorted.loc[idx, cols].stack()
                vals = vals[vals.astype(str).str.strip() != ""]
                return float((~vals.map(answer_filter.is_valid)).mean()) if len(vals) else 0.0
            dm, dr = dk_share(mine), dk_share(rest)
            if dm >= 0.15 and dm >= 2 * dr:
                notes.append((dm, f"много «не знаю»/отказов: {dm * 100:.0f}% ответов (у остальных {dr * 100:.0f}%)"))
                score += dm
        # одно случайное отклонение на маленькой выборке — не сигнал
        if notes and score >= min_score:
            notes.sort(key=lambda x: -x[0])
            city = base.loc[mine, "city"].mode()
            out.append({"inter": inter, "city": city.iloc[0] if len(city) else "—", "n": int(n),
                        "score": round(score, 2), "notes": [t for _, t in notes[:5]], "n_notes": len(notes)})
    out.sort(key=lambda r: -r["score"])
    return out


# ─────────────────────────────────────────────────────────────────────────
# 3. Время по блокам
# ─────────────────────────────────────────────────────────────────────────
def timestamp_columns(raw_sorted, df, cfg):
    """Колонки-отметки времени внутри анкеты (Kobo calculate now()),
    упорядоченные по ходу анкеты."""
    from .engine import parse_datetime
    skip = {c for c in cfg["mapping"].values() if c}
    iv = df[~df["technical"] & ~df["rejected"] & df["start"].notna() & df["end"].notna()]
    if len(iv) < 5:
        return []
    found = []
    for c in raw_sorted.columns:
        if c in skip or GPS_PART.search(str(c)) or str(c).startswith("_"):
            continue
        col = raw_sorted.loc[iv.index, c]
        if col.notna().mean() < 0.5:
            continue
        if not (pd.api.types.is_datetime64_any_dtype(col) or _looks_like_time(col.dropna())):
            continue
        ts = parse_datetime(col)
        inside = (ts >= iv["start"] - pd.Timedelta(minutes=1)) & (ts <= iv["end"] + pd.Timedelta(minutes=1))
        if ts.notna().mean() >= 0.5 and inside[ts.notna()].mean() >= 0.8:
            found.append((float((ts - iv["start"]).dt.total_seconds().median()), c))
    return [c for _, c in sorted(found)]


def block_times(df, raw_sorted, cfg, fast_pct=25, min_median_sec=60):
    """({индекс df: [(блок, сек, медиана сек)]}, [{"block", "median_sec"}])."""
    from .engine import parse_datetime
    cols = timestamp_columns(raw_sorted, df, cfg)
    if not cols:
        return {}, []
    points = [("старт", df["start"])] + [(c, parse_datetime(raw_sorted[c])) for c in cols] + [("финиш", df["end"])]
    iv = (~df["technical"] & ~df["rejected"] & df["completed"]).to_numpy()
    flags, summary = {}, []
    for (a_name, a), (b_name, b) in zip(points, points[1:]):
        sec = (b - a).dt.total_seconds()
        name = f"{a_name} → {b_name}"
        med = float(sec[iv & sec.notna().to_numpy() & (sec >= 0).to_numpy()].median()) if iv.any() else np.nan
        summary.append({"block": name, "median_sec": None if np.isnan(med) else round(med)})
        if np.isnan(med) or med < min_median_sec:
            continue
        fast = iv & (sec < med * fast_pct / 100).to_numpy() & (sec >= 0).to_numpy()
        for i in np.flatnonzero(fast):
            flags.setdefault(int(i), []).append((name, float(sec.iloc[i]), med))
    return flags, summary


def fmt_sec(s):
    s = int(round(s))
    return f"{s} сек" if s < 90 else f"{s / 60:.1f} мин".replace(".0 ", " ")
