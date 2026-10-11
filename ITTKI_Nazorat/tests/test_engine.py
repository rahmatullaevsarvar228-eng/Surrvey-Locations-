"""Reference scenarios for the ITTKI engine. Run: python test_engine.py  (or pytest)."""
from datetime import date as d
from ittki.core.engine import *

KEYS = list(CRITERIA)
M = 1_000_000

def yes_all(on, **override):
    ans = {k: "yes" for k in KEYS}
    ev = {k: f"DOC-{k[:2]}-{on}" for k in KEYS}
    for k, v in override.items():
        full = next(x for x in KEYS if x.startswith(k))
        if v == "noevidence":
            ev.pop(full)
        else:
            ans[full] = v
    return Assessment(on, ans, ev)

def base_costs():
    return [Cost(d(2024, 2, 10), 100 * M, "salary"),          # research stage
            Cost(d(2024, 5, 10), 200 * M, "materials"),       # development, before criteria met
            Cost(d(2024, 8, 10), 300 * M, "salary"),          # capitalize
            Cost(d(2024, 9, 10), 50 * M, "training"),         # excluded category
            Cost(d(2024, 10, 10), 40 * M, "general_admin"),   # excluded category
            Cost(d(2024, 11, 10), 250 * M, "depreciation")]   # capitalize

def proj(**kw):
    p = dict(name="S", phases_separable=True, development_start=d(2024, 4, 1),
             available_for_use=d(2025, 1, 1), abandoned_on=None, useful_life_months=96,
             assessments=[yes_all(d(2024, 7, 1))], costs=base_costs(),
             impairment_test_dates=[d(2024, 12, 20)])
    p.update(kw)
    return Project(**p)

def both(p, s=Settings()):
    return evaluate(p, "IAS38", s), evaluate(p, "NAS11", s)

def has(res, code):
    return any(code in w for w in res["warnings"])

def test_s1_research_only():
    a, b = both(proj(development_start=None, available_for_use=None, assessments=[]))
    assert a["capitalized"] == b["capitalized"] == 0 and a["expensed"] == 940 * M

def test_s2_base_and_amortization():
    p = proj()
    a, b = both(p)
    assert a["capitalized"] == b["capitalized"] == 550 * M
    assert a["amort_months"] == 96 and b["amort_months"] == 60          # BHMS 11, 16-band
    sa, sb = schedule(a, p), schedule(b, p)
    assert sa[0]["period_end"] == d(2025, 1, 31)                        # available on day 1 -> same month
    assert len(sa) == 96 and sum(x["amortization"] for x in sa) == 550 * M and sa[-1]["closing"] == 0
    assert len(sb) == 60 and sum(x["amortization"] for x in sb) == 550 * M
    r = reconcile(p, d(2025, 12, 31))                                   # 12 months amortized
    assert r["IAS38_carrying"] == 550 * M - 12 * (550 * M // 96)
    assert r["NAS11_carrying"] == 550 * M - 12 * (550 * M // 60)
    assert r["difference"] == r["IAS38_carrying"] - r["NAS11_carrying"] > 0

def test_s2b_amortization_start_settings():
    p = proj(available_for_use=d(2025, 1, 15))
    a = evaluate(p, "IAS38")
    assert schedule(a, p)[0]["period_end"] == d(2025, 2, 28)            # auto: mid-month -> next month
    assert schedule(a, p, Settings(amort_start="same_month"))[0]["period_end"] == d(2025, 1, 31)
    p2 = proj()
    assert schedule(evaluate(p2, "IAS38"), p2, Settings(amort_start="next_month"))[0]["period_end"] == d(2025, 2, 28)

def test_s3_no_future_benefit():
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K4="no")]))
    assert a["capitalized"] == b["capitalized"] == 0

def test_s4_ability_criterion_difference():
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K3="no")]))
    assert a["capitalized"] == 0 and b["capitalized"] == 550 * M

def test_s5_yes_without_evidence():
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K5="noevidence")]))
    assert a["capitalized"] == b["capitalized"] == 0 and has(a, "E1") and has(b, "E1")

def test_s6_phases_not_separable():
    a, b = both(proj(phases_separable=False))
    assert a["capitalized"] == b["capitalized"] == 0

def test_s7_abandoned_before_ready():
    p = proj(available_for_use=None, abandoned_on=d(2025, 3, 1))
    a, b = both(p)
    assert a["writeoff"] == b["writeoff"] == 550 * M and a["amort_months"] == 0
    assert carrying_amount(a, p, d(2025, 2, 28)) == 550 * M
    assert carrying_amount(a, p, d(2025, 3, 1)) == 0

def test_s8_expert_then_confirmed():
    a, b = both(proj(assessments=[yes_all(d(2024, 7, 1), K1="expert"), yes_all(d(2024, 10, 1))]))
    assert a["capitalized"] == b["capitalized"] == 250 * M and a["first_met_on"] == d(2024, 10, 1)

def test_s9_annual_impairment_test_ias_only():
    # the app passes as_of = today; year-ends after as_of are not checked
    p = proj(available_for_use=None, impairment_test_dates=[])
    a, b = evaluate(p, "IAS38", as_of=d(2025, 1, 31)), evaluate(p, "NAS11", as_of=d(2025, 1, 31))
    assert has(a, "E5") and not has(b, "E5")
    assert not has(evaluate(p, "IAS38", as_of=d(2024, 12, 30)), "E5")   # year not closed yet
    p_ok = proj(available_for_use=None, impairment_test_dates=[d(2024, 12, 20)])
    assert not has(evaluate(p_ok, "IAS38", as_of=d(2025, 1, 31)), "E5")

def test_s10_impairment_after_ready():
    p = proj(impairment_event=(d(2025, 12, 31), 300 * M))
    a = evaluate(p, "IAS38")
    sch = schedule(a, p)
    row = next(x for x in sch if x["impairment"])
    assert row["period_end"] == d(2025, 12, 31) and row["closing"] == 300 * M
    assert sum(x["amortization"] + x["impairment"] for x in sch) == 550 * M and sch[-1]["closing"] == 0
    b = evaluate(p, "NAS11"); sb = schedule(b, p)
    rb = next(x for x in sb if x["impairment"])
    assert rb["period_end"] == d(2025, 12, 31) and rb["closing"] == 300 * M
    assert sum(x["amortization"] + x["impairment"] for x in sb) == 550 * M and sb[-1]["closing"] == 0

def test_s11_criteria_revoked():
    asm = [yes_all(d(2024, 7, 1)), yes_all(d(2024, 9, 1), K4="no")]
    p = proj(assessments=asm)
    a, b = both(p)
    assert a["capitalized"] == 300 * M and has(a, "IAS 36")
    assert b["capitalized"] == 300 * M and b["nas_criteria_writeoff"] == 300 * M
    assert carrying_amount(b, p, d(2024, 8, 31)) == 300 * M
    assert carrying_amount(b, p, d(2024, 9, 1)) == 0
    assert b["amort_months"] == 0

def test_s12_abandoned_after_ready():
    p = proj(abandoned_on=d(2025, 7, 10))
    a = evaluate(p, "IAS38")
    sch = schedule(a, p)
    assert sch[-1]["period_end"] == d(2025, 6, 30) and len(sch) == 6
    assert a["writeoff"] == 550 * M - 6 * (550 * M // 96)
    b = evaluate(p, "NAS11")
    assert len(schedule(b, p)) == 6 and b["writeoff"] == 550 * M - 6 * (550 * M // 60)

def test_s13_out_of_scope():
    for sc in ("mineral_exploration", "contract_for_customer"):
        a, b = both(proj(scope=sc))
        assert a["decision"] == b["decision"] == "STANDART QO'LLANILMAYDI" and a["capitalized"] == 0

def test_s14_impairment_before_ready():
    p = proj(impairment_event=(d(2024, 12, 15), 400 * M))
    a = evaluate(p, "IAS38")
    assert carrying_amount(a, p, d(2024, 12, 31)) == 400 * M
    assert sum(x["amortization"] for x in schedule(a, p)) == 400 * M
    b = evaluate(p, "NAS11")
    assert carrying_amount(b, p, d(2024, 12, 31)) == 400 * M
    assert sum(x["amortization"] for x in schedule(b, p)) == 400 * M and b["amort_months"] == 60

def test_s15_categories():
    extra = [Cost(d(2024, 11, 20), 10 * M, "legal_registration"), Cost(d(2024, 11, 21), 5 * M, "selling")]
    a, b = both(proj(costs=base_costs() + extra))
    assert a["capitalized"] == b["capitalized"] == 560 * M        # registration in, selling/training/admin out
    assert a["expensed"] == b["expensed"] == 390 * M + 5 * M

def test_s16_nas_benefit_limit():
    p = proj(expected_net_benefit=400 * M)
    a, b = both(p)
    assert a["capitalized"] == 550 * M and has(a, "IAS 36.12")      # IAS: no cap at recognition, indicator
    assert b["capitalized"] == 400 * M and b["expensed"] == 540 * M  # NAS 13-band: 150 of Nov cost expensed
    assert sum(r["amount"] for r in b["rows"]) == 940 * M

def test_s17_invalid_settings_rejected():
    import pytest
    with pytest.raises(AssertionError):
        Settings(amort_start="tomorrow")
    with pytest.raises(AssertionError):
        Settings(nas_max_months=72)

def test_s18_same_day_and_boundary_dates():
    # cost on the assessment date and on the development start date are capitalized / development
    costs = [Cost(d(2024, 7, 1), 10 * M, "salary"), Cost(d(2024, 4, 1), 7 * M, "salary"),
             Cost(d(2025, 1, 1), 9 * M, "salary")]                  # on availability date -> expense (R5)
    a = evaluate(proj(costs=costs), "IAS38")
    by = {(r["date"], r["amount"]): r["treatment"] for r in a["rows"]}
    assert by[(d(2024, 7, 1), 10 * M)] == "capitalize"
    assert by[(d(2024, 4, 1), 7 * M)] == "expense"                  # development started, criteria not yet met
    assert by[(d(2025, 1, 1), 9 * M)] == "expense"

def test_s18b_development_start_day_is_development():
    p = proj(development_start=d(2024, 7, 1), costs=[Cost(d(2024, 7, 1), 10 * M, "salary")])
    a, b = both(p)
    assert a["capitalized"] == b["capitalized"] == 10 * M

def test_s19_costs_after_abandonment_expensed():
    p = proj(available_for_use=None, abandoned_on=d(2024, 10, 1))
    a, b = both(p)
    assert a["capitalized"] == b["capitalized"] == 300 * M            # Nov 250 after abandonment -> expense
    assert a["writeoff"] == b["writeoff"] == 300 * M

def test_s20_no_e5_after_asset_ready():
    p = proj(impairment_test_dates=[d(2024, 12, 20)])                 # ready 01.01.2025
    assert not has(evaluate(p, "IAS38", as_of=d(2026, 6, 30)), "E5")

if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); n += 1; print("ok ", name)
    print(f"\nALL {n} SCENARIOS PASSED")
