"""Pytest: validator 0 xato, AI ≤ FIFO, tupik to'g'ri aniqlanadi."""
import pytest

from engine import (make_scenario, simulate_fifo, optimise, verify, objective_value,
                    preset, run_case, apply_breakdown, Station)

TL = 4.0     # testlar uchun qisqa hisob vaqti
SEEDS = [1, 2, 3, 4, 5]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("objective", ["umumiy", "ustuvorlik"])
def test_validator_zero_errors_and_ai_not_worse(seed, objective):
    st, tr = make_scenario(seed)
    ok, sf, _ = simulate_fifo(st, tr)
    assert ok
    assert verify(st, tr, sf) == []
    ok2, sa, status = optimise(st, tr, objective=objective, time_limit=TL, workers=4)
    assert ok2
    assert verify(st, tr, sa) == []
    assert objective_value(st, tr, sa, objective) <= objective_value(st, tr, sf, objective)


def test_avariya_seed4_fifo_deadlock_ai_solves():
    st, tr, dis = preset("avariya")
    ok, _, dl = simulate_fifo(st, tr, dis)
    assert not ok
    assert len(dl["stuck_trains"]) > 0
    assert set(dl["at_station"]) == set(dl["stuck_trains"])
    ok2, sa, _ = optimise(st, tr, dis, time_limit=TL, workers=4)
    assert ok2
    assert verify(st, tr, sa, dis) == []


def test_validator_detects_violations():
    st, tr = make_scenario(1)
    ok, sf, _ = simulate_fifo(st, tr)
    bad = {k: list(v) for k, v in sf.items()}
    t = tr[0]
    s, a, d = bad[t.id][1]
    bad[t.id][1] = (s, a - 1, d)            # juda tez yetib keldi
    assert verify(st, tr, bad)
    # yopiq peregon buzilishi
    seg = (bad[t.id][0][0], bad[t.id][1][0])
    dis = dict(segment=seg, start=bad[t.id][0][2], end=bad[t.id][0][2] + 30)
    assert any("yopiq" in e for e in verify(st, tr, sf, dis))


def test_extra_track_never_hurts_with_hint():
    st, tr = make_scenario(2)
    ok, base, _ = optimise(st, tr, time_limit=TL, workers=4)
    st2 = [Station(s.name, s.km, s.tracks + (1 if j == 5 else 0)) for j, s in enumerate(st)]
    ok2, sc, _ = optimise(st2, tr, time_limit=TL, workers=4, extra_hint=base)
    assert objective_value(st2, tr, sc, "umumiy") <= objective_value(st, tr, base, "umumiy")


def test_breakdown_and_run_case():
    st, tr, _ = preset("oddiy")
    tr2 = apply_breakdown(tr, tr[0].id, 5, 40)
    res = run_case(st, tr2, None, time_limit=TL, workers=4)
    assert res["fifo"]["ok"] and res["ai"]["ok"]
    assert res["ai"]["xatolar"] == [] and res["fifo"]["xatolar"] == []
    assert res["ai"]["metrics"]["umumiy_kechikish_daq"] <= res["fifo"]["metrics"]["umumiy_kechikish_daq"]


def test_recovery_time():
    from engine import recovery_time
    st, tr, dis = preset("avariya")
    ok, sa, _ = optimise(st, tr, dis, time_limit=TL, workers=4)
    r = recovery_time(st, tr, sa, dis)
    assert 0 <= r < 1000
    st, tr, _ = preset("oddiy")
    ok, sf, _ = simulate_fifo(st, tr)
    assert recovery_time(st, tr, sf, dict(segment=(0, 1), start=5000, end=5001)) == 0
