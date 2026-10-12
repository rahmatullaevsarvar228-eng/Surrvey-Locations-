"""Role permissions, empty 'expected net benefit' field, E9 default threshold."""
import os
import sqlite3
from datetime import date as d

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ittki.core.appsettings import AppSettings
from ittki.core.controls import ControlSettings
from ittki.db.permissions import PERMISSIONS
from ittki.db.repository import (CostRecord, ImpairmentTest, PermissionDenied, ProjectRecord, ReadOnlyRole,
                                 Repository, User)
from tests.test_db import all_yes, save_s2
from tests.test_engine import M

LEAD = User("Aliyev B.", "leader")
ACC = User("Karimova D.", "accountant")
AUD = User("Usmonov R.", "auditor")


@pytest.fixture
def repo(tmp_path):
    r = Repository(tmp_path / "p.sqlite3")
    yield r
    r.close()


def denied(repo):
    return [x for x in repo.audit_log() if x.action == "denied"]


# ------------------------------------------------------------------ permission matrix
def test_permission_matrix_matches_requirements():
    assert PERMISSIONS["assessment"] == PERMISSIONS["stage"] == {"leader"}
    for a in ("cost", "import", "impairment", "settings", "report"):
        assert PERMISSIONS[a] == {"accountant"}
    assert all("auditor" not in roles for roles in PERMISSIONS.values())


@pytest.mark.parametrize("action", sorted(PERMISSIONS))
@pytest.mark.parametrize("user", [LEAD, ACC, AUD])
def test_authorize_every_action_and_role(repo, action, user):
    if user.role in PERMISSIONS[action]:
        repo.authorize(user, action)
        assert denied(repo) == []
    else:
        exc = ReadOnlyRole if user.role == "auditor" else PermissionDenied
        with pytest.raises(exc) as e:
            repo.authorize(user, action)
        assert "Ruxsat yo'q" in str(e.value) and e.value.action == action
        (row,) = denied(repo)
        assert (row.entity, row.actor, row.role, row.after) == (action, user.name, user.role,
                                                                {"action": action, "role": user.role})


# ------------------------------------------------------------------ repository operations
def test_leader_cannot_enter_costs_impairment_or_settings(repo):
    pid = save_s2(repo)
    n_costs = len(repo.costs(pid))
    with pytest.raises(PermissionDenied):
        repo.add_cost(CostRecord(pid, d(2024, 1, 1), 1, "salary"), LEAD)
    with pytest.raises(PermissionDenied):
        repo.add_costs([CostRecord(pid, d(2024, 1, 1), 1, "salary")], LEAD)
    c = repo.costs(pid)[0]
    with pytest.raises(PermissionDenied):
        repo.update_cost(CostRecord(pid, c.on_date, 1, c.category, id=c.id), LEAD)
    with pytest.raises(PermissionDenied):
        repo.delete_cost(c.id, LEAD)
    with pytest.raises(PermissionDenied):
        repo.set_impairment_event(pid, d(2025, 6, 1), 1, LEAD)
    with pytest.raises(PermissionDenied):
        repo.add_impairment_test(ImpairmentTest(pid, d(2025, 12, 1)), LEAD)
    with pytest.raises(PermissionDenied):
        repo.save_settings(AppSettings(), LEAD)
    assert len(repo.costs(pid)) == n_costs and repo.costs(pid)[0].amount == c.amount
    assert repo.impairment_event(pid) is None
    assert [x.entity for x in denied(repo)] == ["cost"] * 4 + ["impairment"] * 2 + ["settings"]


def test_accountant_cannot_assess_or_change_stage(repo):
    pid = save_s2(repo)
    n = len(repo.assessments(pid))
    with pytest.raises(PermissionDenied):
        repo.add_assessment(all_yes(pid, d(2024, 9, 1), K4="no"), ACC)
    with pytest.raises(PermissionDenied):
        repo.change_stage(pid, "abandoned", d(2025, 6, 1), ACC)
    assert len(repo.assessments(pid)) == n and repo.project(pid).abandoned_on is None
    assert [x.entity for x in denied(repo)] == ["assessment", "stage"]


def test_auditor_can_only_view(repo):
    pid = save_s2(repo)
    for call in (lambda: repo.save_project(ProjectRecord("X", "X"), AUD),
                 lambda: repo.add_assessment(all_yes(pid, d(2024, 9, 1)), AUD),
                 lambda: repo.change_stage(pid, "abandoned", d(2025, 6, 1), AUD),
                 lambda: repo.add_cost(CostRecord(pid, d(2024, 1, 1), 1, "salary"), AUD),
                 lambda: repo.set_impairment_event(pid, None, None, AUD),
                 lambda: repo.save_settings(AppSettings(), AUD)):
        with pytest.raises(ReadOnlyRole):
            call()
    assert len(denied(repo)) == 6
    assert repo.project(pid).code == "S2" and repo.engine_project(pid).costs


def test_allowed_roles_still_work(repo):
    pid = repo.save_project(ProjectRecord("A", "A"), ACC)       # both roles may edit the project card
    repo.save_project(ProjectRecord("B", "B"), LEAD)
    repo.change_stage(pid, "development", d(2024, 1, 1), LEAD)
    repo.add_assessment(all_yes(pid, d(2024, 1, 2)), LEAD)
    repo.add_cost(CostRecord(pid, d(2024, 2, 1), 5 * M, "salary"), ACC)
    repo.add_impairment_test(ImpairmentTest(pid, d(2024, 12, 20)), ACC)
    assert denied(repo) == []


def test_denied_attempt_survives_and_audit_is_append_only(repo):
    pid = save_s2(repo)
    with pytest.raises(PermissionDenied):
        repo.add_cost(CostRecord(pid, d(2024, 1, 1), 1, "salary"), LEAD)
    repo.close()
    r2 = Repository(repo.path)
    (row,) = [x for x in r2.audit_log() if x.action == "denied"]
    with pytest.raises(sqlite3.DatabaseError):
        r2.conn.execute("DELETE FROM audit_log WHERE id = ?", (row.id,))
    r2.close()


# ------------------------------------------------------------------ UI
@pytest.fixture
def ui(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from ittki.services import Service
    from ittki.ui.app import make_app
    app = make_app(["t"])
    r = Repository(tmp_path / "ui.sqlite3")
    pid = save_s2(r)
    msgs = []
    monkeypatch.setattr("ittki.ui.widgets.error", lambda parent, text: msgs.append(text))
    yield app, Service(r, today=lambda: d(2026, 10, 11)), pid, msgs
    r.close()


def test_ui_leader_cannot_add_cost(ui, monkeypatch):
    from ittki.ui import project_card
    app, svc, pid, msgs = ui
    opened = []
    monkeypatch.setattr(project_card, "CostDialog", lambda *a, **k: opened.append(1))
    card = project_card.ProjectCard(svc, LEAD, pid)
    card._add_cost()
    card._import_costs()
    card._add_test()
    card._export_amort()
    assert opened == [] and len(msgs) == 4 and all("Ruxsat yo'q" in m for m in msgs)
    assert [x.entity for x in denied(svc.repo)] == ["cost", "import", "impairment", "report"]
    card.close()


def test_ui_accountant_cannot_assess_or_change_stage(ui, monkeypatch):
    from ittki.ui import project_card
    app, svc, pid, msgs = ui
    opened = []
    monkeypatch.setattr(project_card, "AssessmentDialog", lambda *a, **k: opened.append(1))
    monkeypatch.setattr(project_card, "StageDialog", lambda *a, **k: opened.append(1))
    card = project_card.ProjectCard(svc, ACC, pid)
    card._new_assessment()
    card._change_stage()
    assert opened == [] and len(msgs) == 2
    assert [x.entity for x in denied(svc.repo)] == ["assessment", "stage"]
    card.close()


def test_ui_reports_only_for_accountant(ui, monkeypatch, tmp_path):
    from ittki.ui import pages
    app, svc, pid, msgs = ui
    out = tmp_path / "s.xlsx"
    monkeypatch.setattr(pages.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    monkeypatch.setattr(pages, "info", lambda *a: None)
    page = pages.ReportsPage(svc, LEAD)
    page._run(page._amort, "xlsx", "rep.amort")
    assert not out.exists() and len(msgs) == 1 and denied(svc.repo)[0].entity == "report"
    page = pages.ReportsPage(svc, ACC)
    page._run(page._amort, "xlsx", "rep.amort")
    assert out.exists() and len(msgs) == 1


def test_ui_leader_cannot_save_settings(ui):
    from ittki.ui import pages
    app, svc, pid, msgs = ui
    page = pages.SettingsPage(svc, LEAD)
    page.refresh()
    page.acc["expense"].setText("9430")
    page._save()
    assert svc.settings.accounts.expense == "9420" and denied(svc.repo)[0].entity == "settings"


# ------------------------------------------------------------------ expected net benefit: empty vs 0
def test_money_edit_empty_is_none_not_zero(ui):
    from ittki.ui.widgets import MoneyEdit
    e = MoneyEdit(None)
    assert e.text() == "" and e.placeholderText() == "" and e.value() is None
    e.setText("0")
    assert e.value() == 0
    e.setValue(0)
    assert e.text() == "0"


def test_card_keeps_benefit_empty_unless_zero_entered(ui):
    from ittki.ui.project_card import ProjectCard
    app, svc, pid, msgs = ui
    card = ProjectCard(svc, LEAD, pid)
    assert card.f_benefit.text() == "" and card.f_benefit.placeholderText() == ""
    card._save_info()                                    # save without touching the field
    assert svc.repo.project(pid).expected_net_benefit is None
    card.f_benefit.setText("0")
    card._save_info()                                    # explicit 0 is stored as 0
    assert svc.repo.project(pid).expected_net_benefit == 0
    card.refresh()
    assert card.f_benefit.text() == "0"
    card.f_benefit.setText("")
    card._save_info()
    assert svc.repo.project(pid).expected_net_benefit is None
    card.close()


# ------------------------------------------------------------------ E9 default
def test_e9_default_threshold_is_one_million(repo):
    assert ControlSettings().e9_amount == 1_000_000
    assert repo.settings().controls.e9_amount == 1_000_000


def test_old_database_with_default_zero_is_upgraded(repo):
    repo.conn.execute("UPDATE settings SET value = '0' WHERE key = 'control.e9_amount'")
    repo.conn.execute("DELETE FROM settings WHERE key = 'meta.settings_version'")
    repo.close()
    r2 = Repository(repo.path)
    assert r2.settings().controls.e9_amount == 1_000_000
    last = r2.audit_log("settings")[-1]
    assert (last.role, last.before, last.after) == ("system", {"control.e9_amount": 0},
                                                    {"control.e9_amount": 1_000_000})
    r2.close()


def test_user_chosen_zero_is_kept(repo):
    s = repo.settings()
    s.controls = ControlSettings(e9_amount=0)
    repo.save_settings(s, ACC)
    repo.conn.execute("DELETE FROM settings WHERE key = 'meta.settings_version'")
    repo.close()
    r2 = Repository(repo.path)
    assert r2.settings().controls.e9_amount == 0
    r2.close()
