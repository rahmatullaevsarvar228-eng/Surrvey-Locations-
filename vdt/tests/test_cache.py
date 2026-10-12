"""Sahna keshi (data/cache) ham mustaqil validatordan o'tishi shart."""
import json
import os

import pytest

from engine import preset, verify, Station

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    with open(os.path.join(ROOT, "data", "cache", name), encoding="utf-8") as f:
        return json.load(f)


def tup(rows):
    return {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in rows.items()}


@pytest.mark.parametrize("name", ["oddiy", "avariya", "osish30"])
def test_cached_scenarios_valid(name):
    st, tr, dis = preset(name)
    d = load(f"{name}.json")
    for obj, res in d["ai"].items():
        assert verify(st, tr, tup(res["schedule"]), dis) == []
        if d["fifo"]["ok"]:
            k = "umumiy_kechikish_daq" if obj == "umumiy" else "vaznli_kechikish"
            assert res["metrics"][k] <= d["fifo"]["metrics"][k]
    if name == "avariya":
        assert not d["fifo"]["ok"] and d["fifo"]["deadlock"]["stuck_trains"]


def test_cached_siding_variants_valid():
    d = load("razyezd.json")
    for name, s in d["ssenariylar"].items():
        st, tr, dis = preset(name)
        assert verify(st, tr, tup(s["nazorat"]["schedule"]), dis) == []
        for v in s["variantlar"]:
            assert v["tejaldi_daq"] >= 0
            st2 = [Station(x.name, x.km, x.tracks + (1 if j == v["indeks"] else 0)) for j, x in enumerate(st)]
            assert verify(st2, tr, tup(v["schedule"]), dis) == []
            assert v["metrics"]["umumiy_kechikish_daq"] == s["nazorat"]["metrics"]["umumiy_kechikish_daq"] - v["tejaldi_daq"]
