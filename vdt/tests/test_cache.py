"""Sahna keshi (data/cache) ham mustaqil validatordan o'tishi shart."""
import json
import os

import pytest

from engine import preset, verify

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


def test_cached_obgon_variants_valid():
    from engine import add_passing_loop
    d = load("obgon.json")
    for name, s in d["ssenariylar"].items():
        st, tr, dis = preset(name)
        for r in s["reyting"]:
            assert r["tejaldi_daq"] >= 0 and r["xatolar"] == 0
        for v in s["variantlar"]:
            st2, tr2, d2, _ = add_passing_loop(st, tr, v["k"], dis)
            assert verify(st2, tr2, tup(v["oldin"]), d2) == []
            assert verify(st2, tr2, tup(v["keyin"]), d2) == []
            assert v["metrics_keyin"]["umumiy_kechikish_daq"] == v["metrics_oldin"]["umumiy_kechikish_daq"] - v["tejaldi_daq"]
