# -*- coding: utf-8 -*-
import io
import json
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anketa_qc.remote import RemoteClient, RemoteError, combine, rows_to_frame  # noqa: E402
from anketa_qc.server import create_app  # noqa: E402
import make_demo  # noqa: E402


@pytest.fixture(scope="module")
def demo_bytes(tmp_path_factory):
    path = tmp_path_factory.mktemp("demo") / "demo.xlsx"
    make_demo.main(str(path))
    return path.read_bytes()


class FakeClient:
    """Сервер доступа в памяти — тот же протокол, что у server/Code.gs."""
    users = {"admin": ("pass-admin", "admin", True), "ali": ("pass-ali", "user", True),
             "boss": ("pass-boss", "lead", True)}
    frames = {}
    saved = {}   # «лист Решения ОТК»: {source_id: {id: решение}}

    def __init__(self, url):
        if not url.startswith("https://"):
            raise RemoteError("Адрес сервера должен начинаться с https://")
        self.user = None
        self.calls = []

    def login(self, login, password):
        u = self.users.get(login)
        if not u or u[0] != password:
            raise RemoteError("Неверный логин или пароль")
        self.user = login
        return {"token": "t", "user": {"login": login, "name": login, "role": u[1]},
                "sources": [{"id": k, "name": k} for k in self.frames]}

    def _check(self):
        if not self.users.get(self.user, (None, None, False))[2]:
            raise RemoteError("доступ закрыт администратором", auth=True)

    def call(self, action, **params):
        self._check()
        self.calls.append((action, params))
        if action == "sources":
            return {"sources": [{"id": k, "name": k} for k in self.frames]}
        if action == "add_source":
            if "docs.google.com" not in params["url"]:
                raise RemoteError("Нужна ссылка на Google-таблицу")
            self.frames[params["name"]] = pd.DataFrame({"x": [1]})
            return {"source": {"id": params["name"]}}
        if action == "delete_source":
            self.frames.pop(params["id"], None)
            return {"ok": True}
        if action == "set_decisions":
            if self.users[self.user][1] not in ("lead", "admin"):
                raise RemoteError("Решения по анкетам ставит только руководитель проекта")
            sheet = self.saved.setdefault(params["source_id"], {})
            for it in params["items"]:
                if it["decision"]:
                    sheet[it["id"]] = dict(it, by=self.user)
                else:
                    sheet.pop(it["id"], None)
            return {"decisions": list(sheet.values())}
        if action == "create_user":
            return {"login": params["login"], "password": "Abc123xyz9"}
        return {"ok": True}

    def fetch_frame(self, source_id, sheet=None):
        self._check()
        book = self.frames[source_id]
        if not isinstance(book, dict):
            book = {"data": book}
        name = sheet or next(iter(book))
        if name not in book:
            raise RemoteError(f"В источнике «{source_id}» нет листа «{name}»")
        return (source_id, source_id, book[name], list(self.saved.get(source_id, {}).values()),
                {"sheets": list(book), "sheet": name})


def login(client, who="admin"):
    res = client.post("/api/auth/login", json={"server_url": "https://script.google.com/x/exec",
                                               "login": who, "password": f"pass-{who}"})
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def test_rows_to_frame_and_combine():
    df = rows_to_frame(["a", "b", "a"], [[1, "x", 2], ["", "y"]])
    assert list(df.columns) == ["a", "b", "a.1"] and df["a"].isna().iloc[1]
    sheets = combine([("T1", df), ("T2", df.iloc[:1])])
    first = next(iter(sheets))
    assert first == "Все источники (2)" and len(sheets[first]) == 3
    assert list(sheets[first]["Источник"]) == ["T1", "T1", "T2"]
    assert set(sheets) == {first, "T1", "T2"}
    assert list(combine([("T1", df)])) == ["T1"]


def test_remote_client_maps_auth_errors(monkeypatch):
    import json as _json

    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return _json.dumps(self.body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from anketa_qc import remote
    answers = iter([{"error": "AUTH: доступ закрыт администратором"}, {"error": "Нет доступа"},
                    b"<html>"])
    def fake_urlopen(req, timeout):
        a = next(answers)
        return Resp(a) if isinstance(a, dict) else type("R", (Resp,), {"read": lambda self: a})(None)
    monkeypatch.setattr(remote.urllib.request, "urlopen", fake_urlopen)
    c = RemoteClient("https://script.google.com/x/exec")
    with pytest.raises(RemoteError) as e:
        c.call("me")
    assert e.value.auth and "закрыт" in str(e.value)
    with pytest.raises(RemoteError) as e:
        c.call("me")
    assert not e.value.auth
    with pytest.raises(RemoteError, match="не то"):
        c.call("me")
    with pytest.raises(RemoteError, match="https"):
        RemoteClient("http://evil")


def test_login_required(tmp_path):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/auth").get_json()["logged_in"] is False
    res = client.get("/api/state")
    assert res.status_code == 401 and res.get_json()["auth"]
    bad = client.post("/api/auth/login", json={"server_url": "https://s/exec", "login": "ali", "password": "x"})
    assert bad.status_code == 400 and "Неверный" in bad.get_json()["error"]
    login(client, "ali")
    assert client.get("/api/state").status_code == 200
    # обычный сотрудник не может в администрирование
    assert client.post("/api/admin/list_users", json={}).status_code == 403
    # адрес сервера и логин запоминаются, пароль — нет
    auth = client.get("/api/auth").get_json()
    assert auth["server_url"].startswith("https://") and auth["last_login"] == "ali"
    assert "pass" not in str(auth)


def test_blocked_user_is_logged_out(tmp_path, demo_bytes):
    FakeClient.frames = {"Ташкент": pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "ali")
    FakeClient.users = dict(FakeClient.users, ali=("pass-ali", "user", False))
    try:
        res = client.post("/api/source/remote", json={"ids": ["Ташкент"]})
        assert res.status_code == 401 and "закрыт" in res.get_json()["error"]
        assert client.get("/api/state").status_code == 401   # данные из памяти недоступны
    finally:
        FakeClient.users = dict(FakeClient.users, ali=("pass-ali", "user", True))


def test_admin_proxy(tmp_path):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "admin")
    res = client.post("/api/admin/create_user", json={"login": "new", "team": "Uzum"}).get_json()
    assert res["password"] == "Abc123xyz9"
    assert client.post("/api/admin/drop_database", json={}).status_code == 404


def test_team_adds_and_removes_own_sources(tmp_path):
    FakeClient.frames = {}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "ali")
    bad = client.post("/api/remote/sources/add", json={"name": "X", "url": "https://evil"})
    assert bad.status_code == 400
    lst = client.post("/api/remote/sources/add", json={"name": "Ташкент", "url": "https://docs.google.com/spreadsheets/d/A"}).get_json()
    assert [x["name"] for x in lst] == ["Ташкент"]
    assert client.post("/api/remote/sources/delete", json={"id": "Ташкент"}).get_json() == []


def test_auto_refresh_reports_new_anketas(tmp_path, demo_bytes):
    data = pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")
    FakeClient.frames = {"Поток": data.iloc[:200]}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client)
    assert client.post("/api/refresh").status_code == 400          # таблицы ещё не подключены
    state = client.post("/api/source/remote", json={"ids": ["Поток"]}).get_json()
    first = client.post("/api/refresh").get_json()   # колонки подставились сами
    assert first["summary"]["total"] == 200 and first["refresh"]["new"] == 0
    FakeClient.frames["Поток"] = data                                # в таблицу пришли новые анкеты
    second = client.post("/api/refresh").get_json()
    assert second["summary"]["total"] == len(data)
    assert second["refresh"]["new"] == len(data) - 200
    assert second["refresh"]["new_defects"] >= 1


def test_full_flow_through_api(tmp_path, demo_bytes):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client)
    data = pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")
    half = len(data) // 2
    FakeClient.frames = {"Волна — Ташкент": data.iloc[:half], "Волна — регионы": data.iloc[half:]}
    state = client.post("/api/source/remote", json={"ids": list(FakeClient.frames)}).get_json()
    assert state["config"]["sheet"] == "Все источники (2)"
    assert state["columns"][0] == "Источник"
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
    client2 = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client2)
    state2 = client2.get("/api/state").get_json()
    assert state2["config"]["remote_sources"] == list(FakeClient.frames)
    assert state2["config"]["repetition"]["values"][0]["name"] == "Uzum Bank"
    assert state2["waves"][0]["wave"] == "W1"


def test_run_requires_columns(tmp_path, demo_bytes):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client)
    client.post("/api/source/file", data={"file": (io.BytesIO(demo_bytes), "demo.xlsx")},
                content_type="multipart/form-data")
    # обязательные колонки, которых нет среди подсказок, — понятная ошибка
    state = client.get("/api/state").get_json()
    cfg = state["config"]
    cfg["mapping"]["device"] = None
    client.post("/api/config", json={"config": cfg})
    client.post("/api/sheet", json={"sheet": "Свод"})
    res = client.post("/api/run", json={})
    assert res.status_code == 400 and "Укажите колонки" in res.get_json()["error"]
    # а на листе с анкетами подсказки подставляются сами, без захода в «Колонки»
    client.post("/api/sheet", json={"sheet": "data"})
    assert client.post("/api/run", json={}).status_code == 200


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


def test_access_server_script():
    """server/Code.gs в имитации сервисов Google (tests/gas_harness.js)."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("нет Node.js")
    harness = Path(__file__).resolve().parent / "gas_harness.js"
    res = subprocess.run([node, str(harness)], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stdout + res.stderr


def test_gps_through_api(tmp_path, demo_bytes):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client)
    state = client.post("/api/source/file", data={"file": (io.BytesIO(demo_bytes), "demo.xlsx")},
                        content_type="multipart/form-data").get_json()
    assert state["suggested"]["lat"] == "_Координаты_latitude"
    cfg = state["config"]
    cfg["mapping"] = state["suggested"]
    cfg["geo"]["plan"] = client.get("/api/geo/default-plan").get_json()
    resp = client.post("/api/run", json={"config": cfg})
    # браузер не прочитает NaN — ответ должен быть строгим JSON
    json.loads(resp.data, parse_constant=lambda c: pytest.fail(f"{c} в ответе API"))
    r = resp.get_json()
    g = r["geo"]
    assert g["enabled"] and g["far"] > 0 and g["clusters_over"] > 0 and g["same"] > 0
    assert {p["inter"] for p in g["points"] if p["out_city"]} == {"Inter 08"}   # «сидит дома» за городом
    assert {p["inter"] for p in g["points"] if p["far"]} == {"Inter 04"}      # отошёл от точки на 3 км
    assert any(c["Интервьюер"] == "Inter 03" and c["Статус"] == "RED" for c in g["clusters"])
    wb = openpyxl.load_workbook(io.BytesIO(client.get("/api/export/full").data))
    assert {"GPS", "GPS скопления"} <= set(wb.sheetnames)
    # план из Excel
    buf = io.BytesIO()
    pd.DataFrame({"Город": ["Бухара"], "Широта": [39.77], "Долгота": [64.44]}).to_excel(buf, index=False)
    plan = client.post("/api/geo/plan/parse", data={"file": (io.BytesIO(buf.getvalue()), "plan.xlsx")},
                       content_type="multipart/form-data").get_json()
    assert plan["Бухара"]["points"][0]["lat"] == 39.77



def test_decisions_detail_and_clean_base(tmp_path, demo_bytes):
    data = pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")
    half = len(data) // 2
    FakeClient.frames = {"Т1": data.iloc[:half], "Т2": data.iloc[half:]}
    FakeClient.saved = {}
    app = create_app(tmp_path, client_factory=FakeClient)
    client = app.test_client()
    login(client, "boss")
    client.post("/api/source/remote", json={"ids": ["Т1", "Т2"]})
    r = client.post("/api/run", json={}).get_json()
    rv = r["summary"]["review"]
    assert rv["enabled"] and rv["can_decide"] and rv["todo"] > 0
    bad = [a for a in r["anketas"] if a["defect"]]
    first, last = bad[0], bad[-1]
    assert first["pos"] != last["pos"]

    # объяснение + исходная строка с выделенными колонками
    d = client.get(f"/api/anketa/{first['pos']}").get_json()
    assert d["issues"] and all(i["logic"] for i in d["issues"])
    cols = [v["column"] for v in d["values"]]
    assert "Источник" in cols and "_id" in cols
    assert any(v["highlight"] for v in d["values"])
    short = next((a for a in bad if "длилось" in a["reasons"]), None)
    if short:
        ds = client.get(f"/api/anketa/{short['pos']}").get_json()
        hl = {v["column"] for v in ds["values"] if v["highlight"]}
        assert {"start", "end"} <= hl

    # решения — пачкой, по двум разным таблицам-источникам
    r = client.post("/api/decisions", json={"positions": [first["pos"], last["pos"]],
                                            "decision": "Брак", "comment": "не дозвонились"}).get_json()
    assert r["summary"]["review"]["Брак"] == 2
    assert set(FakeClient.saved) == {"Т1", "Т2"}
    got = next(a for a in r["anketas"] if a["pos"] == first["pos"])
    assert got["decision"] == "Брак" and got["decision_comment"] == "не дозвонились"
    r = client.post("/api/decisions", json={"positions": [last["pos"]], "decision": "Принять"}).get_json()
    assert r["summary"]["review"]["Принять"] == 1 and r["summary"]["review"]["Брак"] == 1

    # решения переживают перезагрузку данных (читаются из «листа»)
    client.post("/api/source/remote", json={"ids": ["Т1", "Т2"]})
    r = client.post("/api/run", json={}).get_json()
    assert r["summary"]["review"]["Брак"] == 1

    # чистая база: без брака, принятая подозрительная — внутри, нерешённые — отдельно
    wb = openpyxl.load_workbook(io.BytesIO(client.get("/api/export/clean").data))
    assert {"Чистая база", "Не решено"} <= set(wb.sheetnames)
    ws = wb["Чистая база"]
    head = [c.value for c in ws[1]]
    ids = {str(row[head.index("_id")]) for row in ws.iter_rows(min_row=2, values_only=True)}
    assert str(first["id"]) not in ids and str(last["id"]) in ids
    assert len(ids) < len(data)

    # проверяется отдельный лист второй таблицы — решение уходит именно в неё
    client.post("/api/sheet", json={"sheet": "Т2"})
    r = client.post("/api/run", json={}).get_json()
    pos = r["anketas"][0]["pos"]
    before = len(FakeClient.saved.get("Т1", {}))
    client.post("/api/decisions", json={"positions": [pos], "decision": "На перезвон"})
    assert len(FakeClient.saved["Т1"]) == before
    assert str(r["anketas"][0]["id"]) in FakeClient.saved["Т2"]

    # обычный сотрудник решения ставить не может
    c2 = create_app(tmp_path / "u", client_factory=FakeClient).test_client()
    login(c2, "ali")
    c2.post("/api/source/remote", json={"ids": ["Т1"]})
    r2 = c2.post("/api/run", json={}).get_json()
    assert r2["summary"]["review"]["can_decide"] is False
    assert c2.post("/api/decisions", json={"positions": [0], "decision": "Брак"}).status_code == 403


def test_client_report(tmp_path, demo_bytes):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client)
    client.post("/api/source/file", data={"file": (io.BytesIO(demo_bytes), "demo.xlsx")}, content_type="multipart/form-data")
    r = client.post("/api/run", json={}).get_json()
    assert all("risk" in a for a in r["anketas"]) and max(a["risk"] for a in r["anketas"]) >= 70
    wb = openpyxl.load_workbook(io.BytesIO(client.get("/api/export/client").data))
    assert {"Сводка", "Причины брака", "Интервьюеры", "Чистая база"} <= set(wb.sheetnames)
    summary = {row[0]: row[1] for row in wb["Сводка"].iter_rows(min_row=4, values_only=True) if row[0]}
    assert summary["Всего анкет"] == len(r["anketas"])


def test_rejects_foreign_host(tmp_path):
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    assert client.get("/api/auth", headers={"Host": "evil.example:8765"}).status_code == 403
    assert client.get("/api/auth", headers={"Host": "127.0.0.1:51234"}).status_code == 200


def test_word_report_dashboard_payload_and_technical(tmp_path, demo_bytes):
    data = pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")
    FakeClient.frames = {"Т1": data}
    FakeClient.saved = {}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "boss")
    state = client.post("/api/source/remote", json={"ids": ["Т1"]}).get_json()
    # подсказка про технические записи и значения колонки для настройки
    assert state["technical_hint"][0]["col"] == "Тип записи"
    vals = client.get("/api/column/values?col=Тип записи").get_json()
    assert {v["value"] for v in vals} == {"Интервью", "Техническое задание (видео)"}
    cfg = state["config"]
    cfg["mapping"] = state["suggested"]
    cfg["technical"] = {"col": "Тип записи", "values": ["Техническое задание (видео)"]}
    cfg["geo"]["plan"] = client.get("/api/geo/default-plan").get_json()
    cfg["sections"] = [{"name": "Знание банков", "start": "1. Название какого банка первым приходит Вам на ум?"}]
    r = client.post("/api/run", json={"config": cfg}).get_json()
    s = r["summary"]
    assert s["technical"] == (data["Тип записи"] != "Интервью").sum() and s["interviews"] + s["technical"] == s["total"]
    tech = [a for a in r["anketas"] if a["technical"]]
    assert tech and not any(a["defect"] and any(i[0] == "too_short" for i in a["issues"]) for a in tech)
    # у каждой проблемы есть блок и короткое название — для дашбордов
    iss = [i for a in r["anketas"] for i in a["issues"]]
    assert iss and all(len(i) == 5 and i[2] and i[3] for i in iss)
    assert {a["region"] for a in r["anketas"]} >= {"г. Ташкент", "Самаркандская обл."}

    # отчёт Word: целиком и по одному городу
    from docx import Document
    resp = client.get("/api/export/word")
    assert resp.status_code == 200 and resp.headers["Content-Disposition"].split("filename=")[1].strip('"').endswith(".docx")
    doc = Document(io.BytesIO(resp.data))
    text = "\n".join(p.text for p in doc.paragraphs)
    for part in ("1. Итог", "Где брак", "Почему брак", "GPS", "Интервьюеры", "Выводы", "Комментарий руководителя"):
        assert part in text
    assert doc.inline_shapes and len(doc.inline_shapes) >= 3          # графики и карты
    one = Document(io.BytesIO(client.get("/api/export/word?city=Самарканд").data))
    table = next(t for t in one.tables if t.rows[0].cells[0].text == "Город" and t.rows[0].cells[1].text == "Регион")
    assert [row.cells[0].text for row in table.rows[1:]] == ["Самарканд"]


def test_web_scripts_parse():
    """Синтаксическая ошибка в app.js/dash.js — белый экран у пользователя."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("нет Node.js")
    web = Path(__file__).resolve().parents[1] / "anketa_qc" / "web"
    for name in ("app.js", "dash.js"):
        r = subprocess.run([node, "--check", str(web / name)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_choose_sheet_of_google_table_and_best_excel_sheet(tmp_path, demo_bytes):
    data = pd.read_excel(io.BytesIO(demo_bytes), sheet_name="data")
    FakeClient.frames = {"Т1": {"Свод": pd.DataFrame({"Город": ["Ташкент"], "Анкет": [5]}), "Анкеты": data}}
    FakeClient.saved = {}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "boss")
    # первый лист — свод без анкет: программа сама находит лист с анкетами и запоминает его
    state = client.post("/api/source/remote", json={"ids": ["Т1"]}).get_json()
    assert state["source_tabs"]["Т1"] == {"sheets": ["Свод", "Анкеты"], "sheet": "Анкеты"}
    assert state["config"]["source_sheets"] == {"Т1": "Анкеты"} and "deviceid" in state["columns"]
    # выбрать лист можно и вручную
    cfg = state["config"]
    cfg["source_sheets"] = {"Т1": "Свод"}
    client.post("/api/config", json={"config": cfg})
    state = client.post("/api/source/remote", json={"ids": ["Т1"]}).get_json()
    assert state["source_tabs"]["Т1"]["sheet"] == "Свод" and "deviceid" not in state["columns"]
    cfg = state["config"]
    cfg["source_sheets"] = {"Т1": "Анкеты"}
    client.post("/api/config", json={"config": cfg})
    client.post("/api/source/remote", json={"ids": ["Т1"]})
    r = client.post("/api/run", json={}).get_json()
    s = r["summary"]
    # «1» мониторинга: найдено само, не перепроверяется, в «нужно решить» не попадает
    assert s["rejected"] == 3 and s["rejected_info"]["col"] == "Брак (аудиоконтроль)"
    rej = [a for a in r["anketas"] if a["rejected"]]
    assert all(a["defect"] and [i[0] for i in a["issues"]] == ["external"] for a in rej)
    assert s["review"]["todo"] == sum(1 for a in r["anketas"] if (a["defect"] or a["warning"]) and not a["technical"]
                                      and not a["rejected"])
    # Excel с листом-сводом первым: программа сама берёт лист с анкетами
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"Город": ["Ташкент"], "Анкет": [5]}).to_excel(w, sheet_name="Свод", index=False)
        data.to_excel(w, sheet_name="Лист1", index=False)
    st = client.post("/api/source/file", data={"file": (io.BytesIO(buf.getvalue()), "x.xlsx")},
                     content_type="multipart/form-data").get_json()
    assert st["config"]["sheet"] == "Лист1"


def test_technical_tasks_on_separate_sheet(tmp_path):
    """Интервью на одном листе, ТЗ — на другом (отдельная форма, без города):
    интервью сразу после ТЗ не брак, если указать лист ТЗ."""
    def row(i, start, minutes, **extra):
        s = pd.Timestamp(start)
        return {"_id": 7000 + i, "deviceid": "D1", "Код интервьюера": "Inter 01", "Город": "Ургенч",
                "start": s.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": (s + pd.Timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S"), **extra}
    interviews = pd.DataFrame([row(0, "2025-09-15 10:00:00", 15), row(1, "2025-09-15 10:16:10", 15)])
    tz = pd.DataFrame([{k: v for k, v in row(9, "2025-09-15 10:15:10", 0.8).items() if k != "Город"}])
    FakeClient.frames = {"Т": {"Анкеты": interviews, "ТЗ": tz}}
    FakeClient.saved = {}
    client = create_app(tmp_path, client_factory=FakeClient).test_client()
    login(client, "boss")
    state = client.post("/api/source/remote", json={"ids": ["Т"]}).get_json()
    r = client.post("/api/run", json={}).get_json()
    second = next(a for a in r["anketas"] if a["id"] == "7001")
    assert any(i[0] == "no_rest" for i in second["issues"])        # ТЗ программа пока не видит
    cfg = state["config"]
    cfg["tech_tabs"] = {"Т": "ТЗ"}
    client.post("/api/config", json={"config": cfg})
    client.post("/api/source/remote", json={"ids": ["Т"]})
    r = client.post("/api/run", json={}).get_json()
    second = next(a for a in r["anketas"] if a["id"] == "7001")
    assert not second["issues"] and r["summary"]["technical"] == 1 and r["summary"]["interviews"] == 2
    # в окне анкеты видно, что перед ней было ТЗ
    d = client.get(f"/api/anketa/{second['pos']}").get_json()
    assert d["previous"]["technical"] and d["previous"]["kind"] == "техническое задание"
