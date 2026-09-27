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
import math
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
        if vals.map(_norm).value_counts(normalize=True).iloc[0] >= 0.95:
            continue                          # у всех одно и то же («Страна») — ничего не различает
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
    codes = np.full((len(rows), len(cols)), -1, dtype=np.int16)
    for j, c in enumerate(cols):
        col = raw_sorted[c].iloc[rows]
        vals = col.map({u: _norm(u) for u in pd.unique(col.dropna())})
        if set(vals.dropna().unique()) <= {"0", "1"}:
            # вариант вопроса с несколькими ответами (Kobo делит его на колонки 0/1):
            # «не выбран» у всех совпадает — сравниваем только выбранные
            vals = vals.where(vals == "1")
        cat, uniq = pd.factorize(vals, use_na_sentinel=True)
        if len(uniq) < 32000:                    # int16; почти уникальные колонки и так отброшены
            codes[:, j] = cat
    valid = codes >= 0
    out = {}
    # Копии делают внутри своей работы — сравниваем анкеты одного города
    # (в N раз быстрее на больших волнах; без города — все со всеми).
    city = df["city"].fillna("—").to_numpy()[rows]
    for g in pd.unique(city):
        idx = np.flatnonzero(city == g)
        if len(idx) < 2:
            continue
        C, V = codes[idx], valid[idx]
        chunk = max(1, 4_000_000 // max(len(idx) * len(cols), 1))
        for a in range(0, len(idx), chunk):
            A, VA = C[a:a + chunk], V[a:a + chunk]
            both = VA[:, None, :] & V[None, :, :]
            same = both & (A[:, None, :] == C[None, :, :])
            n_both = both.sum(axis=2)
            ratio = np.where(n_both >= min_questions, same.sum(axis=2) / np.maximum(n_both, 1), 0.0)
            for k in range(len(A)):
                ratio[k, a + k] = 0.0                # сама с собой
            best = ratio.argmax(axis=1)
            for k, b in enumerate(best):
                r = ratio[k, b]
                if r >= threshold:
                    out[int(rows[idx[a + k]])] = (float(r), int(rows[idx[b]]), int(n_both[k, b]))
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


def _norm_frame(frame):
    """Нормализованные ответы: одна строка — одно значение на колонку.
    Считаем по уникальным значениям — в разы быстрее, чем по каждой ячейке."""
    out = {}
    for c in frame.columns:
        col = frame[c]
        uniq = pd.unique(col.dropna())
        m = {u: _norm(u) for u in uniq}
        out[c] = col.map(m)
    return pd.DataFrame(out, index=frame.index)


def answer_patterns(df, raw_sorted, cols, answer_filter, min_n=15, tvd_limit=0.3, alpha=0.001, min_score=0.6):
    """[{inter, city, n, score, notes: [...]}] — интервьюеры, у чьих
    респондентов ответы заметно отличаются от остальных."""
    from .engine import clean_str
    base = df[df["completed"] & df["inter"].notna()]
    if len(base) < 2 * min_n or not cols:
        return []
    norm = _norm_frame(raw_sorted.loc[base.index, cols])
    inter_of = base["inter"]
    cat_cols = [c for c in cols if 2 <= norm[c].nunique() <= 12 and norm[c].notna().mean() >= 0.5]
    # таблицы «интервьюер × вариант ответа» — один раз на вопрос
    tabs = {c: pd.crosstab(inter_of, norm[c]) for c in cat_cols}
    labels = {}
    for c in cat_cols:
        col = raw_sorted.loc[base.index, c].dropna()
        labels[c] = {}
        for v in pd.unique(col):
            labels[c].setdefault(_norm(v), clean_str(v))
    # «не знаю»/отказы: сколько заполненных ответов и сколько из них заглушки — по строкам
    filled = norm.notna()
    valid_map = {}
    for c in cols:
        for v in pd.unique(raw_sorted.loc[base.index, c].dropna()):
            valid_map.setdefault((c, v), answer_filter.is_valid(v))
    invalid = pd.DataFrame({c: raw_sorted.loc[base.index, c].map(
        lambda v, c=c: (not valid_map.get((c, v), True)) if pd.notna(v) else False) for c in cols}, index=base.index)
    per_row_filled = filled.sum(axis=1)
    per_row_dk = (invalid & filled).sum(axis=1)
    dk_by = pd.DataFrame({"f": per_row_filled, "d": per_row_dk}).groupby(inter_of).sum()
    tot_f, tot_d = dk_by["f"].sum(), dk_by["d"].sum()

    counts = inter_of.value_counts()
    inters = list(counts.index)
    pos = {x: i for i, x in enumerate(inters)}
    notes_by = {x: [] for x in inters}
    score_by = dict.fromkeys(inters, 0.0)
    modal_m = {x: [] for x in inters}
    modal_r = {x: [] for x in inters}
    erfc = np.vectorize(math.erfc)
    limit = alpha / max(len(cat_cols), 1)
    # все интервьюеры по одному вопросу — сразу, матрицами
    for c in cat_cols:
        t = tabs[c].reindex(inters, fill_value=0)
        T = t.to_numpy(dtype=float)
        tot = T.sum(axis=0)
        nm = T.sum(axis=1)
        R = tot[None, :] - T
        nr = R.sum(axis=1)
        use = (nm >= min_n) & (nr >= 2 * min_n)
        if not use.any():
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            pm = T / nm[:, None]
            pr = R / nr[:, None]
            diff = pm - pr
            tvd = 0.5 * np.abs(diff).sum(axis=1)
            exp = pr * nm[:, None]
            ok = exp > 0
            chi2 = np.where(ok, (T - exp) ** 2 / np.where(ok, exp, 1), 0).sum(axis=1) + np.where(ok, 0, T).sum(axis=1) * 10
        dfree = np.maximum(ok.sum(axis=1) - 1, 1)
        z = ((chi2 / dfree) ** (1 / 3) - (1 - 2 / (9 * dfree))) / np.sqrt(2 / (9 * dfree))
        p = 0.5 * erfc(z / math.sqrt(2))
        for i in np.flatnonzero(use):
            inter = inters[i]
            modal_m[inter].append(float(np.nanmax(pm[i])))
            modal_r[inter].append(float(np.nanmax(pr[i])))
            if tvd[i] >= tvd_limit and p[i] < limit:
                j = int(np.nanargmax(np.abs(diff[i])))
                opt = t.columns[j]
                notes_by[inter].append((float(tvd[i]), f"«{c}»: ответ «{labels[c].get(opt, opt)}» — у него "
                                                      f"{pm[i, j] * 100:.0f}%, у остальных {pr[i, j] * 100:.0f}%"))
                score_by[inter] += float(tvd[i])

    out = []
    for inter, n in counts.items():
        if n < min_n or len(base) - n < 2 * min_n:
            continue
        notes, score = notes_by[inter], score_by[inter]
        modal_mine, modal_rest = modal_m[inter], modal_r[inter]
        # слишком одинаковые ответы у разных респондентов
        if len(modal_mine) >= 5:
            mm, mr = float(np.mean(modal_mine)), float(np.mean(modal_rest))
            if mm - mr >= 0.2:
                notes.append((mm - mr, f"ответы его респондентов слишком похожи друг на друга: самый частый "
                                       f"вариант в среднем у {mm * 100:.0f}% (у остальных {mr * 100:.0f}%)"))
                score += mm - mr
        # «не знаю» / отказы
        if inter in dk_by.index:
            fm, dmn = dk_by.at[inter, "f"], dk_by.at[inter, "d"]
            dm = dmn / fm if fm else 0.0
            dr = (tot_d - dmn) / (tot_f - fm) if tot_f - fm else 0.0
            if dm >= 0.15 and dm >= 2 * dr:
                notes.append((dm, f"много «не знаю»/отказов: {dm * 100:.0f}% ответов (у остальных {dr * 100:.0f}%)"))
                score += dm
        # одно случайное отклонение на маленькой выборке — не сигнал
        if notes and score >= min_score:
            notes.sort(key=lambda x: -x[0])
            city = base.loc[inter_of == inter, "city"].mode()
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
