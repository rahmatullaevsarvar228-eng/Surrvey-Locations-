"""Stage 3: GUI smoke tests (offscreen Qt)."""
import os
from datetime import date as d

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QPushButton  # noqa: E402

from ittki.core.engine import CRITERIA  # noqa: E402
from ittki.db.repository import ProjectRecord, Repository, User  # noqa: E402
from ittki.demo import load_demo  # noqa: E402
from ittki.services import Service  # noqa: E402
from ittki.ui import dialogs  # noqa: E402
from ittki.ui.app import make_app  # noqa: E402
from ittki.ui.main_window import MainWindow  # noqa: E402

TODAY = d(2026, 10, 11)


@pytest.fixture(scope="module")
def app():
    return make_app(["test"])


@pytest.fixture
def svc(tmp_path):
    repo = Repository(tmp_path / "ui.sqlite3")
    load_demo(repo)
    yield Service(repo, today=lambda: TODAY)
    repo.close()


def test_all_pages_and_card_tabs_render(app, svc):
    w = MainWindow(svc, User("Test", "accountant"))
    for i in range(len(w.pages)):
        w.show_page(i)
    assert w.pages[0].table.rowCount() == 4
    for p in svc.repo.projects():
        card = w.open_project(p.id)
        assert [card.tabs.tabText(i) for i in range(card.tabs.count())] == [
            "Ma'lumot", "Bosqichlar", "Mezonlar", "Xarajatlar", "Qaror", "Provodkalar", "Amortizatsiya",
            "Solishtirma"]
        for i in range(card.tabs.count()):
            card.tabs.setCurrentIndex(i)
        assert card.t_costs.rowCount() == len(svc.repo.costs(p.id))
        card.close()
    w.close()


def test_decision_tab_two_columns(app, svc):
    w = MainWindow(svc, User("Test", "accountant"))
    pid = svc.repo.project_by_code("DEMO-ATJBT-02").id
    card = w.open_project(pid)
    ias, nas = card.d_cols["IAS38"], card.d_cols["NAS11"]
    assert ias[0].title() == "IAS 38" and nas[0].title() == "BHMS 11"
    assert ias[3]["dec.capitalized"].text().startswith("270 000 000")
    assert nas[3]["dec.capitalized"].text().startswith("880 000 000")
    t = ias[4]
    assert t.columnCount() == 5 and t.item(0, 4).text() == "IAS 38.54"      # standard paragraph per cost
    card.close(); w.close()


def test_auditor_is_read_only(app, svc):
    w = MainWindow(svc, User("Auditor", "auditor"))
    card = w.open_project(svc.repo.projects()[0].id)
    for b in (card.b_c_add, card.b_c_del, card.b_assess, card.b_stage, card.b_save):
        assert not b.isEnabled()
    assert not w.pages[1].b_new.isEnabled() and not w.pages[4].b_save.isEnabled()
    card.close(); w.close()


def _yes_without_evidence_dialog(svc, pid):
    dlg = dialogs.AssessmentDialog(svc.repo, User("L", "leader"), pid, TODAY)
    for r in dlg.rows:
        r.answer.setCurrentIndex(r.answer.findData("yes"))
        r.ev_type.setCurrentText("TEI")
        r.ev_number.setText("1")
    dlg.rows[4].ev_number.setText("")          # K5 'Ha' without a document
    return dlg


def test_yes_without_evidence_is_not_saved(app, svc, monkeypatch):
    pid = svc.repo.save_project(ProjectRecord("UI-1", "UI"), User("L", "leader"))
    monkeypatch.setattr(dialogs, "choose", lambda *a, **k: 1)     # user picks "Bekor qilish"
    dlg = _yes_without_evidence_dialog(svc, pid)
    dlg._save(False)
    assert svc.repo.assessments(pid) == [] and dlg.saved_id is None


def test_yes_without_evidence_saved_as_draft_raises_e1(app, svc, monkeypatch):
    pid = svc.repo.save_project(ProjectRecord("UI-2", "UI", development_start=d(2026, 1, 1)), User("L", "leader"))
    monkeypatch.setattr(dialogs, "choose", lambda *a, **k: 0)     # user picks "Qoralama sifatida saqlash"
    dlg = _yes_without_evidence_dialog(svc, pid)
    dlg._save(False)
    (a,) = svc.repo.assessments(pid)
    assert a.is_draft and a.answers["K5_adequate_resources"].evidence is None
    assert "E1" in [f.code for f in svc.analyze(pid).findings]


def test_complete_assessment_saved(app, svc):
    pid = svc.repo.save_project(ProjectRecord("UI-3", "UI"), User("L", "leader"))
    dlg = _yes_without_evidence_dialog(svc, pid)
    dlg.rows[4].ev_number.setText("5")
    dlg._save(False)
    (a,) = svc.repo.assessments(pid)
    assert not a.is_draft and set(a.answers) == set(CRITERIA)


def test_settings_page_saves_and_rejects_9410(app, svc, monkeypatch):
    msgs = []
    monkeypatch.setattr("ittki.ui.pages.error", lambda parent, text: msgs.append(text))
    monkeypatch.setattr("ittki.ui.pages.info", lambda parent, text: msgs.append(text))
    w = MainWindow(svc, User("B", "accountant"))
    w.show_page(4)
    page = w.pages[4]
    page.acc["expense"].setText("9410")
    page._save()
    assert "9410" in msgs[-1] and svc.settings.accounts.expense == "9420"
    page.acc["expense"].setText("9430")
    page._save()
    assert svc.settings.accounts.expense == "9430"
    w.close()
