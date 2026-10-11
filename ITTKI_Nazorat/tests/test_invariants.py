"""Random-project invariant checks for the ITTKI engine (3 seeds x 3 000 = 9 000 projects x 2 frameworks x 3 settings)."""
import random
from datetime import date, timedelta
from ittki.core.engine import *

def rd(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))

def random_project():
    K = list(CRITERIA); cats = sorted(ALL_CATEGORIES); s0 = date(2022, 1, 1)
    asm = []
    for _ in range(random.randint(0, 3)):
        ans = {k: random.choice(["yes"] * 6 + ["no", "expert"]) for k in K}
        ev = {k: "DOC" for k in K if random.random() < .95}
        asm.append(Assessment(rd(s0, date(2025, 1, 1)), ans, ev))
    return Project(
        "x", random.random() < .9,
        rd(s0, date(2023, 6, 1)) if random.random() < .85 else None,
        rd(date(2023, 6, 1), date(2025, 6, 1)) if random.random() < .7 else None,
        rd(date(2023, 1, 1), date(2026, 1, 1)) if random.random() < .2 else None,
        random.choice([0, 12, 36, 60, 96, 120]), asm,
        [Cost(rd(s0, date(2025, 12, 31)), random.randint(1, 10**9), random.choice(cats)) for _ in range(random.randint(0, 25))],
        scope=random.choice(["rnd"] * 8 + ["mineral_exploration", "contract_for_customer"]),
        impairment_event=(rd(s0, date(2027, 1, 1)), random.randint(0, 3 * 10**9)) if random.random() < .3 else None,
        impairment_test_dates=[rd(s0, date(2026, 1, 1))] if random.random() < .5 else [],
        expected_net_benefit=random.randint(0, 5 * 10**9) if random.random() < .3 else None)

def check_project(p):
    total = sum(c.amount for c in p.costs)
    for fw in FRAMEWORKS:
        for st in (Settings(), Settings(amort_start="next_month"), Settings(amort_start="same_month")):
            r = evaluate(p, fw, st, as_of=date(2026, 6, 30))
            if p.scope == "rnd":
                assert r["capitalized"] + r["expensed"] == total
                assert sum(x["amount"] for x in r["rows"]) == total
                assert r["capitalized"] == sum(x["amount"] for x in r["rows"] if x["treatment"] == "capitalize")
                if fw == "NAS11" and p.expected_net_benefit is not None:
                    assert r["capitalized"] <= p.expected_net_benefit
            sch = schedule(r, p, st)
            assert all(x["closing"] >= 0 and x["amortization"] >= 0 and x["impairment"] >= 0 for x in sch)
            for x in sch:
                assert x["opening"] - x["amortization"] - x["impairment"] == x["closing"]
            for x, y in zip(sch, sch[1:]):
                assert y["opening"] == x["closing"]
            if sch and not p.abandoned_on and len(sch) == r["amort_months"]:
                assert sch[-1]["closing"] == 0
            assert 0 <= r["writeoff"] <= r["capitalized"]
            if fw == "NAS11":
                assert r["amort_months"] <= 60
            prev = None
            for at in (date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31), date(2026, 12, 31), date(2040, 1, 1)):
                ca = carrying_amount(r, p, at, st)
                assert 0 <= ca <= r["capitalized"]
                if p.available_for_use and at >= p.available_for_use and prev is not None and prev[0] >= p.available_for_use:
                    assert ca <= prev[1]          # after availability carrying never grows
                prev = (at, ca)

def test_invariants():
    for seed in (1, 2, 3):
        random.seed(seed)
        for _ in range(3000):
            check_project(random_project())

if __name__ == "__main__":
    test_invariants(); print("INVARIANTS OK")
