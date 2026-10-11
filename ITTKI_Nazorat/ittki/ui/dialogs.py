"""Dialogs: login, new project, stage change, criteria assessment, cost."""
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
                               QWidget)

from ..core.engine import ALL_CATEGORIES, CRITERIA, INCLUDED
from ..db.repository import (ROLES, TRANSITIONS, Answer, AssessmentRecord, CostRecord, EvidenceDoc,
                             EvidenceRequired, ProjectRecord, User)
from ..i18n import uz
from .widgets import DateEdit, MoneyEdit, choose, error

CATEGORY_ORDER = sorted(INCLUDED["IAS38"]) + sorted(ALL_CATEGORIES - INCLUDED["IAS38"])


def _buttons(dialog, ok_text=None):
    bb = QDialogButtonBox()
    ok = bb.addButton(ok_text or uz.t("btn.save"), QDialogButtonBox.AcceptRole)
    ok.setObjectName("Primary")
    bb.addButton(uz.t("btn.cancel"), QDialogButtonBox.RejectRole)
    bb.accepted.connect(dialog.accept)
    bb.rejected.connect(dialog.reject)
    return bb, ok


def combo(items: dict, current=None) -> QComboBox:
    c = QComboBox()
    for k, v in items.items():
        c.addItem(v, k)
    if current is not None:
        c.setCurrentIndex(max(c.findData(current), 0))
    return c


# ---------------------------------------------------------------- login
class LoginDialog(QDialog):
    def __init__(self, parent=None, user: Optional[User] = None):
        super().__init__(parent)
        self.setWindowTitle(f"{uz.APP_NAME} — {uz.t('user.title')}")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(uz.t("user.prompt")))
        form = QFormLayout()
        self.name = QLineEdit(user.name if user else "")
        self.role = combo(uz.ROLE, user.role if user else "accountant")
        form.addRow(uz.t("user.name"), self.name)
        form.addRow(uz.t("user.role"), self.role)
        lay.addLayout(form)
        bb, _ = _buttons(self, "OK")
        lay.addWidget(bb)
        self.setMinimumWidth(420)

    def accept(self):
        if not self.name.text().strip():
            error(self, uz.t("msg.required", field=uz.t("user.name")))
            return
        super().accept()

    def user(self) -> User:
        return User(self.name.text().strip(), self.role.currentData())


# ---------------------------------------------------------------- new project
class NewProjectDialog(QDialog):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle(uz.t("projects.new"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.code = QLineEdit()
        self.name = QLineEdit()
        self.scope = combo(uz.SCOPE, "rnd")
        self.dept = QLineEdit()
        self.leader = QLineEdit()
        self.start = DateEdit()
        self.budget = MoneyEdit()
        form.addRow(uz.t("f.code") + " *", self.code)
        form.addRow(uz.t("f.name") + " *", self.name)
        form.addRow(uz.t("f.type"), self.scope)
        form.addRow(uz.t("f.department"), self.dept)
        form.addRow(uz.t("f.leader"), self.leader)
        form.addRow(uz.t("f.start"), self.start)
        form.addRow(uz.t("f.budget"), self.budget)
        lay.addLayout(form)
        bb, _ = _buttons(self)
        lay.addWidget(bb)
        self.setMinimumWidth(520)

    def accept(self):
        for w, f in ((self.code, "f.code"), (self.name, "f.name")):
            if not w.text().strip():
                error(self, uz.t("msg.required", field=uz.t(f)))
                return
        if self.repo.project_by_code(self.code.text().strip()):
            error(self, uz.t("msg.code_exists"))
            return
        try:
            self.budget.value()
        except ValueError:
            error(self, uz.t("set.invalid", error=uz.t("f.budget")))
            return
        super().accept()

    def record(self) -> ProjectRecord:
        return ProjectRecord(self.code.text().strip(), self.name.text().strip(), self.scope.currentData(),
                             self.dept.text().strip(), self.leader.text().strip(), self.start.value(),
                             self.budget.value())


# ---------------------------------------------------------------- stage
class StageDialog(QDialog):
    def __init__(self, record: ProjectRecord, today: date, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(uz.t("btn.stage"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        cur = record.stage
        form.addRow(uz.t("stage.current"), QLabel(uz.STAGE[cur]))
        self.to = QComboBox()
        for s in [x for x in ("development", "ready", "abandoned") if x in TRANSITIONS[cur]] + \
                 ([cur] if cur != "research" else []):
            label = uz.STAGE[s] + (" (sanani tuzatish)" if s == cur else "")
            self.to.addItem(label, s)
        self.on = DateEdit(today)
        self.life = QSpinBox()
        self.life.setRange(0, 1200)
        self.life.setValue(record.useful_life_months)
        self.life.setSuffix(" oy")
        self.note = QLineEdit()
        form.addRow(uz.t("stage.to"), self.to)
        form.addRow(uz.t("stage.date"), self.on)
        self.life_row = QLabel(uz.t("f.life"))
        form.addRow(self.life_row, self.life)
        form.addRow(uz.t("f.note"), self.note)
        lay.addLayout(form)
        self.hint = QLabel(uz.t("stage.need_ready"))
        self.hint.setWordWrap(True)
        self.hint.setObjectName("Muted")
        lay.addWidget(self.hint)
        bb, self.ok = _buttons(self)
        lay.addWidget(bb)
        self.to.currentIndexChanged.connect(self._sync)
        self._sync()
        self.ok.setEnabled(self.to.count() > 0)
        self.setMinimumWidth(480)

    def _sync(self):
        ready = self.to.currentData() == "ready"
        self.life.setVisible(ready)
        self.life_row.setVisible(ready)
        self.hint.setVisible(ready)

    def values(self):
        return self.to.currentData(), self.on.value(), self.life.value(), self.note.text().strip()


# ---------------------------------------------------------------- assessment
class _CriterionRow:
    def __init__(self, grid: QGridLayout, row: int, key: str, prev: Optional[Answer], on: date, parent):
        self.key = key
        lb = QLabel(uz.CRITERION[key] + ("  ¹" if key == "K3_ability_use_or_sell" else ""))
        lb.setWordWrap(True)
        lb.setMinimumWidth(320)
        self.answer = combo(uz.ANSWER, prev.answer if prev else "expert")
        self.ev_type = QComboBox()
        self.ev_type.setEditable(True)
        self.ev_type.addItems(uz.EVIDENCE_TYPES)
        self.ev_number = QLineEdit()
        self.ev_number.setMinimumWidth(140)
        self.ev_number.setPlaceholderText(uz.t("crit.ev_number"))
        self.ev_date = DateEdit(on)
        self.ev_file = QLineEdit()
        self.ev_file.setPlaceholderText(uz.t("crit.ev_file"))
        self.browse = QPushButton("...")
        self.browse.setFixedWidth(34)
        self.browse.setStyleSheet("padding: 4px 2px;")
        self.browse.clicked.connect(lambda: self._pick(parent))
        if prev and prev.evidence:
            self.ev_type.setCurrentText(prev.evidence.doc_type)
            self.ev_number.setText(prev.evidence.number)
            self.ev_date.setValue(prev.evidence.doc_date)
            self.ev_file.setText(prev.evidence.file_path)
        for c, w in enumerate((lb, self.answer, self.ev_type, self.ev_number, self.ev_date, self.ev_file, self.browse)):
            grid.addWidget(w, row, c)
        self.answer.currentIndexChanged.connect(self._sync)
        self._sync()

    def _pick(self, parent):
        path, _ = QFileDialog.getOpenFileName(parent, uz.t("btn.choose_file"))
        if path:
            self.ev_file.setText(path)

    def _sync(self):
        on = self.answer.currentData() == "yes"
        for w in (self.ev_type, self.ev_number, self.ev_date, self.ev_file, self.browse):
            w.setEnabled(on)

    def value(self) -> Answer:
        a = self.answer.currentData()
        ev = None
        if a == "yes" and self.ev_type.currentText().strip() and self.ev_number.text().strip():
            ev = EvidenceDoc(self.ev_type.currentText().strip(), self.ev_number.text().strip(),
                             self.ev_date.value(), self.ev_file.text().strip())
        return Answer(a, ev)


class AssessmentDialog(QDialog):
    """New assessment version. 'Ha' requires an evidence document; otherwise it can only be
    saved explicitly as a draft (then E1 is raised)."""

    def __init__(self, repo, user: User, pid: int, today: date, prev: Optional[AssessmentRecord] = None,
                 parent=None):
        super().__init__(parent)
        self.repo, self.user, self.pid = repo, user, pid
        self.setWindowTitle(uz.t("btn.new_assessment"))
        lay = QVBoxLayout(self)
        top = QFormLayout()
        self.on = DateEdit(today)
        self.note = QLineEdit()
        top.addRow(uz.t("crit.date"), self.on)
        top.addRow(uz.t("f.note"), self.note)
        lay.addLayout(top)
        box = QGroupBox(uz.t("tab.criteria"))
        grid = QGridLayout(box)
        for c, h in enumerate((uz.t("col.criterion"), uz.t("col.answer"), uz.t("crit.ev_type"),
                               uz.t("crit.ev_number"), uz.t("crit.ev_date"), uz.t("crit.ev_file"))):
            hl = QLabel(h); hl.setObjectName("Muted"); grid.addWidget(hl, 0, c)
        self.rows = [_CriterionRow(grid, i, k, prev.answers.get(k) if prev else None, today, self)
                     for i, k in enumerate(CRITERIA, 1)]
        lay.addWidget(box)
        foot = QLabel("¹ " + uz.t("crit.k3_note"))
        foot.setObjectName("Muted")
        lay.addWidget(foot)
        bb = QDialogButtonBox()
        save = bb.addButton(uz.t("btn.save"), QDialogButtonBox.AcceptRole)
        save.setObjectName("Primary")
        draft = bb.addButton(uz.t("btn.save_draft"), QDialogButtonBox.ActionRole)
        bb.addButton(uz.t("btn.cancel"), QDialogButtonBox.RejectRole)
        save.clicked.connect(lambda: self._save(False))
        draft.clicked.connect(lambda: self._save(True))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.saved_id = None
        self.resize(1180, 440)

    def record(self, draft: bool) -> AssessmentRecord:
        return AssessmentRecord(self.pid, self.on.value(), {r.key: r.value() for r in self.rows}, is_draft=draft,
                                note=self.note.text().strip())

    def _save(self, draft: bool):
        try:
            self.saved_id = self.repo.add_assessment(self.record(draft), self.user)
        except EvidenceRequired as e:
            names = "\n".join("• " + uz.CRITERION[k] for k in e.keys)
            if choose(self, uz.t("crit.need_evidence", criterion="\n" + names),
                      [uz.t("btn.save_draft"), uz.t("btn.cancel")]) == 0:
                self._save(True)
            return
        except (ValueError, PermissionError) as e:
            error(self, str(e))
            return
        self.accept()


# ---------------------------------------------------------------- cost
class CostDialog(QDialog):
    def __init__(self, pid: int, today: date, cost: Optional[CostRecord] = None, parent=None):
        super().__init__(parent)
        self.pid, self.cost = pid, cost
        self.setWindowTitle(uz.t("cost.new") if cost is None else uz.t("btn.edit"))
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.on = DateEdit(cost.on_date if cost else today)
        self.amount = MoneyEdit(cost.amount if cost else None)
        self.category = QComboBox()
        for c in CATEGORY_ORDER:
            self.category.addItem(uz.CATEGORY[c], c)
        if cost:
            self.category.setCurrentIndex(self.category.findData(cost.category))
        self.document = QLineEdit(cost.document if cost else "")
        self.comment = QLineEdit(cost.comment if cost else "")
        form.addRow(uz.t("col.date"), self.on)
        form.addRow(uz.t("col.amount") + " (so'm) *", self.amount)
        form.addRow(uz.t("col.category"), self.category)
        form.addRow(uz.t("col.document"), self.document)
        form.addRow(uz.t("col.comment"), self.comment)
        lay.addLayout(form)
        bb, _ = _buttons(self)
        lay.addWidget(bb)
        self.setMinimumWidth(480)

    def accept(self):
        try:
            v = self.amount.value()
        except ValueError:
            v = None
        if not v:
            error(self, uz.t("msg.required", field=uz.t("col.amount")))
            return
        super().accept()

    def record(self) -> CostRecord:
        return CostRecord(self.pid, self.on.value(), self.amount.value(), self.category.currentData(),
                          self.document.text().strip(), self.comment.text().strip(),
                          self.cost.id if self.cost else None)
