"""Stage 2: SQLite storage, migrations, repository round-trip, audit log (M11)."""
import sqlite3
from dataclasses import replace
from datetime import date as d

import pytest

from ittki.core.appsettings import AppSettings
from ittki.core.engine import CRITERIA, Settings, evaluate, reconcile, schedule
from ittki.core.journal import Accounts
from ittki.db.repository import (Answer, AssessmentRecord, CostRecord, EvidenceDoc, EvidenceRequired,
                                 ImpairmentTest, ProjectRecord, ReadOnlyRole, Repository, User)
from ittki.db.schema import SCHEMA_VERSION
from tests.test_engine import M, proj

ACC = User("Karimova D.", "accountant")
LEAD = User("Aliyev B.", "leader")
AUD = User("Usmonov R.", "auditor")


def ev(k, on):
    return EvidenceDoc("TEI", f"{k[:2]}-1", on)


def all_yes(pid, on, **over):
    ans = {k: Answer("yes", ev(k, on)) for k in CRITERIA}
    for short, v in over.items():
        k = next(x for x in CRITERIA if x.startswith(short))
        ans[k] = Answer(v, None if v != "yes" else ans[k].evidence)
    return AssessmentRecord(pid, on, ans)


def save_s2(repo) -> int:
    """Scenario S2 (base project) entered through the repository, the way the UI does it."""
    pid = repo.save_project(ProjectRecord("S2", "Bazaviy loyiha", start_date=d(2024, 1, 15), budget=1000 * M,
                                          useful_life_months=96), LEAD)
    repo.change_stage(pid, "development", d(2024, 4, 1), LEAD)
    repo.add_assessment(all_yes(pid, d(2024, 7, 1)), LEAD)
    for c in proj().costs:
        repo.add_cost(CostRecord(pid, c.on, c.amount, c.category, "PD-1"), ACC)
    repo.add_impairment_test(ImpairmentTest(pid, d(2024, 12, 20), "test"), ACC)
    repo.change_stage(pid, "ready", d(2025, 1, 1), LEAD)
    return pid


@pytest.fixture
def repo(tmp_path):
    r = Repository(tmp_path / "t.sqlite3")
    yield r
    r.close()


def test_migration_on_first_run_and_idempotent(tmp_path):
    path = tmp_path / "x.sqlite3"
    r = Repository(path)
    assert r.version == SCHEMA_VERSION
    tables = {x[0] for x in r.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "stage_events", "assessments", "assessment_answers", "evidence_documents", "costs",
            "impairment_events", "impairment_tests", "settings", "audit_log"} <= tables
    r.close()
    r = Repository(path)                     # second start: no re-migration, settings not re-seeded
    assert r.conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1
    assert len([a for a in r.audit_log("settings")]) == 1
    r.close()


def test_s2_roundtrip_gives_same_engine_result(repo, tmp_path):
    pid = save_s2(repo)
    expected = proj()
    loaded = repo.engine_project(pid)
    for fw in ("IAS38", "NAS11"):
        a, b = evaluate(expected, fw), evaluate(loaded, fw)
        for k in ("decision", "capitalized", "expensed", "amort_months", "writeoff", "cap_rows", "first_met_on"):
            assert a[k] == b[k], k
        assert [(r["date"], r["amount"], r["treatment"], r["reason"]) for r in a["rows"]] == \
               [(r["date"], r["amount"], r["treatment"], r["reason"]) for r in b["rows"]]
        assert schedule(a, expected) == schedule(b, loaded)
    assert reconcile(expected, d(2025, 12, 31)) == reconcile(loaded, d(2025, 12, 31))
    assert evaluate(loaded, "IAS38")["capitalized"] == 550 * M
    # and after reopening the file
    repo.close()
    r2 = Repository(tmp_path / "t.sqlite3")
    assert evaluate(r2.engine_project(pid), "NAS11")["amort_months"] == 60
    r2.close()


def test_project_fields_roundtrip(repo):
    p = ProjectRecord("P1", "Nom", scope="contract_for_customer", department="Bo'lim", leader="X",
                      start_date=d(2024, 1, 1), budget=5 * M, phases_separable=False, useful_life_months=12,
                      expected_net_benefit=7 * M, note="izoh", is_demo=True)
    pid = repo.save_project(p, LEAD)
    q = repo.project(pid)
    assert replace(q, created_at=None) == replace(p, created_at=None)
    assert q.stage == "research" and q.status == "active"


def test_money_must_be_int(repo):
    pid = repo.save_project(ProjectRecord("P", "N"), LEAD)
    for bad in (1.5, -1, True, "100"):
        with pytest.raises(TypeError):
            repo.add_cost(CostRecord(pid, d(2024, 1, 1), bad, "salary"), ACC)
    with pytest.raises(sqlite3.IntegrityError):            # also enforced by the schema itself
        repo.conn.execute("INSERT INTO costs (project_id, on_date, amount, category, created_at) "
                          "VALUES (?, '2024-01-01', 1.5, 'salary', 'x')", (pid,))


def test_dates_must_be_date(repo):
    with pytest.raises(TypeError):
        repo.save_project(ProjectRecord("P", "N", start_date="2024-01-01"), LEAD)


def test_audit_log_records_every_change(repo):
    pid = save_s2(repo)
    log = repo.audit_log()
    entities = [(x.entity, x.action) for x in log]
    assert ("project", "create") in entities and ("assessment", "create") in entities
    assert entities.count(("cost", "create")) == 6 and entities.count(("stage_event", "create")) == 2
    c = repo.costs(pid)[0]
    repo.update_cost(replace(c, amount=101 * M), ACC)
    last = repo.audit_log("cost", c.id)[-1]
    assert (last.action, last.before, last.after, last.actor, last.role) == \
           ("update", {"amount": 100 * M}, {"amount": 101 * M}, "Karimova D.", "accountant")
    repo.delete_cost(c.id, ACC)
    last = repo.audit_log("cost", c.id)[-1]
    assert last.action == "delete" and last.before["amount"] == 101 * M and last.after is None
    p = repo.project(pid); p.name = "Yangi nom"; repo.save_project(p, LEAD)
    last = repo.audit_log("project", pid)[-1]
    assert last.before == {"name": "Bazaviy loyiha"} and last.after == {"name": "Yangi nom"}


@pytest.mark.parametrize("table", ["audit_log", "stage_events", "assessments", "assessment_answers",
                                   "evidence_documents"])
def test_append_only_tables(repo, table):
    save_s2(repo)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        repo.conn.execute(f"DELETE FROM {table}")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        repo.conn.execute(f"UPDATE {table} SET id = id")


def test_change_and_audit_are_atomic(repo):
    pid = repo.save_project(ProjectRecord("P", "N"), LEAD)
    n = len(repo.audit_log())
    with pytest.raises(ValueError):
        repo.add_assessment(AssessmentRecord(pid, d(2024, 1, 1), {"K1_technical_feasibility":
                                             Answer("yes", EvidenceDoc("", "", d(2024, 1, 1)))}), LEAD)
    assert repo.assessments(pid) == [] and len(repo.audit_log()) == n


def test_yes_requires_evidence_unless_draft(repo):
    pid = repo.save_project(ProjectRecord("P", "N"), LEAD)
    a = all_yes(pid, d(2024, 7, 1))
    a.answers["K5_adequate_resources"] = Answer("yes", None)
    with pytest.raises(EvidenceRequired) as e:
        repo.add_assessment(a, LEAD)
    assert e.value.keys == ["K5_adequate_resources"] and repo.assessments(pid) == []
    a.is_draft = True
    repo.add_assessment(a, LEAD)
    (saved,) = repo.assessments(pid)
    assert saved.is_draft
    res = evaluate(repo.engine_project(pid), "IAS38")
    assert any("E1" in w for w in res["warnings"])


def test_assessments_are_versioned_and_same_day_last_wins(repo):
    pid = repo.save_project(ProjectRecord("P", "N", development_start=d(2024, 1, 1)), LEAD)
    repo.add_cost(CostRecord(pid, d(2024, 8, 1), 10 * M, "salary"), ACC)
    repo.add_assessment(all_yes(pid, d(2024, 7, 1)), LEAD)
    repo.add_assessment(all_yes(pid, d(2024, 7, 1), K4="no"), LEAD)      # same day, entered later -> wins
    assert len(repo.assessments(pid)) == 2
    assert evaluate(repo.engine_project(pid), "IAS38")["capitalized"] == 0
    repo.add_assessment(all_yes(pid, d(2024, 7, 1)), LEAD)
    assert evaluate(repo.engine_project(pid), "IAS38")["capitalized"] == 10 * M


def test_stage_transitions(repo):
    pid = repo.save_project(ProjectRecord("P", "N", useful_life_months=12), LEAD)
    with pytest.raises(ValueError):
        repo.change_stage(pid, "ready", d(2024, 1, 1), LEAD)               # research -> ready not allowed
    repo.change_stage(pid, "development", d(2024, 1, 1), LEAD)
    repo.change_stage(pid, "development", d(2024, 2, 1), LEAD, "sana tuzatildi")   # correction
    repo.change_stage(pid, "ready", d(2024, 6, 1), LEAD)
    repo.change_stage(pid, "abandoned", d(2025, 6, 1), LEAD)
    p = repo.project(pid)
    assert (p.development_start, p.available_for_use, p.abandoned_on, p.status) == \
           (d(2024, 2, 1), d(2024, 6, 1), d(2025, 6, 1), "abandoned")
    assert [(e.from_stage, e.to_stage) for e in repo.stage_events(pid)] == [
        ("research", "development"), ("development", "development"), ("development", "ready"), ("ready", "abandoned")]


def test_auditor_is_read_only(repo):
    pid = save_s2(repo)
    with pytest.raises(ReadOnlyRole):
        repo.add_cost(CostRecord(pid, d(2024, 1, 1), 1, "salary"), AUD)
    with pytest.raises(ReadOnlyRole):
        repo.save_settings(AppSettings(), AUD)
    assert repo.project(pid).code == "S2"       # reading is fine


def test_settings_roundtrip_and_audit(repo):
    s = repo.settings()
    assert s == AppSettings()
    assert s.accounts.expense == "9420" and s.accounts.capitalize == "0830"
    s.accounts = Accounts(expense="9430", amortization_debit="2510")
    s.engine = Settings(amort_start="next_month")
    changed = repo.save_settings(s, ACC)
    assert set(changed) == {"account.expense", "account.amortization_debit", "amort_start"}
    assert repo.settings().accounts.expense == "9430" and repo.settings().engine.amort_start == "next_month"
    log = [x for x in repo.audit_log("settings") if x.action == "update"]
    assert {list(x.after)[0] for x in log} == set(changed)


def test_category_override_is_stored_and_audited(repo):
    s = repo.settings()
    s.engine = Settings(included={"IAS38": s.engine.categories("IAS38"),
                                  "NAS11": s.engine.categories("NAS11") | {"training"}})
    assert repo.save_settings(s, ACC) == ["categories.NAS11"]
    assert "training" in repo.settings().engine.categories("NAS11")


def test_invalid_settings_rejected(repo):
    flat = repo.settings().to_flat()
    for k, v in (("amort_start", "tomorrow"), ("nas_max_months", 72)):
        with pytest.raises(AssertionError):
            AppSettings.from_flat({**flat, k: v})
    with pytest.raises(ValueError):
        AppSettings.from_flat({**flat, "account.expense": "9410"})


def test_impairment_event_and_tests(repo):
    pid = save_s2(repo)
    repo.set_impairment_event(pid, d(2025, 12, 31), 300 * M, ACC)
    p = repo.engine_project(pid)
    assert p.impairment_event == (d(2025, 12, 31), 300 * M) and p.impairment_test_dates == [d(2024, 12, 20)]
    sch = schedule(evaluate(p, "IAS38"), p)
    assert next(x for x in sch if x["impairment"])["closing"] == 300 * M
    repo.set_impairment_event(pid, None, None, ACC)
    assert repo.engine_project(pid).impairment_event is None
    assert [x.action for x in repo.audit_log("impairment_event")] == ["create", "delete"]


def test_backup(repo, tmp_path):
    pid = save_s2(repo)
    repo.backup(tmp_path / "copy.sqlite3")
    r2 = Repository(tmp_path / "copy.sqlite3")
    assert evaluate(r2.engine_project(pid), "IAS38")["capitalized"] == 550 * M
    r2.close()
