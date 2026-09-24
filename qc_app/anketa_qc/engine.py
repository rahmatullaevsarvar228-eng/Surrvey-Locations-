# -*- coding: utf-8 -*-
"""Движок проверок анкет.

Технические проверки перенесены из cheat_detector.py / main.py без изменения
логики: Device ID, «1 устройство ↔ 1 код интервьюера», длительность, интервал
между стартами, «отдых» после предыдущей анкеты, «конвейер», доля интервьюера
в городе, минимум интервьюеров на город, пропуски телефона по городу, глубина
зондажа в открытых вопросах и среднее число ответов интервьюера против медианы
волны.

Новые проверки: дубликаты респондентов (телефон / ФИО), аномалии по времени
суток, пользовательские логические правила, повтор значения у интервьюера по
списку, который задаёт PM (раньше был зашит под банки).

Каждая найденная проблема — (код, серьёзность, текст). Серьёзность «defect»
делает анкету браком, «warning» — только предупреждение. Код нужен, чтобы
группировать причины без поиска подстрок в тексте.
"""
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

DEFECT = "defect"
WARNING = "warning"

# Полные формулировки для сводных таблиц (по коду проблемы).
ISSUE_LABELS = {
    "no_device": "Отсутствует Device ID",
    "device_multi_inter": "Одно устройство — несколько кодов интервьюера",
    "inter_multi_device": "Один код интервьюера — несколько устройств",
    "too_long": "Анкета длилась дольше максимума",
    "too_short": "Анкета короче минимума",
    "start_gap": "Слишком маленький интервал между стартами анкет",
    "no_rest": "Нет перерыва после завершения предыдущей анкеты",
    "conveyor": "«Конвейер» — много анкет подряд за короткое окно на одном устройстве",
    "night": "Анкета в нетипичное время суток",
    "dup_phone": "Дубликат респондента: тот же телефон",
    "dup_name": "Дубликат респондента: то же ФИО",
    "probe_depth": "Мало ответов в открытом вопросе (слабый зондаж «А ещё?»)",
    "probe_low_avg": "У интервьюера мало ответов в открытых вопросах относительно медианы волны",
    "no_gps": "Нет GPS-координат",
    "geo_far": "Анкета далеко от плановой точки опроса",
    "geo_cluster": "Скопление: слишком много анкет интервьюера в одном месте",
    "geo_same": "Одинаковые GPS-координаты в разных анкетах интервьюера",
    "geo_jump": "«Телепорт»: слишком быстрое перемещение между анкетами",
}

# Система раннего предупреждения (из main.py) — одна шкала для всех проверок.
STATUS_LEVELS = {
    "RED": dict(code="RED", emoji="🔴", label="Критическое нарушение",
                actions="временно остановить интервьюера; проверить его данные; решить вопрос "
                        "о замене; при необходимости исключить подозрительные интервью из базы"),
    "YELLOW": dict(code="YELLOW", emoji="🟡", label="Предупреждение",
                   actions="уведомить интервьюера; объяснить ошибку; провести дополнительный "
                           "инструктаж; усилить мониторинг"),
    "GREEN": dict(code="GREEN", emoji="🟢", label="Нормальная работа",
                  actions="требования выполняются, существенных нарушений нет"),
}


def status_for_pct(pct, red_pct, yellow_pct):
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "GREEN"
    if pct >= red_pct:
        return "RED"
    if pct >= yellow_pct:
        return "YELLOW"
    return "GREEN"


def status_legend(cfg):
    red, yellow = cfg["status"]["red_pct"], cfg["status"]["yellow_pct"]
    desc = {"RED": f"Доля брака ≥ {red}%", "YELLOW": f"Доля брака от {yellow}% до {red}%",
            "GREEN": f"Доля брака < {yellow}%"}
    return [dict(STATUS_LEVELS[c], desc=desc[c]) for c in ("RED", "YELLOW", "GREEN")]


# ─────────────────────────────────────────────────────────────────────────
# Подготовка данных
# ─────────────────────────────────────────────────────────────────────────
_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def parse_datetime(series):
    """Время как его видел интервьюер (локальное). Kobo пишет «…+05:00»:
    отрезаем смещение, а не переводим в UTC, иначе проверка «ночных» анкет
    сдвинется на 5 часов. Для интервалов результат тот же.
    Только pandas — без np.datetime64(pd.Timestamp(...)), который падает на
    части версий numpy/pandas под Windows."""
    def _strip(v):
        if isinstance(v, str):
            return _TZ_SUFFIX.sub("", v.strip())
        if isinstance(v, pd.Timestamp) and v.tzinfo is not None:
            return v.tz_localize(None)
        return v
    parsed = pd.to_datetime(series.map(_strip), errors="coerce", format="mixed")
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_localize(None)
    return parsed


def clean_str(v):
    """Приводит значение ячейки к строке: 356789012345678.0 → «356789012345678»,
    пустые строки → None."""
    if v is None:
        return None
    if isinstance(v, float):
        if np.isnan(v):
            return None
        if v.is_integer():
            return str(int(v))
    s = str(v).strip()
    return s or None


def normalize_city(v):
    s = clean_str(v)
    if s is None:
        return None
    return re.sub(r"^(г\.\s*|shahar\s+)", "", s, flags=re.IGNORECASE).strip() or None


def _is_blank(series):
    return series.isna() | (series.astype(str).str.strip() == "")


def prepare(raw, cfg):
    """Стандартная таблица анкет. raw и результат выровнены по позиции:
    колонка pos указывает на строку raw (после отбрасывания пустых строк)."""
    m = cfg["mapping"]
    raw = raw.reset_index(drop=True)
    df = pd.DataFrame(index=raw.index)
    if m.get("id"):
        df["row_id"] = raw[m["id"]].map(clean_str).fillna("—")
    else:
        df["row_id"] = "стр. " + (raw.index + 2).astype(str)   # номер строки в Excel
    df["deviceid"] = raw[m["device"]].map(clean_str)
    df["start"] = parse_datetime(raw[m["start"]])
    df["end"] = parse_datetime(raw[m["end"]])
    df["city"] = raw[m["city"]].map(normalize_city)
    df["inter"] = raw[m["inter"]].map(clean_str)
    df["phone"] = raw[m["phone"]].map(clean_str) if m.get("phone") else None
    df["resp_name"] = raw[m["name"]].map(clean_str) if m.get("name") else None
    if m.get("lat"):
        from .geo import parse_coords
        df["lat"], df["lon"] = parse_coords(raw[m["lat"]], raw[m["lon"]] if m.get("lon") else None)
    else:
        df["lat"] = df["lon"] = np.nan

    done_cols = [c for c in cfg.get("completed_cols") or [] if c in raw.columns]
    if done_cols:
        df["completed"] = (~raw[done_cols].apply(_is_blank)).any(axis=1)
    else:
        df["completed"] = True

    keep = (df["deviceid"].notna() | df["inter"].notna()) & df["city"].notna()
    n_dropped = int((~keep).sum())
    df = df[keep].copy()
    raw = raw.loc[df.index].reset_index(drop=True)
    df = df.reset_index(drop=True)
    df["pos"] = df.index
    df["duration_min"] = (df["end"] - df["start"]).dt.total_seconds() / 60
    return df, raw, n_dropped


# ─────────────────────────────────────────────────────────────────────────
# Открытые ответы: заглушки «не знаю» и приведение к значению из списка
# ─────────────────────────────────────────────────────────────────────────
def norm_text(v):
    return re.sub(r"\s+", " ", str(v).strip().lower())


class AnswerFilter:
    def __init__(self, invalid_exact, invalid_substr):
        self.exact = {norm_text(x) for x in invalid_exact if str(x).strip()}
        self.substr = tuple(norm_text(x) for x in invalid_substr if str(x).strip())

    def is_valid(self, v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return False
        s = norm_text(v)
        if s == "" or s in self.exact:
            return False
        return not any(p in s for p in self.substr)


class Canonicalizer:
    """Объединяет варианты написания одного значения («Uzum», «Узум банк»,
    «Uzumbank») в одно. Сначала точное совпадение с названием или вариантом,
    затем — вариант как подстрока ответа (как BRAND_CORE_PATTERNS в main.py).
    Значения вне списка остаются как есть."""

    def __init__(self, values):
        self.exact = {}
        self.substr = []
        for item in values or []:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            self.exact[norm_text(name)] = name
            for var in item.get("variants") or []:
                var_n = norm_text(var)
                if not var_n:
                    continue
                self.exact.setdefault(var_n, name)
                self.substr.append((var_n, name))
            self.substr.append((norm_text(name), name))
        # длинные варианты раньше коротких: «uzum bank» точнее, чем «uzum»
        self.substr.sort(key=lambda x: -len(x[0]))

    def __bool__(self):
        return bool(self.exact)

    def match(self, answer):
        s = norm_text(answer)
        if s in self.exact:
            return self.exact[s]
        for var, name in self.substr:
            if len(var) >= 3 and var in s:
                return name
        return None

    def canonical(self, answer):
        return self.match(answer) or str(answer).strip()


# ─────────────────────────────────────────────────────────────────────────
# Пользовательские правила «если … то …»
# ─────────────────────────────────────────────────────────────────────────
RULE_OPS = {
    "<": "меньше", "<=": "не больше", ">": "больше", ">=": "не меньше",
    "==": "равно", "!=": "не равно", "contains": "содержит", "not_contains": "не содержит",
    "empty": "пусто", "not_empty": "заполнено",
}
_NUMERIC_OPS = {"<", "<=", ">", ">="}


def _to_float(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def eval_condition(series, op, value, unknown_as):
    """Булева маска условия. unknown_as — чем считать строки, где число не
    удалось прочитать: в «если» это False (правило не применяется), в «то» —
    True (нарушение не доказано)."""
    if op == "empty":
        return _is_blank(series)
    if op == "not_empty":
        return ~_is_blank(series)
    if op in _NUMERIC_OPS:
        target = _to_float(value)
        nums = pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False).str.strip(),
                             errors="coerce")
        if target is None:
            return pd.Series(unknown_as, index=series.index)
        res = {"<": nums < target, "<=": nums <= target,
               ">": nums > target, ">=": nums >= target}[op]
        return res.where(nums.notna(), unknown_as).astype(bool)
    text = series.map(lambda v: norm_text(v) if clean_str(v) is not None else "")
    val = norm_text(value)
    if op in ("==", "!="):
        target = _to_float(value)
        nums = pd.to_numeric(series, errors="coerce")
        if target is not None and nums.notna().any():
            eq = (nums == target) | ((nums.isna()) & (text == val))
        else:
            eq = text == val
        return eq if op == "==" else ~eq
    if op in ("contains", "not_contains"):
        has = text.str.contains(re.escape(val), regex=True) if val else pd.Series(True, index=series.index)
        return has if op == "contains" else ~has
    raise ValueError(f"Неизвестная операция: {op}")


def describe_rule(rule):
    def part(col, op, val):
        if op in ("empty", "not_empty"):
            return f"«{col}» {RULE_OPS[op]}"
        return f"«{col}» {RULE_OPS.get(op, op)} {val}"
    then = part(rule["then_col"], rule["then_op"], rule.get("then_val", ""))
    if rule.get("if_col"):
        return f"если {part(rule['if_col'], rule['if_op'], rule.get('if_val', ''))}, то {then}"
    return f"всегда {then}"


# ─────────────────────────────────────────────────────────────────────────
# Основной прогон
# ─────────────────────────────────────────────────────────────────────────
def _fmt_list(items, limit=5):
    items = [str(x) for x in items]
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f" и ещё {len(items) - limit}"


def normalize_phone(v):
    digits = re.sub(r"\D", "", str(v)) if v is not None else ""
    if len(digits) < 7 or len(set(digits)) == 1:
        return None   # «0», «999999999» и прочие заглушки — не телефон
    return digits[-9:]


def normalize_name(v, answer_filter):
    if v is None or not answer_filter.is_valid(v):
        return None
    s = re.sub(r"[^\w\s]", " ", str(v).lower())
    words = sorted(w for w in s.split() if len(w) > 1)
    # Одно имя («Азиз») встречается постоянно — дубликат только по имени + фамилии.
    return " ".join(words) if len(words) >= 2 else None


def run(raw_input, cfg):
    t = cfg["thresholds"]
    df, raw, n_dropped = prepare(raw_input, cfg)
    probing = cfg["probing"]
    answer_filter = AnswerFilter(probing.get("invalid_exact", []), probing.get("invalid_substr", []))

    # Число реальных ответов в каждом блоке открытых вопросов (до сортировки —
    # df и raw ещё выровнены по позиции).
    blocks = [b for b in probing.get("blocks") or []
              if [c for c in b.get("columns") or [] if c in raw.columns]]
    for i, b in enumerate(blocks):
        cols = [c for c in b["columns"] if c in raw.columns]
        df[f"probe_{i}"] = raw[cols].apply(lambda col: col.map(answer_filter.is_valid)).sum(axis=1)

    df = df.sort_values(["deviceid", "start"], na_position="last").reset_index(drop=True)
    issues = [[] for _ in range(len(df))]

    def add(mask, code, severity, text_fn):
        for i in np.flatnonzero(np.asarray(mask, dtype=bool)):
            issues[i].append((code, severity, text_fn(i)))

    # --- Device ID ---------------------------------------------------------
    add(df["deviceid"].isna(), "no_device", DEFECT, lambda i: "нет Device ID")

    # --- 1 устройство ↔ 1 код интервьюера (предупреждения) -----------------
    with_dev = df.dropna(subset=["deviceid", "inter"])
    dev_codes = with_dev.groupby("deviceid")["inter"].agg(lambda s: sorted(s.unique(), key=str))
    code_devs = with_dev.groupby("inter")["deviceid"].agg(lambda s: sorted(s.unique(), key=str))
    multi_dev = {d: c for d, c in dev_codes.items() if len(c) > 1}
    multi_code = {c: d for c, d in code_devs.items() if len(d) > 1}
    add(df["deviceid"].isin(list(multi_dev)), "device_multi_inter", WARNING,
        lambda i: f"1 устройство → {len(multi_dev[df.at[i, 'deviceid']])} кодов интервьюера "
                  f"({_fmt_list(multi_dev[df.at[i, 'deviceid']])})")
    add(df["inter"].isin(list(multi_code)) & df["deviceid"].notna(), "inter_multi_device", WARNING,
        lambda i: f"1 код интервьюера → {len(multi_code[df.at[i, 'inter']])} устройств "
                  f"({_fmt_list(multi_code[df.at[i, 'inter']])})")

    # --- Длительность --------------------------------------------------------
    dur = df["duration_min"]
    add(dur > t["max_duration_min"], "too_long", DEFECT,
        lambda i: f"анкета длилась {dur[i]:.0f} мин (> {t['max_duration_min']})")
    # Короткими обязаны быть скринауты — порог только для завершённых интервью.
    add((dur < t["min_duration_min"]) & dur.notna() & df["completed"], "too_short", DEFECT,
        lambda i: f"интервью длилось {dur[i]:.1f} мин (< {t['min_duration_min']})")

    # --- Интервал между стартами и «отдых» ----------------------------------
    df["gap_min"] = df.groupby("deviceid")["start"].diff().dt.total_seconds() / 60
    add((df["gap_min"] < t["min_interval_min"]) & df["gap_min"].notna(), "start_gap", DEFECT,
        lambda i: f"интервал с предыдущей анкетой {df.at[i, 'gap_min']:.1f} мин (< {t['min_interval_min']})")
    # Не то же самое, что интервал между стартами: после длинной анкеты старты
    # могут быть далеко друг от друга, а реального перерыва не было.
    prev_end = df.groupby("deviceid")["end"].shift(1)
    df["rest_min"] = (df["start"] - prev_end).dt.total_seconds() / 60
    add((df["rest_min"] < t["min_interval_min"]) & df["rest_min"].notna(), "no_rest", DEFECT,
        lambda i: f"начал следующую анкету через {df.at[i, 'rest_min']:.1f} мин после завершения "
                  f"предыдущей (< {t['min_interval_min']})")

    # --- «Конвейер» — только pandas-сравнения, без np.datetime64 ------------
    window, min_count = t["mass_window_min"], t["mass_min_count"]
    burst = pd.Series(0, index=df.index)
    for _, g in df[df["deviceid"].notna() & df["start"].notna()].groupby("deviceid"):
        if len(g) < min_count:
            continue
        starts = g["start"].reset_index(drop=True)
        idxs = g.index.to_numpy()
        for pos in range(len(g)):
            window_end = starts.iloc[pos] + pd.Timedelta(minutes=window)
            in_window = ((starts >= starts.iloc[pos]) & (starts <= window_end)).to_numpy()
            cnt = int(in_window.sum())
            if cnt >= min_count:
                for j in idxs[in_window]:
                    burst[j] = max(burst[j], cnt)
    add(burst >= min_count, "conveyor", DEFECT,
        lambda i: f"конвейер: {int(burst[i])} анкет за {window} мин на одном устройстве (≥ {min_count})")

    # --- Время суток ---------------------------------------------------------
    night = cfg["night"]
    if night.get("enabled"):
        h0, h1 = int(night["work_start_hour"]), int(night["work_end_hour"])
        hour = df["start"].dt.hour + df["start"].dt.minute / 60
        inside = (hour >= h0) & (hour < h1) if h0 <= h1 else (hour >= h0) | (hour < h1)
        add(df["start"].notna() & ~inside, "night", night.get("severity", WARNING),
            lambda i: f"анкета начата в {df.at[i, 'start']:%H:%M} (вне {h0:02d}:00–{h1:02d}:00)")

    # --- Дубликаты респондентов ---------------------------------------------
    dups = cfg["duplicates"]
    for key, col, code, label in (("phone", "phone", "dup_phone", "телефон"),
                                  ("name", "resp_name", "dup_name", "ФИО")):
        if not cfg["mapping"].get(key):
            continue
        if key == "phone":
            norm = df[col].map(normalize_phone)
        else:
            # Полных тёзок в большом городе много — одно ФИО сравниваем только
            # внутри одного города.
            names = df[col].map(lambda v: normalize_name(v, answer_filter))
            norm = (df["city"].fillna("") + "|" + names).where(names.notna())
        groups = df[norm.notna()].groupby(norm[norm.notna()])
        dup_of = {}
        for _, g in groups:
            if len(g) < 2:
                continue
            for i in g.index:
                others = g.drop(index=i)
                dup_of[i] = (f"тот же {label} ещё в {len(others)} анкет(ах): "
                             f"{_fmt_list(others['row_id'])} "
                             f"(интервьюер: {_fmt_list(sorted(others['inter'].dropna().unique(), key=str), 3)})")
        add(df.index.isin(list(dup_of)), code, dups.get(f"{key}_severity", DEFECT), lambda i: dup_of[i])

    # --- Глубина зондажа в открытых вопросах --------------------------------
    for bi, b in enumerate(blocks):
        cnt, min_n = df[f"probe_{bi}"], int(b.get("min_n") or 0)
        add((cnt > 0) & (cnt < min_n) & df["completed"], "probe_depth", probing.get("severity", WARNING),
            lambda i, cnt=cnt, b=b, min_n=min_n: f"{b.get('label') or 'Блок'}: назвал(а) {int(cnt[i])} (< {min_n})")
    wave_median = None
    if blocks:
        probe_total = df[[f"probe_{i}" for i in range(len(blocks))]].sum(axis=1)
        df["probe_total"] = probe_total
        base = df[df["completed"]]
        wave_median = float(base["probe_total"].median()) if len(base) else None
        if wave_median:
            limit = wave_median * probing.get("low_avg_pct", 70) / 100
            inter_avg = base.groupby("inter")["probe_total"].mean()
            low = inter_avg[inter_avg < limit]
            add(df["inter"].isin(list(low.index)), "probe_low_avg", probing.get("low_avg_severity", DEFECT),
                lambda i: f"у интервьюера в среднем {low[df.at[i, 'inter']]:.1f} ответов в открытых вопросах "
                          f"(< {probing.get('low_avg_pct', 70)}% медианы волны {wave_median:.1f})")

    # --- GPS-контроль (если выбрана колонка с координатами) -----------------
    geo_result = {"enabled": False}
    if cfg["mapping"].get("lat"):
        from . import geo
        geo_result = geo.check(df, cfg, add)

    # --- Пользовательские правила -------------------------------------------
    rule_errors = []
    raw_sorted = raw.loc[df["pos"]].reset_index(drop=True)
    for ri, rule in enumerate(cfg.get("rules") or []):
        name = (rule.get("name") or "").strip() or f"Правило {ri + 1}"
        cols = [c for c in (rule.get("if_col"), rule.get("then_col")) if c]
        missing = [c for c in cols if c not in raw_sorted.columns]
        if not rule.get("then_col") or missing:
            rule_errors.append(f"{name}: " + (f"нет колонки {', '.join(missing)}" if missing
                                              else "не выбрана колонка «то»"))
            continue
        try:
            cond_if = (eval_condition(raw_sorted[rule["if_col"]], rule["if_op"], rule.get("if_val"), False)
                       if rule.get("if_col") else pd.Series(True, index=raw_sorted.index))
            cond_then = eval_condition(raw_sorted[rule["then_col"]], rule["then_op"], rule.get("then_val"), True)
        except ValueError as e:
            rule_errors.append(f"{name}: {e}")
            continue
        code = f"rule:{name}"
        ISSUE_LABELS.setdefault(code, f"Правило «{name}»: {describe_rule(rule)}")
        tc = rule["then_col"]
        add(cond_if & ~cond_then, code, rule.get("severity", DEFECT),
            lambda i, name=name, tc=tc: f"правило «{name}»: «{tc}» = {clean_str(raw_sorted.at[i, tc]) or 'пусто'}")

    # --- Итог по анкетам -----------------------------------------------------
    df["issues"] = issues
    df["is_defect"] = df["issues"].map(lambda xs: any(s == DEFECT for _, s, _ in xs))
    df["is_warning"] = df["issues"].map(lambda xs: any(s == WARNING for _, s, _ in xs))
    df["reason_text"] = df["issues"].map(lambda xs: "; ".join(x for _, s, x in xs if s == DEFECT))
    df["warning_text"] = df["issues"].map(lambda xs: "; ".join(x for _, s, x in xs if s == WARNING))

    city_issues = check_cities(df, cfg)
    repetition, answers = analyze_answers(df, raw, cfg, answer_filter, blocks)
    interviewers = summarize_interviewers(df, cfg, repetition)

    return {
        "df": df,
        "raw": raw,
        "n_dropped": n_dropped,
        "city_issues": city_issues,
        "rule_errors": rule_errors,
        "wave_median": wave_median,
        "blocks": [b.get("label") or f"Блок {i + 1}" for i, b in enumerate(blocks)],
        "interviewers": interviewers,
        "repetition": repetition,
        "geo": geo_result,
        # Общие для всей выгрузки данные — отдельно от построчной таблицы
        # (урок из main.py: копия на каждой строке роняла приложение по памяти).
        "answers": answers,
    }


def check_cities(df, cfg):
    t = cfg["thresholds"]
    out = []
    for city, g in df.groupby("city"):
        n_inters = g["inter"].nunique()
        if n_inters < t["min_inters_per_city"]:
            out.append(dict(city=city, level="YELLOW",
                            text=f"только {n_inters} интервьюер(а) — нужно минимум {t['min_inters_per_city']}"))
        counts = g["inter"].value_counts()
        total = int(counts.sum())
        for inter, cnt in counts.items():
            share = cnt / total * 100
            if share > t["max_share_city_pct"]:
                out.append(dict(city=city, level="RED" if share >= 90 else "YELLOW",
                                text=f"{inter} сделал {share:.0f}% анкет города ({cnt}/{total}, "
                                     f"> {t['max_share_city_pct']}%)"))
        if cfg["mapping"].get("phone"):
            done = g[g["completed"]]
            if len(done):
                no_phone = int(done["phone"].map(normalize_phone).isna().sum())
                pct = no_phone / len(done) * 100
                if pct > t["phone_missing_city_pct"]:
                    out.append(dict(city=city, level="YELLOW",
                                    text=f"без номера телефона {pct:.0f}% завершённых анкет "
                                         f"({no_phone}/{len(done)}, > {t['phone_missing_city_pct']}%)"))
    return out


def analyze_answers(df, raw, cfg, answer_filter, blocks):
    """Аудит открытых ответов и детектор повтора значения у интервьюера.
    Возвращает (repetition, answers):
      repetition — {"enabled", "rows"} по интервьюерам;
      answers — {"all": [...уникальные ответы...], "index": {ответ: [где встретился]}}.
    """
    rep_cfg = cfg["repetition"]
    canon = Canonicalizer(rep_cfg.get("values"))
    rep_cols = [c for c in rep_cfg.get("columns") or [] if c in raw.columns]
    block_of = {}
    for b in blocks:
        for c in b["columns"]:
            block_of.setdefault(c, b.get("label") or "Блок")
    audit_cols = list(dict.fromkeys([c for b in blocks for c in b["columns"] if c in raw.columns] + rep_cols))

    # df отсортирован — достаём атрибуты анкеты по позиции в raw
    by_pos = df.set_index("pos")[["row_id", "city", "inter"]]
    index = defaultdict(list)
    counter = Counter()
    for col in audit_cols:
        for pos, v in raw[col].items():
            s = clean_str(v)
            if s is None or pos not in by_pos.index:
                continue
            counter[s] += 1
            r = by_pos.loc[pos]
            index[s].append({"ID анкеты": r["row_id"], "Город": r["city"] or "—",
                             "Интервьюер": r["inter"] or "—",
                             "Вопрос": block_of.get(col, col)})

    all_rows = []
    for ans, cnt in counter.most_common():
        if not answer_filter.is_valid(ans):
            status, value = "❌ заглушка «не знаю»", ""
        elif canon:
            match = canon.match(ans)
            status, value = ("✅ из списка", match) if match else ("❔ не из списка", "")
        else:
            status, value = "✅ засчитан", ""
        all_rows.append({"Ответ": ans, "Раз": cnt, "Статус": status, "Значение из списка": value,
                         "Интервьюеров": len({o["Интервьюер"] for o in index[ans]})})

    repetition = {"enabled": bool(canon) and bool(rep_cols), "rows": []}
    if repetition["enabled"]:
        rc = rep_cfg
        per_inter = defaultdict(lambda: {"city": Counter(), "answers": Counter(), "total": 0})
        for col in rep_cols:
            for pos, v in raw[col].items():
                if pos not in by_pos.index or not answer_filter.is_valid(v):
                    continue
                r = by_pos.loc[pos]
                d = per_inter[r["inter"] or "—"]
                d["city"][r["city"] or "—"] += 1
                d["answers"][canon.canonical(v)] += 1
                d["total"] += 1
        for inter, d in per_inter.items():
            top, top_n = d["answers"].most_common(1)[0]
            pct = round(top_n / d["total"] * 100, 1)
            n = d["total"]
            if pct >= rc["red_pct"] and n >= rc["red_min_n"]:
                level = "RED"
            elif pct >= rc["yellow_pct"] and n >= rc["yellow_min_n"]:
                level = "YELLOW"
            else:
                level = "GREEN"
            repetition["rows"].append({
                "Город": d["city"].most_common(1)[0][0], "Интервьюер": inter,
                "Ответов": n, "Самое частое значение": top, "Повторов": top_n,
                "% повтора": pct, "Статус": level,
            })
        repetition["rows"].sort(key=lambda r: (str(r["Город"]), -r["% повтора"]))

    return repetition, {"all": all_rows, "index": dict(index)}


def summarize_interviewers(df, cfg, repetition):
    red, yellow = cfg["status"]["red_pct"], cfg["status"]["yellow_pct"]
    rep_by_inter = {r["Интервьюер"]: r for r in repetition.get("rows", [])}
    rows = []
    for inter, g in df.groupby(df["inter"].fillna("—")):
        n = len(g)
        n_def = int(g["is_defect"].sum())
        pct = round(n_def / n * 100, 1) if n else 0.0
        codes = Counter(code for xs in g["issues"] for code, sev, _ in xs if sev == DEFECT)
        top = ", ".join(f"{ISSUE_LABELS.get(c, c)} ×{k}" for c, k in codes.most_common(3))
        city = g["city"].mode()
        rep = rep_by_inter.get(inter)
        rows.append({
            "Интервьюер": inter,
            "Город": city.iloc[0] if len(city) else "—",
            "Анкет": n,
            "Завершено": int(g["completed"].sum()),
            "Брак": n_def,
            "% брака": pct,
            "Статус": status_for_pct(pct, red, yellow),
            "Предупреждений": int(g["is_warning"].sum()),
            "Повтор значения": f"{rep['Самое частое значение']} — {rep['% повтора']}%" if rep else "",
            "Повтор: статус": rep["Статус"] if rep else "",
            "Главные причины брака": top,
        })
    rows.sort(key=lambda r: (-r["% брака"], str(r["Интервьюер"])))
    return rows


# ─────────────────────────────────────────────────────────────────────────
# Сводки для интерфейса
# ─────────────────────────────────────────────────────────────────────────
def issue_breakdown(df, severity):
    n_base = int(df["is_defect"].sum()) if severity == DEFECT else len(df)
    counts = Counter()
    for xs in df["issues"]:
        for code in {c for c, s, _ in xs if s == severity}:
            counts[code] += 1
    return [{"Причина": ISSUE_LABELS.get(code, code), "code": code, "Анкет": k,
             "%": round(k / max(n_base, 1) * 100, 1)} for code, k in counts.most_common()]


def data_period(df):
    starts = df["start"].dropna()
    if not len(starts):
        return None
    a, b = starts.min().strftime("%d.%m.%Y"), starts.max().strftime("%d.%m.%Y")
    return a if a == b else f"{a} – {b}"
