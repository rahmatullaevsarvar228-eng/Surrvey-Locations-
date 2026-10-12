"""Control numbers from the final specification (п.3), checked on the running program."""
from datetime import date as d

import pytest

from ittki.core.engine import reconcile
from ittki.db.repository import Repository, User
from ittki.services import Service
from tests.test_engine import proj

TODAY = d(2026, 10, 11)


@pytest.fixture(scope="module")
def demo():
    repo = Repository()
    svc = Service(repo, today=lambda: TODAY)
    svc.load_demo(User("Buxgalter", "accountant"))
    an = {a.record.code: a for a in svc.analyze_all()}
    yield svc, an
    repo.close()


def test_s2_carrying_31_12_2025():
    r = reconcile(proj(), d(2025, 12, 31))
    assert (r["IAS38_carrying"], r["NAS11_carrying"]) == (481_250_008, 440_000_008)


def test_flot_01(demo):
    a = demo[1]["DEMO-FLOT-01"]
    assert a.res["IAS38"]["capitalized"] == a.res["NAS11"]["capitalized"] == 1_568_000_000
    assert (a.carrying["IAS38"], a.carrying["NAS11"]) == (1_453_666_669, 1_385_066_669)


def test_atjbt_02(demo):
    a = demo[1]["DEMO-ATJBT-02"]
    assert (a.res["IAS38"]["capitalized"], a.res["NAS11"]["capitalized"]) == (270_000_000, 880_000_000)
    assert (a.res["IAS38"]["expensed"], a.res["NAS11"]["expensed"]) == (905_000_000, 295_000_000)
    assert a.reconcile["difference"] == -610_000_000              # IAS 38 − BHMS 11
    assert a.reasons[0].startswith("K3")


def test_home_totals(demo):
    t = demo[0].totals(list(demo[1].values()))
    assert (t["capitalized.IAS38"], t["capitalized.NAS11"]) == (2_333_000_000, 2_943_000_000)


def test_exceptions_with_e9_one_million(demo):
    svc, _ = demo
    assert svc.settings.controls.e9_amount == 1_000_000
    got = sorted((rec.code, f.code, f.on) for rec, f in svc.findings_all())
    assert got == sorted([
        ("DEMO-GIDRO-04", "E1", d(2024, 11, 20)),     # K4 = Ha without evidence (draft)
        ("DEMO-GIDRO-04", "E4", TODAY),               # 685 mln vs budget 600 mln (+14%)
        ("DEMO-REAG-03", "E10", d(2025, 6, 20)),      # no activity for more than 12 months
        ("DEMO-FLOT-01", "E7", d(2025, 9, 5)),        # training 35 mln
        ("DEMO-FLOT-01", "E7", d(2026, 4, 10)),       # general admin 22 mln
        ("DEMO-FLOT-01", "E9", TODAY),                # 68 600 000
        ("DEMO-ATJBT-02", "E9", TODAY),               # 610 000 000
    ])
