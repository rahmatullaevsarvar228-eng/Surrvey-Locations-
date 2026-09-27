# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anketa_qc import config, engine, export, history  # noqa: E402


def make_row(i, dev, inter, start, minutes, city="Ташкент", phone=None, name=None, age=30, q1=None):
    s = pd.Timestamp(start)
    return {
        "_id": 1000 + i, "deviceid": dev, "Код интервьюера": inter, "Город": city,
        "start": s.strftime("%Y-%m-%dT%H:%M:%S.000+05:00"),
        "end": (s + pd.Timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.000+05:00"),
        "Номер телефона респондента": phone, "Скажите пожалуйста как вас зовут?": name,
        "Возраст": age, "Доход": 100,
        "Q1": q1[0] if q1 else None, "Q1.1": q1[1] if q1 and len(q1) > 1 else None,
        "Q1.2": q1[2] if q1 and len(q1) > 2 else None,
    }


@pytest.fixture
def cfg():
    c = config.default_config()
    c["mapping"] = config.suggest_mapping(list(make_row(0, "d", "i", "2025-09-01 10:00", 10).keys()))
    return c


def test_suggest_mapping_finds_kobo_columns(cfg):
    m = cfg["mapping"]
    assert m["device"] == "deviceid"
    assert m["start"] == "start" and m["end"] == "end"
    assert m["city"] == "Город" and m["inter"] == "Код интервьюера"
    assert m["id"] == "_id"
    assert m["phone"] == "Номер телефона респондента"
    assert m["name"] == "Скажите пожалуйста как вас зовут?"


def test_technical_checks(cfg):
    rows = [
        make_row(0, "D1", "A", "2025-09-01 10:00", 3),            # короткая
        make_row(1, "D1", "A", "2025-09-01 10:04", 40),           # старт через 4 мин, отдых 1 мин, длинная
        make_row(2, None, "B", "2025-09-01 12:00", 10),           # нет Device ID
        make_row(3, "D2", "B", "2025-09-01 02:30", 10),           # ночью
        make_row(4, "D2", "C", "2025-09-01 14:00", 10),           # D2 -> 2 кода
    ]
    res = engine.run(pd.DataFrame(rows), cfg)
    df = res["df"].set_index("row_id")
    codes = {rid: {c for c, _, _ in xs} for rid, xs in df["issues"].items()}
    assert "too_short" in codes["1000"]
    assert {"too_long", "no_rest"} <= codes["1001"]
    assert "start_gap" not in codes["1001"]
    assert "no_device" in codes["1002"]
    assert "night" in codes["1003"]           # 02:30 по местному времени, не по UTC
    assert "device_multi_inter" in codes["1004"]
    assert not df.loc["1004", "is_defect"]    # только предупреждение
    assert df.loc["1000", "is_defect"]


def test_night_uses_local_time(cfg):
    # 21:30 местного = 16:30 UTC: не ночь. Если бы переводили в UTC — ошибки не было бы,
    # а вот 06:00 местного = 01:00 UTC — должно ловиться именно как местное 06:00.
    rows = [make_row(0, "D1", "A", "2025-09-01 21:30", 10), make_row(1, "D2", "B", "2025-09-01 06:00", 10)]
    df = engine.run(pd.DataFrame(rows), cfg)["df"].set_index("row_id")
    assert not any(c == "night" for c, _, _ in df.loc["1000", "issues"])
    assert any(c == "night" for c, _, _ in df.loc["1001", "issues"])


def test_conveyor(cfg):
    rows = [make_row(i, "D1", "A", f"2025-09-01 10:{i:02d}", 1) for i in range(0, 12, 2)]
    df = engine.run(pd.DataFrame(rows), cfg)["df"]
    assert df["issues"].map(lambda xs: any(c == "conveyor" for c, _, _ in xs)).all()


def test_duplicates(cfg):
    rows = [
        make_row(0, "D1", "A", "2025-09-01 10:00", 10, phone="+998 90 123-45-67", name="Азиз Каримов"),
        make_row(1, "D2", "B", "2025-09-01 11:00", 10, phone="901234567", name="Нигора Алиева"),
        make_row(2, "D3", "C", "2025-09-01 12:00", 10, phone="999999999", name="Азиз"),
        make_row(3, "D4", "D", "2025-09-01 13:00", 10, phone="999999999", name="Азиз"),
        make_row(4, "D1", "A", "2025-09-01 14:00", 10, phone="+998 91 000-11-22", name="каримов азиз"),
        make_row(5, "D5", "E", "2025-09-01 15:00", 10, phone="+998 93 222-33-44", name="Азиз Каримов"),
    ]
    df = engine.run(pd.DataFrame(rows), cfg)["df"].set_index("row_id")
    assert any(c == "dup_phone" for c, _, _ in df.loc["1000", "issues"])
    # то же ФИО у того же интервьюера — дубликат; тёзка у другого интервьюера — нет
    assert any(c == "dup_name" for c, _, _ in df.loc["1004", "issues"])
    assert not any(c == "dup_name" for c, _, _ in df.loc["1005", "issues"])
    # заглушки телефона и одно имя без фамилии — не дубликаты
    assert not df.loc["1002", "issues"]


def test_custom_rules(cfg):
    cfg["rules"] = [
        {"name": "Молодой с доходом", "if_col": "Возраст", "if_op": "<", "if_val": "18",
         "then_col": "Доход", "then_op": "<=", "then_val": "0", "severity": "defect"},
        {"name": "Нет колонки", "if_col": "", "if_op": "", "then_col": "XXX", "then_op": "empty"},
    ]
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 10, age=16),
            make_row(1, "D2", "B", "2025-09-01 10:00", 10, age=40)]
    res = engine.run(pd.DataFrame(rows), cfg)
    df = res["df"].set_index("row_id")
    assert any(c.startswith("rule:") for c, _, _ in df.loc["1000", "issues"])
    assert not df.loc["1001", "issues"]
    assert res["rule_errors"] and "XXX" in res["rule_errors"][0]


def test_probing_and_repetition(cfg):
    cfg["probing"]["blocks"] = [{"label": "Банки", "columns": ["Q1", "Q1.1", "Q1.2"], "min_n": 3}]
    cfg["repetition"]["columns"] = ["Q1", "Q1.1", "Q1.2"]
    cfg["repetition"]["values"] = [{"name": "Uzum Bank", "variants": ["uzum", "узум"]},
                                   {"name": "TBC", "variants": ["тбс"]}]
    rows = []
    for i in range(6):
        rows.append(make_row(i, "D1", "A", f"2025-09-01 {10 + i}:00", 10,
                             q1=["Uzum", "Узум банк", "uzumbank"]))
        rows.append(make_row(10 + i, "D2", "B", f"2025-09-01 {10 + i}:00", 10,
                             q1=["TBC", "не знаю", None] if i == 0 else ["TBC", "Uzum", "Anor"]))
    res = engine.run(pd.DataFrame(rows), cfg)
    rep = {r["Интервьюер"]: r for r in res["repetition"]["rows"]}
    assert rep["A"]["Самое частое значение"] == "Uzum Bank" and rep["A"]["% повтора"] == 100.0
    assert rep["A"]["Статус"] == "RED"
    assert rep["B"]["Статус"] == "GREEN"
    df = res["df"].set_index("row_id")
    assert any(c == "probe_depth" for c, _, _ in df.loc["1010", "issues"])  # 1 ответ < 3
    statuses = {r["Ответ"]: r["Статус"] for r in res["answers"]["all"]}
    assert statuses["не знаю"].startswith("❌")
    assert statuses["Anor"].startswith("❔")
    assert statuses["Узум банк"].startswith("✅")
    assert len(res["answers"]["index"]["Uzum"]) == 11


def test_repetition_disabled_without_values(cfg):
    cfg["repetition"]["columns"] = ["Q1"]
    res = engine.run(pd.DataFrame([make_row(0, "D1", "A", "2025-09-01 10:00", 10, q1=["x"])]), cfg)
    assert res["repetition"]["enabled"] is False


def test_city_issues_and_status(cfg):
    rows = [make_row(i, "D1", "A", f"2025-09-01 {8 + i}:00", 10, city="г. Бухара") for i in range(5)]
    res = engine.run(pd.DataFrame(rows), cfg)
    texts = " ".join(x["text"] for x in res["city_issues"])
    assert "только 1 интервьюер" in texts and "100%" in texts
    assert res["city_issues"][0]["city"] == "Бухара"
    assert engine.status_for_pct(55, 50, 20) == "RED"
    assert engine.status_for_pct(25, 50, 20) == "YELLOW"
    assert engine.status_for_pct(5, 50, 20) == "GREEN"


def test_numeric_device_id_not_scientific(cfg):
    rows = [make_row(0, 356789012345678.0, "A", "2025-09-01 10:00", 10)]
    df = engine.run(pd.DataFrame(rows), cfg)["df"]
    assert df.loc[0, "deviceid"] == "356789012345678"


def test_history_streak(tmp_path):
    store = history.Store(tmp_path / "h.db")
    for wave, status in [("W1", "YELLOW"), ("W2", "RED"), ("W3", "YELLOW")]:
        store.save_wave("P", wave, [
            {"Интервьюер": "A", "Город": "Ташкент", "Анкет": 10, "Брак": 3, "% брака": 30.0,
             "Статус": status, "Предупреждений": 0},
            {"Интервьюер": "B", "Город": "Ташкент", "Анкет": 10, "Брак": 0, "% брака": 0.0,
             "Статус": "GREEN", "Предупреждений": 0},
        ])
    store.save_wave("P", "W3", [{"Интервьюер": "A", "Город": "Ташкент", "Анкет": 10, "Брак": 3,
                                 "% брака": 30.0, "Статус": "YELLOW", "Предупреждений": 0}])
    h = store.history("P")
    assert [w["wave"] for w in h["waves"]] == ["W1", "W2", "W3"]
    a = next(r for r in h["rows"] if r["Интервьюер"] == "A")
    assert a["Подряд в зоне риска"] == 3 and a["Худший статус"] == "RED"
    assert history_report_ok(h)


def history_report_ok(h):
    return export.history_report(h)[:2] == b"PK"


def test_full_report_is_xlsx(cfg):
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 3), make_row(1, "D2", "B", "2025-09-01 10:00", 10)]
    res = engine.run(pd.DataFrame(rows), cfg)
    data = export.full_report(res, engine.status_legend(cfg))
    xls = pd.ExcelFile(__import__("io").BytesIO(data))
    assert {"Брак", "Интервьюеры", "Все анкеты"} <= set(xls.sheet_names)


def test_name_duplicates_only_within_city(cfg):
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 10, city="Ташкент", name="Азиз Каримов"),
            make_row(1, "D2", "B", "2025-09-01 11:00", 10, city="Самарканд", name="Азиз Каримов")]
    df = engine.run(pd.DataFrame(rows), cfg)["df"]
    assert not df["issues"].map(bool).any()


def test_gps_checks():
    from anketa_qc import geo
    plan = {"Ташкент": {"points": [{"lat": 41.3, "lon": 69.24, "street_ru": "м. Чорсу"}]}}
    cfg = config.default_config()
    rows = []
    for i in range(6):   # A: всё в одной точке у метро
        r = make_row(i, "D1", "A", f"2025-09-01 {9 + i}:00", 10)
        r["lat"], r["lon"] = 41.3001, 69.2401
        rows.append(r)
    far = make_row(10, "D2", "B", "2025-09-01 10:00", 10)
    far["lat"], far["lon"] = 41.40, 69.40                 # ~17 км от точки
    nogps = make_row(11, "D2", "B", "2025-09-01 11:00", 10)
    nogps["lat"], nogps["lon"] = None, None
    rows += [far, nogps]
    df_in = pd.DataFrame(rows)
    cfg["mapping"] = config.suggest_mapping(list(df_in.columns))
    cfg["mapping"].update(lat="lat", lon="lon")
    cfg["geo"].update(plan=plan, max_per_point=5)
    res = engine.run(df_in, cfg)
    codes = {rid: {c for c, _, _ in xs} for rid, xs in res["df"].set_index("row_id")["issues"].items()}
    assert "geo_far" in codes["1010"] and "geo_far" not in codes["1000"]
    assert {"geo_cluster", "geo_same"} <= codes["1000"]
    assert "no_gps" in codes["1011"]
    g = res["geo"]
    assert g["enabled"] and g["with_gps"] == 7 and g["far"] == 1 and g["clusters_over"] == 1
    # geopoint одной строкой, как в Kobo
    lat, lon = geo.parse_coords(pd.Series(["41.31 69.24 450 5", "0 0", None]))
    assert lat.iloc[0] == 41.31 and lon.iloc[0] == 69.24 and lat.iloc[1:].isna().all()
    assert len(geo.default_plan()) == 14


def test_gps_plan_from_excel():
    from anketa_qc import geo
    plan = geo.plan_from_frame(pd.DataFrame({"Город": ["г. Бухара", "Бухара", "Нукус"],
                                             "Широта": [39.77, "39,78", 42.46], "Долгота": [64.44, 64.41, 59.62],
                                             "Название": ["Ляби-Хауз", None, "Площадь"]}))
    assert list(plan) == ["Бухара", "Нукус"] and len(plan["Бухара"]["points"]) == 2
    with pytest.raises(ValueError):
        geo.plan_from_frame(pd.DataFrame({"x": [1]}))


def test_quotas():
    from anketa_qc import quotas
    assert quotas.parse_bins("18-24, 25-34,60+")[2][2] == "60+"
    with pytest.raises(ValueError):
        quotas.parse_bins("молодые")
    cfg = config.default_config()
    rows = []
    for i, (city, sex, age) in enumerate([("Ташкент", "Ж", 20), ("Ташкент", "Ж", 22), ("Ташкент", "М", 40),
                                          ("Бухара", "Ж", 30), ("Бухара", "Ж", 31)]):
        r = make_row(i, f"D{i}", f"I{i}", f"2025-09-01 {9 + i}:00", 10 if i != 1 else 2, city=city)  # №1 — брак (коротко)
        r["Пол"], r["Возраст"] = sex, age
        rows.append(r)
    df_in = pd.DataFrame(rows)
    cfg["mapping"] = config.suggest_mapping(list(df_in.columns))
    cfg["quotas"] = {"by_city": True, "dims": [{"label": "Пол", "column": "Пол", "bins": ""},
                                                {"label": "Возраст", "column": "Возраст", "bins": "18-24,25-44"}],
                     "plan": [{"keys": {"Город": "Ташкент", "Пол": "Ж", "Возраст": "18-24"}, "target": 3},
                              {"keys": {"Город": "Бухара", "Пол": "Ж", "Возраст": "25-44"}, "target": 1}]}
    res = engine.run(df_in, cfg)
    q = quotas.compute(res, cfg, {})
    tash, buh = q["rows"]
    assert (tash["Засчитано"], tash["Под вопросом"], tash["Осталось"], tash["Статус"]) == (1, 1, 2, "YELLOW")
    assert (buh["Засчитано"], buh["Перебор"], buh["Статус"]) == (2, 1, "RED")
    assert q["outside_plan"][0]["Пол"] == "М"
    # брак руководителя уходит из «под вопросом» в «брак»
    pos1 = int(res["df"].set_index("row_id").at["1001", "pos"])
    q2 = quotas.compute(res, cfg, {pos1: {"decision": "Брак"}})
    assert (q2["rows"][0]["Брак"], q2["rows"][0]["Под вопросом"]) == (1, 0)
    tpl = quotas.template(res, cfg, cfg["quotas"]["plan"])
    assert len(tpl) == 3 and any(t["target"] == 3 for t in tpl)
    plan = quotas.plan_from_frame(pd.DataFrame({"Город": ["г. Ташкент"], "Пол": ["Ж"], "Возраст": ["18-24"], "План": [5]}),
                                  quotas.dim_labels(cfg))
    assert plan == [{"keys": {"Город": "Ташкент", "Пол": "Ж", "Возраст": "18-24"}, "target": 5}]


def test_gps_point_radius_quota_and_jump():
    plan = {"Ташкент": {"points": [{"lat": 41.30, "lon": 69.24, "street_ru": "Рынок", "radius_km": 0.3, "quota": 1},
                                   {"lat": 41.35, "lon": 69.30, "street_ru": "Метро"}]}}
    cfg = config.default_config()
    a = make_row(0, "D1", "A", "2025-09-01 10:00", 10); a["lat"], a["lon"] = 41.3005, 69.2405   # у рынка
    b = make_row(1, "D1", "A", "2025-09-01 10:20", 10); b["lat"], b["lon"] = 41.3010, 69.2400   # у рынка — квота 1 превышена
    c = make_row(2, "D1", "A", "2025-09-01 10:35", 10); c["lat"], c["lon"] = 41.50, 69.60       # 35+ км за 5 мин — телепорт
    d = make_row(3, "D2", "B", "2025-09-01 10:00", 10); d["lat"], d["lon"] = 41.306, 69.24      # 0.7 км: вне радиуса рынка (0.3)
    df_in = pd.DataFrame([a, b, c, d])
    cfg["mapping"] = config.suggest_mapping(list(df_in.columns))
    cfg["mapping"].update(lat="lat", lon="lon")
    cfg["geo"]["plan"] = plan
    res = engine.run(df_in, cfg)
    codes = {rid: {code for code, _, _ in xs} for rid, xs in res["df"].set_index("row_id")["issues"].items()}
    assert "geo_jump" in codes["1002"] and "geo_jump" not in codes["1001"]
    assert "geo_far" in codes["1003"] and "geo_far" not in codes["1000"]
    market = next(p for p in res["geo"]["point_stats"] if p["Точка"] == "Рынок")
    assert (market["Анкет"], market["Квота"], market["Статус"]) == (2, 1, "RED")
    assert res["geo"]["jumps"] == 1


def test_risk_score():
    assert engine.risk_score([]) == 0
    assert engine.risk_score([("conveyor", "defect", "")]) == 70
    # два средних сигнала складываются: 1 − 0.6·0.5 = 0.7
    assert engine.risk_score([("start_gap", "defect", ""), ("too_short", "defect", "")]) == 70
    assert engine.risk_score([("rule:X", "warning", "")]) == 25


def _codes(res):
    return {rid: {c for c, _, _ in xs} for rid, xs in res["df"].set_index("row_id")["issues"].items()}


def test_overlap_and_mass_open(cfg):
    # 3 анкеты открыты за минуту и заполняются параллельно, потом честная анкета
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00:00", 15),
            make_row(1, "D1", "A", "2025-09-01 10:00:30", 25),
            make_row(2, "D1", "A", "2025-09-01 10:01:00", 35),
            make_row(3, "D1", "A", "2025-09-01 11:00:00", 15),
            make_row(4, "D2", "B", "2025-09-01 10:00:00", 15),
            make_row(5, "D2", "B", "2025-09-01 10:20:00", 15)]
    codes = _codes(engine.run(pd.DataFrame(rows), cfg))
    assert {"overlap", "mass_open"} <= codes["1001"] and {"overlap", "mass_open"} <= codes["1002"]
    assert "overlap" not in codes["1000"] and "mass_open" in codes["1000"]
    assert not codes["1003"] and not codes["1004"] and not codes["1005"]
    # отрицательный «отдых» — это наложение, а не «нет перерыва»
    assert "no_rest" not in codes["1001"]


def test_technical_records_skip_interview_checks(cfg):
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 15),
            make_row(1, "D1", "A", "2025-09-01 10:16", 1),     # видео по заданию: 1 минута
            make_row(2, "D1", "A", "2025-09-01 10:22", 15)]
    for r, kind in zip(rows, ["Интервью", "Техническое задание (видео)", "Интервью"]):
        r["Тип записи"] = kind
    df_in = pd.DataFrame(rows)
    from anketa_qc import blocks
    hint = blocks.suggest_technical(df_in)
    assert hint and hint[0]["col"] == "Тип записи" and hint[0]["values"] == ["Техническое задание (видео)"]
    # распознаётся само — без настройки
    res = engine.run(df_in, cfg)
    codes = _codes(res)
    assert not codes["1001"] and not codes["1002"]
    df = res["df"].set_index("row_id")
    assert df.loc["1001", "technical"] and not df.loc["1001", "completed"]
    assert res["technical_info"]["auto"] and res["technical_info"]["n"] == 1
    # если выключить автоопределение — видео выглядит как короткая анкета без перерыва
    cfg["technical"] = {"col": None, "values": [], "auto": False}
    codes = _codes(engine.run(df_in, cfg))
    assert {"too_short", "no_rest"} <= codes["1001"]


def test_gap_after_technical_task_is_not_defect(cfg):
    """Интервью → сразу видео по заданию → через секунды следующее интервью:
    не брак. Интервью → через 30 секунд следующее интервью: брак."""
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00:00", 15),          # до 10:15:00
            make_row(1, "D1", "A", "2025-09-01 10:15:10", 0.7),         # видео до 10:15:52
            make_row(2, "D1", "A", "2025-09-01 10:15:53", 15),          # до 10:30:53
            make_row(3, "D1", "A", "2025-09-01 10:31:23", 15),          # через 30 с после интервью
            make_row(4, "D1", "A", "2025-09-01 11:00:00", 15)]
    for r, kind in zip(rows, ["Интервью", "Видео по заданию", "Интервью", "Интервью", "Интервью"]):
        r["Тип записи"] = kind
    res = engine.run(pd.DataFrame(rows), cfg)
    codes = _codes(res)
    assert not codes["1001"] and not codes["1002"] and not codes["1004"]
    assert "no_rest" in codes["1003"]
    text = next(t for c, _, t in res["df"].set_index("row_id").loc["1003", "issues"] if c == "no_rest")
    assert "1002" in text and "0.5 мин" in text


def test_out_of_city_and_region(cfg):
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 15, city="Самарканд"),
            make_row(1, "D1", "A", "2025-09-01 12:00", 15, city="Самарканд"),
            make_row(2, "D2", "B", "2025-09-01 12:00", 15, city="Qarshi shahri")]
    rows[0]["lat"], rows[0]["lon"] = 39.655, 66.96          # центр Самарканда
    rows[1]["lat"], rows[1]["lon"] = 39.8989, 66.2561       # это Каттакурган
    rows[2]["lat"], rows[2]["lon"] = 38.86, 65.79
    df_in = pd.DataFrame(rows)
    cfg["mapping"] = config.suggest_mapping(list(df_in.columns))
    cfg["mapping"].update(lat="lat", lon="lon")
    res = engine.run(df_in, cfg)
    codes = _codes(res)
    assert "geo_city" in codes["1001"] and "geo_city" not in codes["1000"] and "geo_city" not in codes["1002"]
    text = next(t for c, _, t in res["df"].set_index("row_id").loc["1001", "issues"] if c == "geo_city")
    assert "Каттакурган" in text
    df = res["df"].set_index("row_id")
    assert df.loc["1000", "region"] == "Самаркандская обл." and df.loc["1002", "region"] == "Кашкадарьинская обл."
    assert res["geo"]["out_city"] == 1


def test_sections_blocks_required_and_grid(cfg):
    rows = []
    for i in range(3):
        r = make_row(i, "D1", "A", f"2025-09-01 1{i}:00", 15, name=["Азиз Каримов", "Нигора Алиева", "Бобур Олимов"][i])
        for k in range(5):
            r[f"grp_brand/g{k}"] = "Знаю" if i == 1 else (None if i == 2 else ["Знаю", "Не знаю"][k % 2])
        rows.append(r)
    df_in = pd.DataFrame(rows)
    from anketa_qc import blocks
    auto = blocks.build_sections(df_in.columns, {"sections": []})
    assert [s["name"] for s in auto] == ["Brand"]
    cfg["completed_cols"] = ["Скажите пожалуйста как вас зовут?"]
    cfg["sections"] = [{"name": "Знание брендов", "start": "grp_brand/g0", "required": True, "grid": True}]
    res = engine.run(df_in, cfg)
    df = res["df"].set_index("row_id")
    codes = _codes(res)
    assert "grid_same" in codes["1001"] and "block_empty" in codes["1002"] and not codes["1000"]
    i = [c for c, _, _ in df.loc["1002", "issues"]].index("block_empty")
    assert df.loc["1002", "blocks"][i] == "Знание брендов"
    assert df.loc["1002", "primary"] == "block_empty"


def test_rejected_by_monitoring_not_rechecked(cfg):
    """Группа мониторинга поставила «1» — анкета уже брак: не перепроверяется,
    одна причина «брак по аудиоконтролю», в завершённые (квоты, норма) не идёт."""
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00", 2),       # короткая, но уже отбракована
            make_row(1, "D1", "A", "2025-09-01 10:30", 15),
            make_row(2, "D2", "B", "2025-09-01 11:00", 15)]
    rows += [make_row(3 + k, f"D{3 + k}", f"C{k}", "2025-09-01 12:00", 15) for k in range(5)]
    for r in rows:
        r["Брак (аудио)"] = None
    rows[0]["Брак (аудио)"] = 1
    rows[2]["Брак (аудио)"] = 0
    df_in = pd.DataFrame(rows)
    from anketa_qc import blocks
    assert blocks.rejected_candidates(df_in)[0]["col"] == "Брак (аудио)"
    res = engine.run(df_in, cfg)
    df = res["df"].set_index("row_id")
    assert [c for c, _, _ in df.loc["1000", "issues"]] == ["external"]
    assert df.loc["1000", "is_defect"] and df.loc["1000", "rejected"] and not df.loc["1000", "completed"]
    assert not df.loc["1001", "issues"] and not df.loc["1002", "issues"]
    assert res["rejected_info"]["n"] == 1 and res["rejected_info"]["auto"]
    # колонка, где «1» у всех — не отметка брака
    df_in["Брак (аудио)"] = 1
    assert not blocks.rejected_candidates(df_in)
    # выключили — снова обычная проверка
    df_in["Брак (аудио)"] = [1, None, 0] + [None] * 5
    cfg["rejected"] = {"col": None, "values": ["1"], "auto": False}
    codes = _codes(engine.run(df_in, cfg))
    assert "too_short" in codes["1000"] and "external" not in codes["1000"]


def test_technical_detection_variants(cfg):
    from anketa_qc import blocks
    # «ТЗ» целым словом; «отзыв» (внутри есть «тз») — не ТЗ
    df = pd.DataFrame({"Анкета тури": ["Сўровнома", "ТЗ", "Сўровнома", "ТЗ"],
                       "Мнение": ["отзыв", "хорошо", "отзыв", "нет"]})
    c = blocks.technical_candidates(df)
    assert c[0]["col"] == "Анкета тури" and c[0]["values"] == ["ТЗ"] and c[0]["sure"]
    assert all(x["col"] != "Мнение" for x in c)
    # колонка с видеофайлом, заполненная у части записей
    df = pd.DataFrame({"Q7": ["1695.mp4", None, None, "1702.mp4", None]})
    c = blocks.technical_candidates(df)
    assert c and c[0]["mode"] == "filled" and c[0]["sure"]


def test_technical_rows_without_city_are_kept(cfg):
    """ТЗ из отдельной формы: без города, но с устройством и временем —
    нужно в цепочке, чтобы следующее интервью не стало «без перерыва»."""
    from anketa_qc.blocks import TECH_SHEET_COL
    rows = [make_row(0, "D1", "A", "2025-09-01 10:00:00", 15),
            make_row(1, "D1", "A", "2025-09-01 10:15:30", 15)]
    tech = make_row(9, "D1", "A", "2025-09-01 10:15:02", 0.3, city=None)
    tech[TECH_SHEET_COL] = "да"
    res = engine.run(pd.DataFrame(rows + [tech]), cfg)
    codes = _codes(res)
    assert not codes["1001"], codes["1001"]
    assert res["df"]["technical"].sum() == 1 and res["technical_info"]["sheet_rows"] == 1
    # без листа с ТЗ та же пара интервью — брак «нет перерыва»
    assert "no_rest" in _codes(engine.run(pd.DataFrame(rows), cfg))["1001"]


def _survey(n_inter=6, per=20, seed=3):
    """Анкета с 20 вопросами-оценками и отметками времени блоков."""
    import random
    rnd = random.Random(seed)
    rows, k = [], 0
    for it in range(n_inter):
        t = pd.Timestamp("2025-09-01 09:00")
        for j in range(per):
            r = make_row(k, f"D{it}", f"I{it}", str(t), 20)
            for q in range(20):
                r[f"Q{q}"] = rnd.choice([1, 2, 3, 3, 4, 4, 5])
            r["t2"] = (t + pd.Timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
            r["t3"] = (t + pd.Timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")
            rows.append(r)
            t += pd.Timedelta(minutes=40)
            k += 1
    return rows


def test_near_duplicates_percent_match(cfg):
    rows = _survey()
    copy = dict(rows[5], _id=9999, deviceid="D0", start="2025-09-01T23:00:00.000+05:00", end="2025-09-01T23:20:00.000+05:00")
    rows.append(copy)                                       # полная копия анкеты 1005
    near = dict(rows[7], _id=9998, start="2025-09-02T08:00:00.000+05:00", end="2025-09-02T08:20:00.000+05:00")
    for q in range(3):
        near[f"Q{q}"] = 5 if near[f"Q{q}"] != 5 else 1       # 3 ответа из ~25 изменены
    rows.append(near)
    res = engine.run(pd.DataFrame(rows), cfg)
    df = res["df"].set_index("row_id")
    sev = {rid: {c: s for c, s, _ in xs} for rid, xs in df["issues"].items()}
    assert sev["9999"]["near_dup"] == "defect" and sev["1005"]["near_dup"] == "defect"
    assert sev["9998"]["near_dup"] == "warning"
    others = [rid for rid, x in sev.items() if "near_dup" in x and rid not in ("9999", "1005", "9998", "1007")]
    assert not others, others                              # у честных случайных анкет копий нет


def test_block_fast_and_answer_patterns(cfg):
    rows = _survey()
    for r in rows:
        if r["Код интервьюера"] == "I2":                    # «пролетает» второй блок
            s = pd.Timestamp(r["start"][:19])
            r["t3"] = (s + pd.Timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%S")
        if r["Код интервьюера"] == "I4":                    # «придумывает»: почти всё 5
            for q in range(20):
                r[f"Q{q}"] = 5
    res = engine.run(pd.DataFrame(rows), cfg)
    df = res["df"]
    fast = set(df.loc[df["issues"].map(lambda xs: any(c == "block_fast" for c, _, _ in xs)), "inter"])
    assert fast == {"I2"}
    assert [b["block"] for b in res["block_times"]] == ["старт → t2", "t2 → t3", "t3 → финиш"]
    pats = {p["inter"] for p in res["answer_patterns"]}
    assert pats == {"I4"}, res["answer_patterns"]


def test_no_false_alarms_on_real_kobo_like_columns(cfg):
    """Вопросы анкеты, похожие на служебные отметки, не должны включать
    автоопределение: «Состоите ли вы в браке? Да» — не брак мониторинга,
    профессия «Техник» — не техническое задание, варианты 0/1 одного вопроса
    и колонка «Страна» — не делают анкеты «копиями»."""
    import random
    from anketa_qc import blocks
    rnd = random.Random(1)
    rows = []
    for k in range(300):
        r = make_row(k, f"D{k % 10}", f"I{k % 10}", f"2025-09-0{1 + (k // 10) // 12} {9 + (k // 10) % 12}:00", 20)
        r["Состоите ли вы в браке?"] = rnd.choice(["Да", "Нет"])
        r["Брак зарегистрирован"] = rnd.choice(["1", "0"])                  # вопрос, а не отметка мониторинга
        r["Вид деятельности"] = rnd.choice(["Техник", "Учитель", "Врач", "Студент"])
        r["Причина отказа"] = rnd.choice([None, "нет времени"])
        r["Страна"] = "Узбекистан"
        chosen = set(rnd.sample(range(25), 2))
        for o in range(25):
            r[f"Q5/opt{o}"] = 1 if o in chosen else 0
        for q in range(20):
            r[f"Q{10 + q}"] = rnd.choice(["Да", "Нет", "Не знаю"])
        rows.append(r)
    df_in = pd.DataFrame(rows)
    assert not [c for c in blocks.technical_candidates(df_in) if c["sure"]]
    assert all(c["col"] not in ("Состоите ли вы в браке?", "Причина отказа") for c in blocks.rejected_candidates(df_in))
    res = engine.run(df_in, cfg)
    df = res["df"]
    assert not df["technical"].any()
    assert not df["rejected"].any()                         # «Брак зарегистрирован» 1/0 — ответ, не отметка
    assert not df["issues"].map(lambda xs: any(c == "near_dup" for c, _, _ in xs)).any()
    assert not res["answer_patterns"]
