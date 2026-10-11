"""M10 control exceptions E1–E10: one positive and one negative case per rule."""
from datetime import date as d

import pytest

from ittki.core.controls import ControlSettings, Finding, LEVELS, add_months, check_project
from ittki.core.engine import Cost, Settings, INCLUDED
from tests.test_engine import M, proj, yes_all

TODAY = d(2026, 6, 30)


def codes(p, as_of=TODAY, **kw):
    return [f.code for f in check_project(p, as_of, **kw)]


def clean(**kw):
    """Base project without the exceptions it has by construction (late assessment -> E3,
    training/admin -> E7, 96 vs 60 months -> E9)."""
    kw.setdefault("assessments", [yes_all(d(2024, 4, 15))])
    kw.setdefault("costs", [Cost(d(2024, 8, 10), 300 * M, "salary")])
    kw.setdefault("useful_life_months", 60)
    return proj(**kw)


def test_clean_project_has_no_exceptions():
    assert codes(clean()) == []


def test_levels_match_tz():
    assert LEVELS == {"E1": "high", "E2": "medium", "E3": "high", "E4": "medium", "E5": "high",
                      "E6": "medium", "E7": "info", "E8": "high", "E9": "info", "E10": "medium"}


def test_e1_yes_without_evidence():
    p = clean(assessments=[yes_all(d(2024, 4, 15), K5="noevidence")])
    f = [x for x in check_project(p, TODAY) if x.code == "E1"]
    assert len(f) == 1 and f[0].level == "high" and "K5" in f[0].message
    assert "E1" not in codes(clean())


def test_e2_expensed_too_long_in_development():
    # development since 01.04.2024, criteria never met, still in development
    p = clean(available_for_use=None, assessments=[yes_all(d(2024, 4, 15), K1="expert")],
              costs=[Cost(d(2024, 5, 10), 10 * M, "salary")])
    assert codes(p, d(2024, 7, 1)).count("E2") == 2              # 91 days, both frameworks
    assert "E2" not in codes(p, d(2024, 6, 30))                  # 90 days — not "longer than"
    assert "E2" not in codes(p, d(2024, 7, 1), ctl=ControlSettings(e2_days=120))
    # criteria met afterwards -> no current E2
    p.assessments.append(yes_all(d(2024, 7, 5)))
    assert "E2" not in codes(p, d(2024, 12, 1))
    # no expensed cost in the run -> no E2
    assert "E2" not in codes(clean(available_for_use=None, assessments=[yes_all(d(2024, 4, 15), K1="expert")],
                                   costs=[]), d(2024, 7, 1))


def test_e2_only_for_the_framework_that_fails():
    p = clean(available_for_use=None, assessments=[yes_all(d(2024, 4, 15), K3="no")],
              costs=[Cost(d(2024, 5, 10), 10 * M, "salary")])
    f = [x for x in check_project(p, d(2024, 8, 1)) if x.code == "E2"]
    assert [x.framework for x in f] == ["IAS38"]                 # K3 is not a BHMS 11 criterion


def test_e3_no_assessment_within_30_days():
    assert "E3" in codes(proj())                                  # dev 01.04.2024, first assessment 01.07.2024
    assert "E3" not in codes(clean())                             # assessed 15.04.2024
    assert "E3" not in codes(proj(), d(2024, 5, 1))               # deadline not passed yet
    assert "E3" not in codes(proj(), ctl=ControlSettings(e3_days=91))


def test_e4_budget_overrun():
    p = clean()
    assert "E4" in codes(p, budget=272 * M)       # 300 > 272 * 1.10 = 299.2
    assert "E4" not in codes(p, budget=273 * M)   # 300 <= 300.3
    assert "E4" not in codes(p)                   # no budget
    assert "E4" not in codes(p, budget=272 * M, ctl=ControlSettings(e4_pct=15))


def test_e5_from_engine_s9():
    p = clean(available_for_use=None, impairment_test_dates=[])
    f = [x for x in check_project(p, d(2025, 1, 31)) if x.code == "E5"]
    assert len(f) == 1 and f[0].framework == "IAS38" and "2024" in f[0].message
    assert "E5" not in codes(clean(available_for_use=None), d(2025, 1, 31))


def test_e6_expert_pending():
    p = clean(available_for_use=None, assessments=[yes_all(d(2024, 4, 15), K4="expert"),
                                                   yes_all(d(2024, 5, 1), K4="expert")])
    f = [x for x in check_project(p, d(2024, 6, 20)) if x.code == "E6"]
    assert len(f) == 1 and f[0].on == d(2024, 4, 15)               # pending since the first 'expert'
    assert "E6" not in codes(p, d(2024, 6, 14))                    # 60 days
    p.assessments.append(yes_all(d(2024, 6, 1)))                   # resolved
    assert "E6" not in codes(p, d(2024, 12, 1))


def test_e7_non_admissible_category():
    p = clean(costs=[Cost(d(2024, 8, 10), 300 * M, "salary"), Cost(d(2024, 9, 10), 5 * M, "training")])
    f = [x for x in check_project(p, TODAY) if x.code == "E7"]
    assert len(f) == 1 and f[0].level == "info" and "IAS 38, BHMS 11" in f[0].message
    s = Settings(included={"IAS38": INCLUDED["IAS38"], "NAS11": INCLUDED["NAS11"] | {"training"}})
    f = [x for x in check_project(p, TODAY, s) if x.code == "E7"]
    assert len(f) == 1 and f[0].framework == "IAS38"


def test_e8_ready_without_useful_life():
    assert "E8" in codes(clean(useful_life_months=0))
    assert "E8" not in codes(clean())
    assert "E8" not in codes(clean(available_for_use=None, useful_life_months=0))


def test_e9_nas_ifrs_difference():
    assert "E9" in codes(proj())                                   # 96 vs 60 months
    assert "E9" not in codes(proj(), ctl=ControlSettings(e9_amount=10**12))
    assert "E9" not in codes(clean())                              # 60 months in both


def test_e10_inactive_project():
    p = clean(available_for_use=None, impairment_test_dates=[d(2024, 12, 20), d(2025, 12, 20)])
    assert "E10" in codes(p, d(2025, 8, 11))                       # last cost 10.08.2024
    assert "E10" not in codes(p, d(2025, 8, 10))
    assert "E10" not in codes(clean(), d(2026, 6, 30))             # asset is ready
    assert "E10" not in codes(clean(available_for_use=None, abandoned_on=d(2025, 1, 1)), TODAY)


def test_out_of_scope_skips_criteria_checks():
    p = proj(scope="mineral_exploration", assessments=[yes_all(d(2024, 7, 1), K5="noevidence")])
    c = codes(p)
    assert not {"E1", "E2", "E3", "E5", "E6", "E7", "E9"} & set(c)


def test_findings_sorted_by_level():
    f = check_project(proj(assessments=[yes_all(d(2024, 7, 1), K5="noevidence")]), TODAY)
    lv = [{"high": 0, "medium": 1, "info": 2}[x.level] for x in f]
    assert lv == sorted(lv) and isinstance(f[0], Finding)


def test_add_months_clamps_day():
    assert add_months(d(2024, 1, 31), 1) == d(2024, 2, 29)
    assert add_months(d(2024, 11, 15), 14) == d(2026, 1, 15)


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        ControlSettings(e2_days=-1)
