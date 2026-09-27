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
    "grid_same": ((), "Во всех вопросах блока-сетки выбран один и тот же вариант. Похоже, интервьюер "
                      "«прощёлкал» блок, не зачитывая вопросы."),
}


def _params(cfg):
    p = {}
    for key in ("thresholds", "night", "geo", "probing"):
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

    prev = None
    if any(i["code"] in ("start_gap", "no_rest", "conveyor", "overlap", "mass_open") for i in issues) and pd.notna(row["deviceid"]):
        same = df[(df["deviceid"] == row["deviceid"]) & (df["start"] < row["start"]) & ~df["technical"]].sort_values("start")
        if len(same):
            p = same.iloc[-1]
            prev = {"id": p["row_id"], "start": _fmt(p["start"]), "end": _fmt(p["end"])}
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
