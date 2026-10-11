"""Stage 5: demo data (TZ section 9)."""
from datetime import date as d

from ittki.db.repository import Repository
from ittki.demo import load_demo
from ittki.i18n import uz
from ittki.services import Service

TODAY = d(2026, 10, 11)


def test_four_conditional_projects_marked_and_idempotent():
    repo = Repository()
    assert load_demo(repo) == 4 and load_demo(repo) == 0
    ps = repo.projects()
    assert len(ps) == 4 and all(p.is_demo and uz.DEMO_MARK in p.note for p in ps)
    assert "Shartli misol" in uz.DEMO_MARK and '"Olmaliq KMK" AJ' in uz.DEMO_MARK


def test_demo_projects_cover_tz_cases():
    repo = Repository()
    load_demo(repo)
    s = Service(repo, today=lambda: TODAY)
    a = {x.record.code: x for x in s.analyze_all()}
    flot, asu, reag, gidro = a["DEMO-FLOT-01"], a["DEMO-ATJBT-02"], a["DEMO-REAG-03"], a["DEMO-GIDRO-04"]
    # (1) flotation: capitalized, ready, 96 vs 60 months
    assert flot.record.stage == "ready" and flot.res["IAS38"]["decision"] == "KAPITALLASHTIRILADI"
    assert (flot.res["IAS38"]["amort_months"], flot.res["NAS11"]["amort_months"]) == (96, 60)
    # (2) process control: K3 'no' -> standards differ
    assert asu.res["NAS11"]["capitalized"] > asu.res["IAS38"]["capitalized"] > 0
    # (3) reagents: research only
    assert reag.record.stage == "research" and reag.res["IAS38"]["capitalized"] == 0
    assert reag.res["NAS11"]["decision"] == "XARAJAT SIFATIDA TAN OLINADI"
    # (4) abandoned: capitalized, then written off
    assert gidro.record.stage == "abandoned"
    assert gidro.res["IAS38"]["decision"] == "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN"
    assert gidro.res["NAS11"]["writeoff"] == gidro.res["NAS11"]["capitalized"] > 0
    codes = {f.code for x in a.values() for f in x.findings}
    assert {"E1", "E4", "E7", "E9", "E10"} <= codes
