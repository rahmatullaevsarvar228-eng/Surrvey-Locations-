import time

from fastapi.testclient import TestClient

from api.main import app

c = TestClient(app)


def test_solve_fast_and_valid():
    t0 = time.time()
    r = c.post("/api/solve", json=dict(preset="avariya", time_limit=4))
    assert r.status_code == 200
    assert time.time() - t0 < 15
    d = r.json()
    assert d["fifo"]["ok"] is False and d["fifo"]["deadlock"]["stuck_trains"]
    assert d["ai"]["umumiy"]["ok"] and d["ai"]["umumiy"]["xatolar"] == []


def test_breakdown_and_verify():
    r = c.post("/api/solve", json=dict(preset="oddiy", time_limit=3,
                                       breakdown=dict(train_id="YK00", station=4, minutes=30)))
    assert r.status_code == 200
    d = r.json()
    assert "tiklanish" in d
    v = c.post("/api/verify", json=dict(stations=d["scenario"]["stations"],
                                         trains=d["scenario"]["trains"],
                                         schedule=d["ai"]["umumiy"]["schedule"]))
    assert v.json()["konfliktlar"] == 0


def test_bad_input():
    assert c.post("/api/solve", json=dict(disruption=dict(segment=[1, 5], start=0, end=10))).status_code == 400
    assert c.post("/api/solve", json=dict(time_limit=100)).status_code == 422
