# -*- coding: utf-8 -*-
"""Проверка анкет руководителем: решения (Брак / Принять / На перезвон),
объяснение, почему система отметила анкету, и исходная строка выгрузки.

Решения хранятся в Google-таблице источника на листе «Решения ОТК» (пишет
сервер доступа); здесь — только их применение к результатам проверки."""
import pandas as pd

from . import engine

DECISIONS = ("Брак", "Принять", "На перезвон")


def final_state(technical, defect, warning, decision):
    """Итоговое состояние анкеты — как в дашбордах: решение руководителя
    важнее системы. tech / brak / warn / ok."""
    if technical:
        return "tech"
    if decision == "Брак":
        return "brak"
    if decision == "Принять":
        return "ok"
    if decision == "На перезвон":
        return "warn"
    return "brak" if defect else "warn" if warning else "ok"

# Для каждой проверки: какие роли колонок она читает и как рассуждает.
# {…} подставляются из настроек проекта.
EXPLAIN = {
    "no_device": (("device",), "В колонке Device ID пусто. Без идентификатора устройства нельзя проверить, "
                               "кто и откуда заполнял анкету."),
    "device_multi_inter": (("device", "inter"), "С этого устройства приходили анкеты под разными кодами интервьюеров. "
                                                "Возможно, один телефон передавали друг другу."),
    "inter_multi_device": (("inter", "device"), "Этот код интервьюера заполнял анкеты с разных устройств."),
    "too_long": (("start", "end"), "Длительность = финиш − старт. Больше {max_duration_min} мин — анкету, скорее всего, "
                                   "не закрыли вовремя или заполняли с перерывами."),
    "too_short": (("start", "end"), "Длительность = финиш − старт. Полное интервью короче {min_duration_min} мин "
                                    "невозможно провести по-настоящему (скринауты не проверяются)."),
    "start_gap": (("device", "start"), "Время между стартом этой и предыдущей анкеты на том же устройстве меньше "
                                       "{min_interval_min} мин — не успеть найти нового респондента."),
    "no_rest": (("device", "start", "end"), "Между финишем предыдущей анкеты и стартом этой на том же устройстве меньше "
                                            "{min_interval_min} мин."),
    "conveyor": (("device", "start"), "На одном устройстве {mass_min_count}+ анкет за {mass_window_min} мин — "
                                      "похоже на массовое заполнение, а не реальные интервью."),
    "night": (("start",), "Анкета начата вне рабочего времени ({work_start_hour}:00–{work_end_hour}:00) "
                          "по местному времени выгрузки."),
    "dup_phone": (("phone",), "Такой же телефон (последние 9 цифр) есть в другой анкете — один человек опрошен дважды "
                              "или номер вписан из другой анкеты."),
    "dup_name": (("name", "city", "inter"), "Те же имя и фамилия в другой анкете того же интервьюера в том же "
                                            "городе. Тёзки у разных интервьюеров дубликатом не считаются."),
    "probe_depth": ((), "В открытом вопросе респондент назвал меньше вариантов, чем требуется. Интервьюер обязан "
                        "переспрашивать «А ещё?»."),
    "probe_low_avg": (("inter",), "У интервьюера в среднем заметно меньше ответов в открытых вопросах, чем в среднем "
                                  "по волне ({low_avg_pct}% медианы) — слабый зондаж."),
    "no_gps": (("lat", "lon"), "В анкете нет GPS-координат."),
    "geo_far": (("lat", "lon", "city"), "Расстояние от координат анкеты до ближайшей плановой точки её города больше "
                                        "{max_dist_km} км."),
    "geo_cluster": (("lat", "lon", "inter"), "У интервьюера больше {max_per_point} анкет в радиусе {min_sep_km} км."),
    "geo_jump": (("lat", "lon", "start", "end", "inter"), "Скорость = расстояние от предыдущей анкеты интервьюера / время "
                                                         "между ними. Быстрее {max_speed_kmh} км/ч по городу не переместиться — "
                                                         "координаты или время подделаны."),
    "geo_same": (("lat", "lon", "inter"), "Координаты совпадают до метра с другими анкетами этого интервьюера — "
                                          "реальные интервью в разных местах так не совпадают."),
    "geo_city": (("lat", "lon", "city"), "Расстояние от координат анкеты до центра города, который указан в анкете, "
                                         "больше границы города (радиус города + {city_margin_km} км запаса). "
                                         "Интервью проведено в другом месте или город выбран неверно."),
    "overlap": (("device", "start", "end"), "На этом устройстве новая анкета открыта раньше, чем закончена "
                                            "предыдущая. Один интервьюер не может вести два интервью сразу — "
                                            "анкеты заполнялись параллельно, без респондента."),
    "mass_open": (("device", "start"), "На одном устройстве {mass_open_count}+ анкет открыты в пределах "
                                       "{mass_open_sec} сек. Так бывает, когда анкеты открывают заранее "
                                       "«пачкой» и потом заполняют сами."),
    "block_empty": ((), "Интервью отмечено как завершённое, но в обязательном блоке нет ни одного ответа — "
                        "блок пропущен."),
    "external": ((), "Анкету уже забраковала группа мониторинга (например, по аудиозаписи) — в колонке отметки стоит «1». "
                     "Такая анкета не перепроверяется системой и сразу считается браком: в норму, квоты и чистую базу "
                     "не идёт, решения руководителя не требует."),
    "screenout": ((), "В анкете намного меньше ответов, чем обычно: разговор оборвался в начале — респондент не "
                      "подошёл по отбору (возраст, смартфон…) или отказался. Это не брак, но такая анкета не "
                      "засчитывается в норму. Перерыв после неё до следующего интервью браком не считается."),
    "logic": ((), "Респондент в начале анкеты сказал одно, а позже — другое: например, сам назвал банк, а в "
                  "списке ответил, что его не знает; или выбрал «ничего из перечисленного» вместе с другим "
                  "вариантом. Это не брак: люди путаются, интервьюер мог ошибиться при вводе. Если таких анкет "
                  "много у одного интервьюера — послушайте аудио."),
    "near_dup": ((), "Ответы этой анкеты почти полностью совпадают с другой анкетой ({near_dup_pct}%+ одинаковых "
                     "ответов). У двух разных людей так почти не бывает — вероятно, анкету скопировали или заполнили "
                     "по образцу. Брак — если {near_dup_defect_pct}%+ совпадает с анкетой того же интервьюера; с анкетой "
                     "другого интервьюера — «проверить»: неизвестно, кто у кого списал. Метод «percent match» "
                     "(Pew Research, Всемирный банк)."),
    "block_fast": ((), "По отметкам времени внутри анкеты блок пройден в несколько раз быстрее, чем обычно у всех "
                       "(меньше {block_fast_pct}% обычного времени). Так бывает, когда вопросы не зачитывают, а "
                       "отмечают ответы сами."),
    "grid_same": ((), "Во всех вопросах блока-сетки выбран один и тот же вариант. Похоже, интервьюер "
                      "«прощёлкал» блок, не зачитывая вопросы."),
}


def _params(cfg):
    p = {}
    for key in ("thresholds", "night", "geo", "probing", "quality"):
        p.update({k: v for k, v in (cfg.get(key) or {}).items() if not isinstance(v, (dict, list))})
    return p


def explain(cfg, code, text, columns=None):
    """Человеческое объяснение и список колонок исходной таблицы, на которые
    смотрела проверка."""
    m = cfg["mapping"]
    if code.startswith("rule:"):
        name = code[5:]
        rule = next((r for r in cfg.get("rules") or [] if (r.get("name") or "").strip() == name), None)
        if rule:
            return (f"Логическое правило: {engine.describe_rule(rule)}. В этой анкете условие «если» выполнено, "
                    f"а «то» — нет.", [c for c in (rule.get("if_col"), rule.get("then_col")) if c])
        return "Логическое правило проекта.", []
    roles, logic = EXPLAIN.get(code, ((), ""))
    try:
        logic = logic.format(**_params(cfg))
    except (KeyError, IndexError):
        pass
    cols = [m[r] for r in roles if m.get(r)]
    if code == "external" and "«" in text:
        cols = [text.split("«")[1].split("»")[0]]            # колонка, где мониторинг поставил «1»
    if code in ("block_empty", "grid_same"):
        from .blocks import build_sections
        name = text.split("«")[1].split("»")[0] if "«" in text else ""
        cols = next((sec["columns"] for sec in build_sections(columns or [], cfg) if sec["name"] == name), [])
    if code == "probe_depth":
        label = text.split(":")[0]
        for b in cfg["probing"].get("blocks") or []:
            if (b.get("label") or "Блок") == label:
                cols = list(b.get("columns") or [])
    return logic, cols


def anketa_detail(result, cfg, pos, decision=None):
    """Всё для окна «Почему брак»: причины с объяснением, исходная строка
    (все колонки как в выгрузке), выделенные колонки, соседняя анкета на
    том же устройстве для проверок по времени."""
    df, raw = result["df"], result["raw"]
    row = df[df["pos"] == pos].iloc[0]
    issues, highlight = [], []
    for (code, sev, text), block in zip(row["issues"], row["blocks"]):
        logic, cols = explain(cfg, code, text, list(raw.columns))
        issues.append({"code": code, "severity": sev, "label": engine.short_label(code),
                       "full_label": engine.ISSUE_LABELS.get(code, code), "block": block,
                       "text": text, "logic": logic, "columns": cols})
        highlight += [c for c in cols if c not in highlight]

    values = []
    for col, v in raw.loc[pos].items():
        values.append({"column": str(col), "value": engine.clean_str(v) if not isinstance(v, pd.Timestamp)
                       else v.strftime("%Y-%m-%d %H:%M:%S"), "highlight": col in highlight})

    # Запись, которая была на этом устройстве прямо перед анкетой — чтобы
    # руководитель видел, было ли это интервью или техническое задание.
    prev = None
    if pd.notna(row["deviceid"]) and pd.notna(row["start"]):
        same = df[(df["deviceid"] == row["deviceid"]) & (df["start"] < row["start"])].sort_values("start")
        if len(same):
            p = same.iloc[-1]
            gap = (row["start"] - p["end"]).total_seconds() / 60 if pd.notna(p["end"]) else None
            prev = {"id": p["row_id"], "start": _fmt(p["start"]), "end": _fmt(p["end"]),
                    "kind": "техническое задание" if p["technical"] else "интервью",
                    "technical": bool(p["technical"]), "gap_min": None if gap is None else round(gap, 1)}
    return {
        "id": row["row_id"], "city": row["city"], "region": row["region"], "inter": row["inter"],
        "device": row["deviceid"], "technical": bool(row["technical"]), "completed": bool(row["completed"]),
        "risk": int(row["risk"]), "primary": engine.short_label(row["primary"]) if isinstance(row["primary"], str) else None,
        "lat": None if pd.isna(row["lat"]) else float(row["lat"]),
        "lon": None if pd.isna(row["lon"]) else float(row["lon"]),
        "start": _fmt(row["start"]), "end": _fmt(row["end"]),
        "duration": None if pd.isna(row["duration_min"]) else round(float(row["duration_min"]), 1),
        "defect": bool(row["is_defect"]), "warning": bool(row["is_warning"]),
        "issues": issues, "values": values, "previous": prev, "decision": decision,
    }


def _fmt(ts):
    return None if pd.isna(ts) else ts.strftime("%d.%m.%Y %H:%M:%S")


def clean_base(result, decisions_by_pos):
    """(чистая база, не решено). В чистую базу — принятые анкеты и анкеты
    без замечаний системы; брак и «на перезвон» не входят. Подозрительные
    анкеты без решения — отдельным листом, чтобы ничего не потерялось."""
    df, raw = result["df"], result["raw"]
    keep, pending = [], []
    for x in df.itertuples():
        if x.technical:          # технические записи — не интервью, в базу не идут
            continue
        d = (decisions_by_pos.get(x.pos) or {}).get("decision")
        if d == "Принять" or (not d and not x.is_defect):
            keep.append(x.pos)
        elif not d:
            pending.append(x.pos)
    clean = raw.loc[sorted(keep)].copy()
    clean.insert(0, "Статус ОТК", [(decisions_by_pos.get(p) or {}).get("decision") or "Без замечаний"
                                   for p in sorted(keep)])
    done = df.set_index("pos")["completed"]
    clean.insert(1, "Завершено", ["Да" if done.get(p, True) else "Нет (скринаут)" for p in sorted(keep)])
    by_pos = df.set_index("pos")
    todo = raw.loc[sorted(pending)].copy()
    todo.insert(0, "Причина (система)", [by_pos.at[p, "reason_text"] for p in sorted(pending)])
    return clean, todo


def technical_rows(result):
    """Технические записи (видео/фото по заданию) — отдельным листом."""
    df, raw = result["df"], result["raw"]
    pos = sorted(df.loc[df["technical"], "pos"])
    return raw.loc[pos].copy()


def _stable_rank(value):
    """Постоянное «случайное» число для анкеты — выборка не меняется при
    обновлении данных (иначе группа мониторинга получала бы новый список)."""
    import hashlib
    return int(hashlib.md5(str(value).encode("utf-8")).hexdigest()[:8], 16)


def listen_sample(result, cfg, decisions_by_pos):
    """Выборка на прослушку аудио для группы мониторинга (как CARI в
    международной практике): все подозрительные анкеты без решения +
    случайная доля остальных у каждого интервьюера; у новых интервьюеров и
    у тех, кто в красной/жёлтой зоне, доля больше. Минимум одна анкета на
    интервьюера. Возвращает {pos: почему в выборке}."""
    df = result["df"]
    lc = cfg.get("listen") or {}
    base, new, risk = (float(lc.get(k, d)) for k, d in (("base_pct", 5), ("new_pct", 15), ("risk_pct", 20)))
    st = cfg["status"]
    iv = df[~df["technical"] & ~df["rejected"]].copy()
    iv["decision"] = iv["pos"].map(lambda p: (decisions_by_pos.get(p) or {}).get("decision"))
    iv["state"] = [final_state(False, d, w, x) for d, w, x in zip(iv["is_defect"], iv["is_warning"], iv["decision"])]
    last_day = iv["start"].max()
    out = {}
    for inter, g in iv.groupby(iv["inter"].fillna("—")):
        pct_brak = (g["state"] == "brak").mean() * 100
        first = g["start"].min()
        is_new = pd.notna(first) and pd.notna(last_day) and (last_day - first) <= pd.Timedelta(days=2)
        share, why = base, f"случайная выборка {base:g}%"
        if pct_brak >= st["yellow_pct"]:
            share, why = risk, f"интервьюер в зоне риска — выборка {risk:g}%"
        elif is_new:
            share, why = new, f"новый интервьюер — выборка {new:g}%"
        for x in g.itertuples():
            if not x.decision and (x.is_defect or x.is_warning):
                out[x.pos] = "подозрительная анкета — подтвердить по записи"
        rest = g[~g["pos"].isin(list(out)) & g["decision"].isna()]
        rest = rest.assign(_r=rest["row_id"].map(_stable_rank)).sort_values("_r")
        k = max(1, int(round(len(rest) * share / 100))) if len(rest) else 0
        for p in rest["pos"].head(k):
            out[p] = why
    return out


def listen_rows(result, cfg, decisions_by_pos):
    """Таблица для группы мониторинга: что прослушать и куда поставить «1»."""
    df = result["df"].set_index("pos")
    rows = []
    for pos, why in sorted(listen_sample(result, cfg, decisions_by_pos).items(),
                           key=lambda kv: (str(df.at[kv[0], "inter"]), str(df.at[kv[0], "start"]))):
        x = df.loc[pos]
        rows.append({"ID анкеты": x["row_id"], "Интервьюер": x["inter"], "Город": x["city"],
                     "Дата и время": "" if pd.isna(x["start"]) else x["start"].strftime("%d.%m.%Y %H:%M"),
                     "Длительность, мин": None if pd.isna(x["duration_min"]) else round(float(x["duration_min"]), 1),
                     "Почему в выборке": why,
                     "Что нашла система": x["reason_text"] or x["warning_text"] or "",
                     "Брак по записи (поставьте 1)": "", "Комментарий": ""})
    return rows
