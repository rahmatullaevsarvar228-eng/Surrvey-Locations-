from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import Settings
from app.services.weather import WeatherClient

FIELD = {"crop": "paxta", "soil": "orta", "method": "egat", "area_ha": 2.5}


@pytest.fixture
def api(settings: Settings) -> TestClient:
    def no_net(url: str) -> Any:
        raise OSError("oflayn")
    wc = WeatherClient(settings.weather_dir, getter=no_net, sleep=lambda s: None)
    return TestClient(create_app(settings, wc))


def test_health_and_demo_list(api: TestClient) -> None:
    assert api.get("/api/health").json() == {"ok": True, "caches": 2}
    js = api.get("/api/demo").json()
    assert [c["id"] for c in js["caches"]] == ["test_2025", "sintetik_2025"]
    assert js["caches"][1]["synthetic"] is True
    one = api.get("/api/demo/test_2025").json()
    assert one["meta"]["place"] == "Test" and len(one["days"]) == 245
    r = api.get("/api/demo/yoq")
    assert r.status_code == 404 and "make cache" in r.json()["detail"]


def test_advice_demo(api: TestClient) -> None:
    r = api.post("/api/advice", json={"field": FIELD, "last_irrigation": "2025-06-28",
                                      "cache_id": "test_2025", "today": "2025-07-10", "lang": "ru"})
    assert r.status_code == 200, r.text
    js = r.json()
    assert js["advice"]["holat"] in {"bugun", "tez_orada", "kerak_emas"}
    assert js["source"]["kind"] == "demo" and "Демо" in js["source"]["text"]
    d = api.post("/api/advice", json={"field": FIELD, "last_irrigation": "2025-07-01",
                                      "cache_id": "test_2025"})
    assert d.json()["source"]["today"] == "2025-07-14"      # ekish + 90 kun


def test_advice_errors(api: TestClient) -> None:
    r = api.post("/api/advice", json={"field": FIELD, "last_irrigation": "2025-07-01"})
    assert r.status_code == 422
    r = api.post("/api/advice", json={"field": FIELD, "last_irrigation": "2025-07-01", "mode": "live"})
    assert r.status_code == 422 and "ekish" in r.json()["detail"]
    live = {**FIELD, "planting": "2025-04-15"}
    r = api.post("/api/advice", json={"field": live, "last_irrigation": "2025-07-01", "mode": "live"})
    assert r.status_code == 503 and "Ob-havo" in r.json()["detail"]
    r = api.post("/api/advice", json={"field": {**FIELD, "crop": "olma"}, "last_irrigation": "2025-07-01"})
    assert r.status_code == 422


def test_simulate(api: TestClient) -> None:
    r = api.post("/api/simulate", json={"field": FIELD, "cache_id": "test_2025",
                                        "habit": {"every_days": 10, "mm": 150}})
    js = r.json()
    assert r.status_code == 200 and js["field"]["planting"] == "2025-04-15"
    assert js["fao"]["suv_m3_ga"] > 0 and js["habit"]["sugorishlar"] > 0
    assert len(js["fao"]["rows"]) == 195
    r = api.post("/api/simulate", json={"field": {**FIELD, "planting": "2026-04-15"},
                                        "cache_id": "test_2025"})
    assert r.status_code == 422


def test_demand(api: TestClient) -> None:
    js = api.get("/api/demand", params={"cache_id": "test_2025", "today": "2025-07-10"}).json()
    assert js["today"] == "2025-07-10" and len(js["days"]) == 7 and len(js["fields"]) == 8
    assert api.get("/api/demand", params={"cache_id": "test_2025"}).json()["today"] == "2025-07-14"


def test_spa_served(settings: Settings, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>suv</html>")
    (dist / "favicon.svg").write_text("<svg/>")
    (dist / "assets" / "a.js").write_text("1")
    c = TestClient(create_app(settings.model_copy(update={"web_dist": dist})))
    assert c.get("/").text == "<html>suv</html>"
    assert c.get("/sim").text == "<html>suv</html>"
    assert c.get("/favicon.svg").text == "<svg/>"
    assert c.get("/assets/a.js").text == "1"
    assert c.get("/api/health").json()["ok"]
