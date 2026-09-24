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
        make_row(1, "D2", "B", "2025-09-01 11:00", 10, phone="901234567", name="каримов азиз"),
        make_row(2, "D3", "C", "2025-09-01 12:00", 10, phone="999999999", name="Азиз"),
        make_row(3, "D4", "D", "2025-09-01 13:00", 10, phone="999999999", name="Азиз"),
    ]
    df = engine.run(pd.DataFrame(rows), cfg)["df"].set_index("row_id")
    assert any(c == "dup_phone" for c, _, _ in df.loc["1000", "issues"])
    assert any(c == "dup_name" for c, _, _ in df.loc["1001", "issues"])
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
