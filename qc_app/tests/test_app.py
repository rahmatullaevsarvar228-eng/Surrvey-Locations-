# -*- coding: utf-8 -*-
import io
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anketa_qc import sources  # noqa: E402
from anketa_qc.server import create_app  # noqa: E402
import make_demo  # noqa: E402


@pytest.fixture(scope="module")
def demo_bytes(tmp_path_factory):
    path = tmp_path_factory.mktemp("demo") / "demo.xlsx"
    make_demo.main(str(path))
    return path.read_bytes()


def test_sheet_id_from_url():
    url = "https://docs.google.com/spreadsheets/d/1AbC-xyz_123/edit#gid=0"
    assert sources.sheet_id_from_url(url) == "1AbC-xyz_123"
    with pytest.raises(sources.SourceError):
        sources.sheet_id_from_url("https://example.com/table")


def test_google_login_page_is_rejected(monkeypatch):
    class Resp:
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def read(self):
            return b"<html>Sign in</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(sources.urllib.request, "urlopen", lambda *a, **k: Resp())
    with pytest.raises(sources.SourceError, match="закрыта"):
        sources.read_google_public("https://docs.google.com/spreadsheets/d/abc/edit")


def test_google_public_reads_xlsx(monkeypatch, demo_bytes):
    class Resp:
        headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

        def read(self):
            return demo_bytes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(sources.urllib.request, "urlopen", lambda *a, **k: Resp())
    sheets = sources.read_google_public("https://docs.google.com/spreadsheets/d/abc/edit")
    assert set(sheets) == {"data", "Свод"}


def test_full_flow_through_api(tmp_path, demo_bytes):
    client = create_app(tmp_path).test_client()
    state = client.post("/api/source/file", data={"file": (io.BytesIO(demo_bytes), "demo.xlsx")},
                        content_type="multipart/form-data").get_json()
    assert state["sheets"] == ["data", "Свод"] and state["config"]["sheet"] == "data"
    cfg = state["config"]
    cfg["mapping"] = state["suggested"]
    cols = state["columns"]
    first = next(i for i, c in enumerate(cols) if "первым приходит" in c)
    cfg["probing"]["blocks"] = [{"label": "Банки", "columns": cols[first:first + 7], "min_n": 4}]
    cfg["repetition"]["columns"] = cols[first:first + 7]
    cfg["repetition"]["values"] = [{"name": "Uzum Bank", "variants": ["uzum", "узум"]}]

    res = client.post("/api/run", json={"config": cfg})
    assert res.status_code == 200, res.get_json()
    r = res.get_json()
    assert r["summary"]["total"] > 300 and r["summary"]["defects"] > 0
    red = {x["Интервьюер"] for x in r["interviewers"] if x["Статус"] == "RED"}
    assert {"Inter 03", "Inter 08"} <= red
    assert r["repetition"]["enabled"]

    who = client.get("/api/answers/who", query_string={"answer": "Uzum Bank"}).get_json()
    assert who and {"ID анкеты", "Интервьюер"} <= set(who[0])

    data = client.get("/api/export/full").data
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb["Интервьюеры"]
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref
    assert ws["A1"].fill.fgColor.rgb.endswith("1F4E78")

    hist = client.post("/api/history/save", json={"wave": "W1"}).get_json()
    assert hist["waves"][0]["wave"] == "W1"
    # настройки проекта переживают перезапуск приложения
    state2 = create_app(tmp_path).test_client().get("/api/state").get_json()
    assert state2["config"]["repetition"]["values"][0]["name"] == "Uzum Bank"
    assert state2["waves"][0]["wave"] == "W1"


def test_run_requires_columns(tmp_path, demo_bytes):
    client = create_app(tmp_path).test_client()
    client.post("/api/source/file", data={"file": (io.BytesIO(demo_bytes), "demo.xlsx")},
                content_type="multipart/form-data")
    res = client.post("/api/run", json={})
    assert res.status_code == 400 and "Укажите колонки" in res.get_json()["error"]


def test_large_file_memory_friendly(tmp_path):
    """1500 анкет × 20 открытых колонок: общие данные (индекс ответов) не
    копируются на каждую строку, прогон укладывается в секунды."""
    import time
    from anketa_qc import config, engine
    n = 1500
    df = pd.DataFrame({
        "deviceid": [f"d{i % 60}" for i in range(n)], "inter": [f"I{i % 60}" for i in range(n)],
        "city": [f"C{i % 7}" for i in range(n)],
        "start": pd.date_range("2025-09-01 08:00", periods=n, freq="7min").astype(str),
        "end": (pd.date_range("2025-09-01 08:00", periods=n, freq="7min") + pd.Timedelta(minutes=6)).astype(str),
        **{f"q{j}": [f"бренд {(i * j) % 13}" for i in range(n)] for j in range(20)},
    })
    cfg = config.default_config()
    cfg["mapping"].update(device="deviceid", inter="inter", city="city", start="start", end="end")
    cfg["probing"]["blocks"] = [{"label": "Q", "columns": [f"q{j}" for j in range(20)], "min_n": 3}]
    t = time.time()
    res = engine.run(df, cfg)
    assert time.time() - t < 30
    assert "issues" in res["df"] and "answers" not in res["df"].columns
