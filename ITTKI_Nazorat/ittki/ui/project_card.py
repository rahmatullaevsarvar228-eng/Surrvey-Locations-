"""Loyiha kartasi: tabs Ma'lumot, Bosqichlar, Mezonlar, Xarajatlar, Qaror, Provodkalar, Amortizatsiya, Solishtirma."""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from ..core.defaults import ACCOUNT_NAMES
from ..core.engine import CRITERIA, FRAMEWORKS, _assessment_status
from ..core.rules import rule_code, rule_ref, reason_text
from ..db.repository import ImpairmentTest, User
from ..i18n import uz
from ..services import Analysis, Service, cost_rows
from . import style
from .dialogs import AssessmentDialog, CostDialog, StageDialog, combo
from .widgets import (Cell, can, DateEdit, MoneyEdit, OptionalDate, badge, confirm, error, fill_table, info, make_table,
                      money_cell, selected_data, wrap_rows)

T = uz.t


def _fw_combo():
    c = QComboBox()
    for fw in FRAMEWORKS:
        c.addItem(uz.FW[fw], fw)
    return c


def _acc(code: str) -> str:
    name = ACCOUNT_NAMES.get(code)
    return f"{code} {name}" if name else code


class ProjectCard(QWidget):
    def __init__(self, service: Service, user: User, pid: int, on_change: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.service, self.repo, self.user, self.pid = service, service.repo, user, pid
        self.on_change = on_change
        self.readonly = user.role == "auditor"
        self.setWindowTitle(T("card.title"))
        self.resize(1280, 820)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.title.setWordWrap(True)
        self.demo = QLabel(uz.DEMO_MARK)
        self.demo.setObjectName("DemoMark")
        lay.addWidget(self.title)
        lay.addWidget(self.demo)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self._build_info()
        self._build_stages()
        self._build_criteria()
        self._build_costs()
        self._build_decision()
        self._build_journal()
        self._build_amort()
        self._build_reconcile()
        self.refresh()

    # ------------------------------------------------------------ common
    def _changed(self):
        self.refresh()
        if self.on_change:
            self.on_change()

    def _can(self, action: str) -> bool:
        return can(self, self.repo, self.user, action)

    def _ro(self, *widgets):
        for w in widgets:
            w.setEnabled(not self.readonly)

    def refresh(self):
        self.rec = self.repo.project(self.pid)
        self.a: Analysis = self.service.analyze(self.pid)
        self.title.setText(f"{self.rec.code} — {self.rec.name}")
        self.setWindowTitle(f"{T('card.title')}: {self.rec.code}")
        self.demo.setVisible(self.rec.is_demo)
        self._fill_info()
        self._fill_stages()
        self._fill_criteria()
        self._fill_costs()
        self._fill_decision()
        self._fill_journal()
        self._fill_amort()
        self._fill_reconcile()

    # ------------------------------------------------------------ Ma'lumot
    def _build_info(self):
        w = QWidget()
        outer = QHBoxLayout(w)
        left = QGroupBox(T("tab.info"))
        f = QFormLayout(left)
        self.f_code = QLineEdit(); self.f_code.setReadOnly(True)
        self.f_name = QLineEdit()
        self.f_scope = combo(uz.SCOPE)
        self.f_dept = QLineEdit()
        self.f_leader = QLineEdit()
        self.f_start = OptionalDate()
        self.f_budget = MoneyEdit()
        self.f_sep = QCheckBox(T("f.separable"))
        self.f_life = QSpinBox(); self.f_life.setRange(0, 1200); self.f_life.setSuffix(" oy")
        self.f_benefit = MoneyEdit()
        self.f_note = QPlainTextEdit(); self.f_note.setFixedHeight(70)
        self.f_status = QLabel()
        self.f_dates = QLabel(); self.f_dates.setObjectName("Muted")
        for label, wd in (("f.code", self.f_code), ("f.name", self.f_name), ("f.type", self.f_scope),
                          ("f.department", self.f_dept), ("f.leader", self.f_leader), ("f.start", self.f_start),
                          ("f.budget", self.f_budget)):
            f.addRow(T(label), wd)
        f.addRow("", self.f_sep)
        f.addRow(T("f.life"), self.f_life)
        f.addRow(T("f.benefit"), self.f_benefit)
        f.addRow(T("col.status"), self.f_status)
        f.addRow(T("tab.stages"), self.f_dates)
        f.addRow(T("f.note"), self.f_note)
        self.b_save = QPushButton(T("btn.save")); self.b_save.setObjectName("Primary")
        self.b_save.clicked.connect(self._save_info)
        f.addRow("", self.b_save)
        outer.addWidget(left, 3)

        right = QGroupBox(T("f.impairment"))
        r = QVBoxLayout(right)
        rf = QFormLayout()
        self.i_date = OptionalDate()
        self.i_amount = MoneyEdit()
        rf.addRow(T("f.imp_date"), self.i_date)
        rf.addRow(T("f.imp_amount"), self.i_amount)
        r.addLayout(rf)
        self.b_imp = QPushButton(T("btn.save"))
        self.b_imp.clicked.connect(self._save_impairment)
        r.addWidget(self.b_imp, alignment=Qt.AlignLeft)
        r.addWidget(QLabel(T("f.imp_tests")))
        self.t_tests = make_table([T("col.date"), T("col.comment")])
        r.addWidget(self.t_tests)
        h = QHBoxLayout()
        self.t_date = DateEdit(self.service.today())
        self.t_note = QLineEdit(); self.t_note.setPlaceholderText(T("col.comment"))
        self.b_test_add = QPushButton(T("f.add_test"))
        self.b_test_del = QPushButton(T("btn.delete"))
        self.b_test_add.clicked.connect(self._add_test)
        self.b_test_del.clicked.connect(self._del_test)
        for x in (self.t_date, self.t_note, self.b_test_add, self.b_test_del):
            h.addWidget(x)
        r.addLayout(h)
        outer.addWidget(right, 2)
        self._ro(self.b_save, self.b_imp, self.b_test_add, self.b_test_del)
        self.tabs.addTab(w, T("tab.info"))

    def _fill_info(self):
        p = self.rec
        self.f_code.setText(p.code)
        self.f_name.setText(p.name)
        self.f_scope.setCurrentIndex(self.f_scope.findData(p.scope))
        self.f_dept.setText(p.department)
        self.f_leader.setText(p.leader)
        self.f_start.setValue(p.start_date)
        self.f_budget.setValue(p.budget)
        self.f_sep.setChecked(p.phases_separable)
        self.f_life.setValue(p.useful_life_months)
        self.f_benefit.setValue(p.expected_net_benefit)
        self.f_note.setPlainText(p.note)
        self.f_status.setText(f"{uz.PROJECT_STATUS[p.status]} · {uz.STAGE[p.stage]}")
        self.f_dates.setText(
            f"{T('f.dev_start')}: {uz.fdate(p.development_start) or '—'}\n"
            f"{T('f.ready')}: {uz.fdate(p.available_for_use) or '—'}\n"
            f"{T('f.abandoned')}: {uz.fdate(p.abandoned_on) or '—'}")
        ev = self.repo.impairment_event(self.pid)
        self.i_date.setValue(ev[0] if ev else None)
        self.i_amount.setValue(ev[1] if ev else None)
        fill_table(self.t_tests, [[Cell(uz.fdate(t.on_date), data=t.id), t.note]
                                  for t in self.repo.impairment_tests(self.pid)])

    def _save_info(self):
        if not self._can("project"):
            return
        p = self.rec
        try:
            p.budget = self.f_budget.value()
            p.expected_net_benefit = self.f_benefit.value()
        except ValueError:
            error(self, T("set.invalid", error=T("f.budget")))
            return
        if not self.f_name.text().strip():
            error(self, T("msg.required", field=T("f.name")))
            return
        p.name = self.f_name.text().strip()
        p.scope = self.f_scope.currentData()
        p.department = self.f_dept.text().strip()
        p.leader = self.f_leader.text().strip()
        p.start_date = self.f_start.value()
        p.phases_separable = self.f_sep.isChecked()
        p.useful_life_months = self.f_life.value()
        p.note = self.f_note.toPlainText()
        self.repo.save_project(p, self.user)
        self._changed()

    def _save_impairment(self):
        if not self._can("impairment"):
            return
        on = self.i_date.value()
        try:
            amt = self.i_amount.value()
        except ValueError:
            amt = None
        if on is not None and amt is None:
            error(self, T("msg.required", field=T("f.imp_amount")))
            return
        self.repo.set_impairment_event(self.pid, on, amt if on else None, self.user)
        self._changed()

    def _add_test(self):
        if not self._can("impairment"):
            return
        self.repo.add_impairment_test(ImpairmentTest(self.pid, self.t_date.value(), self.t_note.text().strip()),
                                      self.user)
        self.t_note.clear()
        self._changed()

    def _del_test(self):
        if not self._can("impairment"):
            return
        tid = selected_data(self.t_tests)
        if tid is None:
            info(self, T("msg.select_row")); return
        if confirm(self, T("msg.confirm_delete")):
            self.repo.delete_impairment_test(tid, self.user)
            self._changed()

    # ------------------------------------------------------------ Bosqichlar
    def _build_stages(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        self.s_current = QLabel()
        self.s_current.setStyleSheet("font-size: 12pt; font-weight: 600;")
        self.b_stage = QPushButton(T("btn.stage")); self.b_stage.setObjectName("Primary")
        self.b_stage.clicked.connect(self._change_stage)
        h.addWidget(QLabel(T("stage.current") + ":"))
        h.addWidget(self.s_current)
        h.addStretch()
        h.addWidget(self.b_stage)
        lay.addLayout(h)
        self.s_flow = QLabel("Tadqiqot  →  Ishlanma  →  Foydalanishga tayyor   |   To'xtatilgan")
        self.s_flow.setObjectName("Muted")
        lay.addWidget(self.s_flow)
        lay.addWidget(QLabel(T("stage.history")))
        self.t_stages = make_table([T("stage.date"), T("col.stage_from"), T("col.stage_to"), T("f.note"),
                                    T("col.who"), T("col.role"), T("col.when")], stretch=3)
        lay.addWidget(self.t_stages)
        self._ro(self.b_stage)
        self.tabs.addTab(w, T("tab.stages"))

    def _fill_stages(self):
        self.s_current.setText(uz.STAGE[self.rec.stage])
        fill_table(self.t_stages, [[uz.fdate(e.on_date), uz.STAGE.get(e.from_stage, ""), uz.STAGE[e.to_stage],
                                    e.note, e.actor, uz.ROLE.get(e.role, e.role), e.created_at.replace("T", " ")]
                                   for e in self.repo.stage_events(self.pid)])
        self.b_stage.setEnabled(not self.readonly and self.rec.stage != "abandoned")

    def _change_stage(self):
        if not self._can("stage"):
            return
        d = StageDialog(self.rec, self.service.today(), self)
        if not d.exec():
            return
        to, on, life, note = d.values()
        try:
            if to == "ready" and life != self.rec.useful_life_months:
                self.rec.useful_life_months = life
                self.repo.save_project(self.rec, self.user)
            self.repo.change_stage(self.pid, to, on, self.user, note)
        except (ValueError, PermissionError) as e:
            error(self, str(e)); return
        self._changed()

    # ------------------------------------------------------------ Mezonlar
    def _build_criteria(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel(T("crit.history")))
        h.addStretch()
        self.b_assess = QPushButton(T("btn.new_assessment")); self.b_assess.setObjectName("Primary")
        self.b_assess.clicked.connect(self._new_assessment)
        h.addWidget(self.b_assess)
        lay.addLayout(h)
        split = QSplitter(Qt.Vertical)
        self.t_asm = make_table([T("crit.date"), T("crit.draft"), f"{T('crit.status')} IAS 38",
                                 f"{T('crit.status')} BHMS 11", T("col.who"), T("col.role"), T("f.note")])
        self.t_asm.currentCellChanged.connect(lambda *a: self._show_assessment())
        self.t_ans = make_table([T("col.criterion"), T("col.answer"), T("col.evidence"), "IAS 38", "BHMS 11"],
                                stretch=2)
        split.addWidget(self.t_asm)
        split.addWidget(self.t_ans)
        split.setSizes([260, 300])
        lay.addWidget(split)
        note = QLabel("Holat: 'Bajarilgan' — barcha majburiy mezonlar 'Ha' va har birida dalil hujjati bor; "
                      "'Yo'q' — kamida bitta 'Yo'q'; aks holda 'Kutilmoqda'. Shu sanadan boshlab oxirgi baho amal "
                      "qiladi; bir kunda bir nechta baho bo'lsa — oxirgi kiritilgani.")
        note.setWordWrap(True); note.setObjectName("Muted")
        lay.addWidget(note)
        self._ro(self.b_assess)
        self.tabs.addTab(w, T("tab.criteria"))

    def _fill_criteria(self):
        self.asm = self.repo.assessments(self.pid)
        rows = []
        for a in self.asm:
            eng = self.a.project.assessments[self.asm.index(a)]
            cells = [Cell(uz.fdate(a.on_date), data=a.id), T("yes") if a.is_draft else ""]
            for fw in FRAMEWORKS:
                st = _assessment_status(eng, fw)[0]
                fg, bg = style.status_colors(st)
                cells.append(Cell(uz.STATUS[st], fg=fg, bg=bg, bold=True))
            cells += [a.actor, uz.ROLE.get(a.role, a.role), a.note]
            rows.append(cells)
        fill_table(self.t_asm, rows)
        if self.asm:
            self.t_asm.selectRow(len(self.asm) - 1)
        self._show_assessment()

    def _show_assessment(self):
        r = self.t_asm.currentRow()
        if r < 0 or r >= len(self.asm):
            fill_table(self.t_ans, [])
            return
        a = self.asm[r]
        rows = []
        for k, refs in CRITERIA.items():
            ans = a.answers.get(k)
            v = ans.answer if ans else None
            fg, bg = {"yes": (style.GREEN, None), "no": (style.RED, None)}.get(v, (style.YELLOW, None))
            ev = ans.evidence.ref() if ans and ans.evidence else ("— (E1)" if v == "yes" else "")
            rows.append([uz.CRITERION[k], Cell(uz.ANSWER.get(v, "—"), fg=fg, bold=True),
                         Cell(ev, fg=style.RED if ev.startswith("—") else None),
                         refs["IAS38"], refs["NAS11"] or "— (alohida mezon yo'q)"])
        fill_table(self.t_ans, rows)

    def _new_assessment(self):
        if not self._can("assessment"):
            return
        prev = self.asm[-1] if self.asm else None
        d = AssessmentDialog(self.repo, self.user, self.pid, self.service.today(), prev, self)
        if d.exec():
            self._changed()

    # ------------------------------------------------------------ Xarajatlar
    def _build_costs(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        self.c_total = QLabel()
        self.c_total.setStyleSheet("font-weight: 600;")
        h.addWidget(self.c_total)
        h.addStretch()
        self.b_c_add = QPushButton(T("btn.add")); self.b_c_add.setObjectName("Primary")
        self.b_c_edit = QPushButton(T("btn.edit"))
        self.b_c_del = QPushButton(T("btn.delete"))
        self.b_c_imp = QPushButton(T("btn.import"))
        for b, fn in ((self.b_c_add, self._add_cost), (self.b_c_edit, self._edit_cost),
                      (self.b_c_del, self._del_cost), (self.b_c_imp, self._import_costs)):
            b.clicked.connect(fn); h.addWidget(b)
        lay.addLayout(h)
        self.t_costs = make_table([T("col.date"), T("col.amount"), T("col.category"), T("col.document"),
                                   T("col.comment"), "IAS 38", "BHMS 11"], stretch=4)
        self.t_costs.doubleClicked.connect(lambda *_: self._edit_cost())
        lay.addWidget(self.t_costs)
        self._ro(self.b_c_add, self.b_c_edit, self.b_c_del, self.b_c_imp)
        self.tabs.addTab(w, T("tab.costs"))

    def _fill_costs(self):
        self.costs = self.repo.costs(self.pid)
        per_fw = {fw: cost_rows(self.a, fw) for fw in FRAMEWORKS}
        rows = []
        for i, c in enumerate(self.costs):
            cells = [Cell(uz.fdate(c.on_date), data=c.id), money_cell(c.amount), uz.CATEGORY[c.category],
                     c.document, c.comment]
            for fw in FRAMEWORKS:
                rr = per_fw[fw][i] if i < len(per_fw[fw]) else []
                if not rr:
                    cells.append(Cell("—", fg=style.GREY))
                    continue
                txt = " + ".join(f"{uz.TREATMENT[r['treatment']]} ({rule_code(r['reason'])})"
                                 + (f" {uz.money(r['amount'])}" if len(rr) > 1 else "") for r in rr)
                fg, bg = style.treatment_colors(rr[0]["treatment"] if len(rr) == 1 else "expense")
                if len(rr) > 1:
                    fg, bg = style.YELLOW, style.YELLOW_BG
                cells.append(Cell(txt, fg=fg, bg=bg))
            rows.append(cells)
        fill_table(self.t_costs, rows)
        self.c_total.setText(f"{T('cost.total')}: {uz.money(sum(c.amount for c in self.costs))} so'm"
                             + (f"   ·   {T('f.budget')}: {uz.money(self.rec.budget)}" if self.rec.budget else ""))

    def _cost_by_id(self, cid):
        return next((c for c in self.costs if c.id == cid), None)

    def _add_cost(self):
        if not self._can("cost"):
            return
        d = CostDialog(self.pid, self.service.today(), parent=self)
        if d.exec():
            self.repo.add_cost(d.record(), self.user)
            self._changed()

    def _edit_cost(self):
        if self.readonly:
            return
        if not self._can("cost"):
            return
        c = self._cost_by_id(selected_data(self.t_costs))
        if c is None:
            info(self, T("msg.select_row")); return
        d = CostDialog(self.pid, self.service.today(), c, self)
        if d.exec():
            self.repo.update_cost(d.record(), self.user)
            self._changed()

    def _del_cost(self):
        if not self._can("cost"):
            return
        cid = selected_data(self.t_costs)
        if cid is None:
            info(self, T("msg.select_row")); return
        if confirm(self, T("msg.confirm_delete")):
            self.repo.delete_cost(cid, self.user)
            self._changed()

    def _import_costs(self):
        if not self._can("import"):
            return
        path, _ = QFileDialog.getOpenFileName(self, T("btn.import"), "", "Excel (*.xlsx)")
        if not path:
            return
        from ..reports.excel_import import read_costs
        records, errors = read_costs(path, self.pid)
        if errors:
            error(self, T("cost.import_errors") + ":\n" + "\n".join(errors[:30]))
            if not records or not confirm(self, T("cost.imported", n=len(records)) + "?"):
                return
        self.repo.add_costs(records, self.user)
        info(self, T("cost.imported", n=len(records)))
        self._changed()

    # ------------------------------------------------------------ Qaror
    def _build_decision(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        self.d_cols = {}
        for fw in FRAMEWORKS:
            box = QGroupBox(uz.FW[fw])
            v = QVBoxLayout(box)
            b = QLabel(); v.addWidget(b)
            grid = QGridLayout()
            vals = {}
            for i, k in enumerate(("dec.capitalized", "dec.expensed", "dec.writeoff", "dec.amort_months",
                                   "dec.carrying", "dec.first_met", "dec.status_today")):
                lb = QLabel(T(k)); lb.setObjectName("Muted")
                val = QLabel(); val.setStyleSheet("font-weight: 600;")
                val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                grid.addWidget(lb, i, 0); grid.addWidget(val, i, 1)
                vals[k] = val
            v.addLayout(grid)
            t = make_table([T("col.date"), T("col.amount"), T("col.treatment"), T("col.reason"),
                            T("col.standard")], stretch=3)
            v.addWidget(t, 1)
            wl = QLabel(); wl.setWordWrap(True); wl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            wl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(wl); sc.setMaximumHeight(130)
            v.addWidget(QLabel(T("dec.warnings")))
            v.addWidget(sc)
            lay.addWidget(box)
            self.d_cols[fw] = (box, v, b, vals, t, wl)
        self.tabs.addTab(w, T("tab.decision"))

    def _fill_decision(self):
        a = self.a
        for fw in FRAMEWORKS:
            box, v, old_badge, vals, t, wl = self.d_cols[fw]
            r = a.res[fw]
            fg, bg = style.decision_colors(r["decision"], a.status[fw])
            nb = badge(uz.DECISION[r["decision"]], fg, bg)
            v.replaceWidget(old_badge, nb)
            old_badge.deleteLater()
            self.d_cols[fw] = (box, v, nb, vals, t, wl)
            writeoff = sum(e.amount for e in a.journal[fw]
                           if e.op in ("nas_writeoff", "abandon_writeoff", "disposal_residual"))
            vals["dec.capitalized"].setText(uz.money(r["capitalized"]) + " so'm")
            vals["dec.expensed"].setText(uz.money(r["expensed"]) + " so'm")
            vals["dec.writeoff"].setText(uz.money(writeoff) + " so'm")
            vals["dec.amort_months"].setText(str(r["amort_months"] or "—"))
            vals["dec.carrying"].setText(uz.money(a.carrying[fw]) + " so'm")
            vals["dec.first_met"].setText(uz.fdate(r["first_met_on"]) or "—")
            sfg, _ = style.status_colors(a.status[fw])
            vals["dec.status_today"].setText(uz.STATUS[a.status[fw]])
            vals["dec.status_today"].setStyleSheet(f"font-weight: 600; color: {sfg};")
            rows = []
            for x in r["rows"]:
                tfg, tbg = style.treatment_colors(x["treatment"])
                rows.append([uz.fdate(x["date"]), money_cell(x["amount"]),
                             Cell(uz.TREATMENT[x["treatment"]], fg=tfg, bg=tbg, bold=True),
                             f"{rule_code(x['reason'])}: {reason_text(x['reason'])} · {uz.CATEGORY[x['category']]}",
                             rule_ref(x["reason"], fw)])
            fill_table(t, rows)
            wrap_rows(t)
            warn = list(r["warnings"])
            if r["decision"] == "STANDART QO'LLANILMAYDI":
                warn.insert(0, f"{T('dec.ref')}: {r['out_of_scope_ref']}")
            wl.setText("\n".join("• " + x for x in warn) or "—")

    # ------------------------------------------------------------ Provodkalar
    def _build_journal(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        self.j_fw = _fw_combo()
        self.j_fw.currentIndexChanged.connect(lambda *_: self._fill_journal())
        h.addWidget(QLabel(T("amort.fw")))
        h.addWidget(self.j_fw)
        h.addStretch()
        self.j_total = QLabel(); self.j_total.setObjectName("Muted")
        h.addWidget(self.j_total)
        lay.addLayout(h)
        self.t_journal = make_table([T("col.date"), T("col.operation"), T("col.debit"), T("col.credit"),
                                     T("col.amount"), T("col.reason")], stretch=5)
        lay.addWidget(self.t_journal)
        self.tabs.addTab(w, T("tab.journal"))

    def _fill_journal(self):
        fw = self.j_fw.currentData()
        entries = self.a.journal[fw]
        fill_table(self.t_journal, [[uz.fdate(e.on), uz.JOURNAL_OPS[e.op], _acc(e.debit), _acc(e.credit),
                                     money_cell(e.amount), e.reason] for e in entries])
        self.j_total.setText(f"{len(entries)} ta provodka · {uz.money(sum(e.amount for e in entries))} so'm")

    # ------------------------------------------------------------ Amortizatsiya
    def _build_amort(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        self.am_fw = _fw_combo()
        self.am_fw.currentIndexChanged.connect(lambda *_: self._fill_amort())
        h.addWidget(QLabel(T("amort.fw")))
        h.addWidget(self.am_fw)
        self.am_info = QLabel(); self.am_info.setObjectName("Muted")
        h.addWidget(self.am_info)
        h.addStretch()
        self.b_am_exp = QPushButton(T("btn.export"))
        self.b_am_exp.clicked.connect(self._export_amort)
        h.addWidget(self.b_am_exp)
        lay.addLayout(h)
        self.t_amort = make_table([T("col.period"), T("col.opening"), T("col.amortization"), T("col.impairment"),
                                   T("col.closing")])
        lay.addWidget(self.t_amort)
        self.tabs.addTab(w, T("tab.amort"))

    def _fill_amort(self):
        fw = self.am_fw.currentData()
        sch = self.a.schedule[fw]
        fill_table(self.t_amort, [[Cell(r["period_end"].strftime("%m.%Y"), "center"), money_cell(r["opening"]),
                                   money_cell(r["amortization"]),
                                   money_cell(r["impairment"], fg=style.RED if r["impairment"] else None),
                                   money_cell(r["closing"])] for r in sch])
        res = self.a.res[fw]
        if sch:
            self.am_info.setText(f"  {res['amort_months']} oy · {uz.fdate(sch[0]['period_end'])} — "
                                 f"{uz.fdate(sch[-1]['period_end'])} · jami "
                                 f"{uz.money(sum(r['amortization'] for r in sch))} so'm")
        else:
            self.am_info.setText("  " + T("amort.empty"))

    def _export_amort(self):
        if not self._can("report"):
            return
        path, _ = QFileDialog.getSaveFileName(self, T("btn.export"), f"amortizatsiya_{self.rec.code}.xlsx",
                                              "Excel (*.xlsx)")
        if path:
            from ..reports.excel import export_schedule
            export_schedule([self.a], path, self.service.settings)
            info(self, T("rep.saved", path=path))

    # ------------------------------------------------------------ Solishtirma
    def _build_reconcile(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel(T("rec.date")))
        self.r_date = DateEdit(self.service.today())
        self.r_date.dateChanged.connect(lambda *_: self._fill_reconcile())
        h.addWidget(self.r_date)
        h.addStretch()
        lay.addLayout(h)
        self.t_rec = make_table([T("col.indicator"), T("col.ias"), T("col.nas"), T("col.diff")], stretch=0)
        self.t_rec.setMaximumHeight(140)
        lay.addWidget(self.t_rec)
        lay.addWidget(QLabel(T("rec.reasons")))
        self.r_reasons = QLabel(); self.r_reasons.setWordWrap(True)
        self.r_reasons.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.r_reasons.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(self.r_reasons)
        lay.addWidget(sc)
        self.tabs.addTab(w, T("tab.reconcile"))

    def _fill_reconcile(self):
        at = self.r_date.value()
        a = self.a if at == self.a.as_of else self.service.analyze(self.pid, at)
        ri, rn = a.res["IAS38"], a.res["NAS11"]
        rows = []
        for label, x, y in ((T("rec.capitalized"), ri["capitalized"], rn["capitalized"]),
                            (T("rec.expensed"), ri["expensed"], rn["expensed"]),
                            (T("rec.carrying"), a.carrying["IAS38"], a.carrying["NAS11"])):
            diff = x - y
            rows.append([Cell(label, bold=True), money_cell(x), money_cell(y),
                         money_cell(diff, fg=style.RED if diff else None, bold=bool(diff))])
        rows.append([Cell(T("rec.amort_months"), bold=True), Cell(ri["amort_months"], "right"),
                     Cell(rn["amort_months"], "right"), Cell(ri["amort_months"] - rn["amort_months"], "right")])
        fill_table(self.t_rec, rows)
        self.r_reasons.setText("\n".join("• " + x for x in a.reasons))
