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


def test_cached_full_plan_valid():
    from engine import add_passing_loops
    d = load("obgon.json")
    for name, s in d["ssenariylar"].items():
        st, tr, dis = preset(name)
        k_of = {r["peregon"]: r["k"] for r in s["reyting"]}
        steps = s["bosqichlar"]
        ks = [k_of[p] for p in steps[-1]["punktlar"]]
        st2, tr2, d2, _ = add_passing_loops(st, tr, ks, dis)
        full = s["toliq"]
        assert [x.name for x in st2] == [x["name"] for x in full["scenario"]["stations"]]
        assert verify(st2, tr2, tup(full["oldin"]), d2) == []
        assert verify(st2, tr2, tup(full["keyin"]), d2) == []
        # bosqichlar: tejash kamaymaydi, xato yo'q
        prev = 0
        for x in steps:
            assert x["xatolar"] == 0 and x["tejaldi_daq"] >= prev
            prev = x["tejaldi_daq"]
        assert full["metrics_keyin"]["umumiy_kechikish_daq"] == s["nazorat"] - steps[-1]["tejaldi_daq"] + \
            (full["metrics_oldin"]["umumiy_kechikish_daq"] - s["nazorat"])
