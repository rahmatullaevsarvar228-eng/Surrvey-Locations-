"""Main window pages: Bosh sahifa, Loyihalar, Nazorat, Hisobotlar, Sozlamalar, Audit jurnali."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QTableWidget, QVBoxLayout,
                               QWidget)

from ..core.appsettings import AppSettings
from ..core.controls import LEVELS, ControlSettings
from ..core.defaults import ACCOUNT_NAMES, DEFAULT_ACCOUNTS, DEFAULT_CONTROLS
from ..core.engine import AMORT_START_MODES, FRAMEWORKS, Settings
from ..core.journal import Accounts
from ..db.repository import User
from .. import clock
from ..i18n import uz
from ..services import Service
from . import style
from .dialogs import CATEGORY_ORDER, NewProjectDialog, combo
from .widgets import (Cell, can, DateEdit, card, error, fill_table, info, make_table, money_cell, page_title,
                      selected_data)

T = uz.t


class Page(QWidget):
    open_project = Signal(int)
    changed = Signal()

    def __init__(self, service: Service, user: User, parent=None):
        super().__init__(parent)
        self.service, self.repo, self.user = service, service.repo, user
        self.readonly = user.role == "auditor"
        self.setObjectName("Page")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(22, 16, 22, 16)

    def refresh(self):
        pass


def _decision_cell(res, status):
    fg, bg = style.decision_colors(res["decision"], status)
    return Cell(uz.DECISION_SHORT[res["decision"]], fg=fg, bg=bg, bold=True)


# ---------------------------------------------------------------- Bosh sahifa
class HomePage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        h = QHBoxLayout()
        h.addWidget(page_title(T("home.title")))
        h.addStretch()
        self.as_of = QLabel(); self.as_of.setObjectName("Muted")
        h.addWidget(self.as_of)
        self.lay.addLayout(h)
        self.cards = QGridLayout()
        self.cards.setSpacing(10)
        self.lay.addLayout(self.cards)
        self.c = {}
        for i, (k, label) in enumerate((("projects", T("home.projects")),
                                        ("cap", T("home.capitalized")),
                                        ("exp", T("home.expensed")),
                                        ("exc", T("home.exceptions")))):
            w = card(label, "")
            self.c[k] = w
            self.cards.addWidget(w, 0, i)
        self.lay.addSpacing(8)
        self.lay.addWidget(QLabel(T("home.by_project")))
        self.table = make_table([T("col.code"), T("col.name"), T("col.stage"), "Qaror IAS 38", "Qaror BHMS 11",
                                 "Balans qiymati IAS 38", "Balans qiymati BHMS 11", T("home.exceptions")], stretch=1)
        self.table.doubleClicked.connect(lambda *_: self._open())
        self.lay.addWidget(self.table, 1)
        b = QHBoxLayout()
        self.b_demo = QPushButton(T("home.demo"))
        self.b_demo.clicked.connect(self._demo)
        self.b_backup = QPushButton(T("home.backup"))
        self.b_backup.clicked.connect(self._backup)
        b.addWidget(self.b_demo)
        b.addWidget(self.b_backup)
        b.addStretch()
        self.lay.addLayout(b)
        self.b_backup.setEnabled(service.can(user, "backup"))

    def _set(self, key, value, sub=""):
        lab = self.c[key].value_label
        lab.setText(value + (f"\n{sub}" if sub else ""))

    def refresh(self):
        an = self.service.analyze_all()
        t = self.service.totals(an)
        self.as_of.setText(f"{T('home.as_of')}: {uz.fdate(self.service.today())}")
        self._set("projects", str(t["projects"]))
        self._set("cap", f"IAS 38: {uz.money(t['capitalized.IAS38'])}", f"BHMS 11: {uz.money(t['capitalized.NAS11'])}")
        self._set("exp", f"IAS 38: {uz.money(t['expensed.IAS38'])}", f"BHMS 11: {uz.money(t['expensed.NAS11'])}")
        self._set("exc", str(t["findings"]),
                  f"{uz.LEVEL['high']}: {t['findings.high']} · {uz.LEVEL['medium']}: {t['findings.medium']} · "
                  f"{uz.LEVEL['info']}: {t['findings.info']}")
        for k in self.c:
            self.c[k].value_label.setStyleSheet("font-size: 12.5pt; font-weight: 600;")
        rows = []
        for a in an:
            high = sum(1 for f in a.findings if f.level == "high")
            rows.append([Cell(a.record.code, data=a.record.id), a.record.name, uz.STAGE[a.record.stage],
                         _decision_cell(a.res["IAS38"], a.status["IAS38"]),
                         _decision_cell(a.res["NAS11"], a.status["NAS11"]),
                         money_cell(a.carrying["IAS38"]), money_cell(a.carrying["NAS11"]),
                         Cell(f"{len(a.findings)}" + (f" ({high} yuqori)" if high else ""), "center",
                              fg=style.RED if high else None)])
        fill_table(self.table, rows)
        # Buxgalter only, and only into an empty database
        self.b_demo.setEnabled(self.service.can_load_demo(self.user))

    def _open(self):
        pid = selected_data(self.table)
        if pid is not None:
            self.open_project.emit(pid)

    def _demo(self):
        if not can(self, self.service, self.user, "demo"):
            return
        try:
            n = self.service.load_demo(self.user)
        except ValueError as e:                       # DemoRefused: the database is not empty
            error(self, str(e))
            return
        info(self, T("home.demo_done") if n else T("home.demo_exists"))
        self.changed.emit()

    def _backup(self):
        if not can(self, self.service, self.user, "backup"):
            return
        name = f"ittki_zaxira_{self.service.today():%Y%m%d}.sqlite3"
        path, _ = QFileDialog.getSaveFileName(self, T("home.backup"), name, "SQLite (*.sqlite3)")
        if path:
            self.service.backup(self.user, path)
            info(self, T("home.backup_done", path=path))


# ---------------------------------------------------------------- Loyihalar
class ProjectsPage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        h = QHBoxLayout()
        h.addWidget(page_title(T("nav.projects")))
        h.addStretch()
        self.b_new = QPushButton(T("projects.new")); self.b_new.setObjectName("Primary")
        self.b_new.clicked.connect(self._new)
        self.b_new.setEnabled(service.can(user, "project"))
        self.b_open = QPushButton(T("projects.open"))
        self.b_open.clicked.connect(self._open)
        h.addWidget(self.b_open)
        h.addWidget(self.b_new)
        self.lay.addLayout(h)
        f = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText(T("projects.search"))
        self.f_status = self._filter(uz.PROJECT_STATUS)
        self.f_stage = self._filter(uz.STAGE)
        self.f_dec = self._filter(uz.DECISION_SHORT)
        self.search.textChanged.connect(lambda *_: self._apply())
        f.addWidget(self.search, 2)
        for label, w in ((T("projects.filter_status"), self.f_status), (T("projects.filter_stage"), self.f_stage),
                         (T("projects.filter_decision"), self.f_dec)):
            f.addWidget(QLabel(label))
            f.addWidget(w, 1)
        self.lay.addLayout(f)
        self.table = make_table([T("col.code"), T("col.name"), T("col.type"), T("col.stage"), T("col.status"),
                                 T("col.leader"), T("col.budget"), T("col.costs"), "IAS 38", "BHMS 11"], stretch=1)
        self.table.doubleClicked.connect(lambda *_: self._open())
        self.lay.addWidget(self.table, 1)
        self.count = QLabel(); self.count.setObjectName("Muted")
        self.lay.addWidget(self.count)

    def _filter(self, items):
        c = QComboBox()
        c.addItem(T("projects.all"), None)
        for k, v in items.items():
            c.addItem(v, k)
        c.currentIndexChanged.connect(lambda *_: self._apply())
        return c

    def refresh(self):
        self.an = self.service.analyze_all()
        self._apply()

    def _apply(self):
        q = self.search.text().strip().lower()
        rows = []
        for a in getattr(self, "an", []):
            r = a.record
            if q and q not in r.code.lower() and q not in r.name.lower():
                continue
            if self.f_status.currentData() and r.status != self.f_status.currentData():
                continue
            if self.f_stage.currentData() and r.stage != self.f_stage.currentData():
                continue
            if self.f_dec.currentData() and a.res["IAS38"]["decision"] != self.f_dec.currentData():
                continue
            rows.append([Cell(r.code, data=r.id), r.name, uz.SCOPE[r.scope], uz.STAGE[r.stage],
                         uz.PROJECT_STATUS[r.status], r.leader, money_cell(r.budget) if r.budget else "",
                         money_cell(sum(c.amount for c in a.project.costs)),
                         _decision_cell(a.res["IAS38"], a.status["IAS38"]),
                         _decision_cell(a.res["NAS11"], a.status["NAS11"])])
        fill_table(self.table, rows)
        self.count.setText(f"{len(rows)} ta loyiha")

    def _open(self):
        pid = selected_data(self.table)
        if pid is None:
            info(self, T("msg.select_row")); return
        self.open_project.emit(pid)

    def _new(self):
        if not can(self, self.service, self.user, "project"):
            return
        d = NewProjectDialog(self.repo, self)
        if d.exec():
            try:
                pid = self.service.save_project(self.user, d.record())
            except PermissionError as e:
                error(self, str(e))
                return
            self.changed.emit()
            self.open_project.emit(pid)


# ---------------------------------------------------------------- Nazorat
class ControlsPage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        h = QHBoxLayout()
        h.addWidget(page_title(T("ctl.title")))
        h.addStretch()
        self.level = QComboBox()
        self.level.addItem(T("ctl.level_all"), None)
        for k, v in uz.LEVEL.items():
            self.level.addItem(v, k)
        self.level.currentIndexChanged.connect(lambda *_: self._apply())
        h.addWidget(self.level)
        self.lay.addLayout(h)
        self.table = make_table([T("col.level"), T("col.code_exc"), T("col.project"), "Qoida", T("col.message"),
                                 T("col.date")], stretch=4)
        self.table.doubleClicked.connect(lambda *_: self._open())
        self.lay.addWidget(self.table, 1)
        self.count = QLabel(); self.count.setObjectName("Muted")
        self.lay.addWidget(self.count)

    def refresh(self):
        self.items = self.service.findings_all()
        self._apply()

    def _apply(self):
        lv = self.level.currentData()
        rows = []
        for rec, f in self.items:
            if lv and f.level != lv:
                continue
            fg, bg = style.level_colors(f.level)
            rows.append([Cell(uz.LEVEL[f.level], fg=fg, bg=bg, bold=True, data=rec.id), Cell(f.code, "center"),
                         rec.code, uz.CONTROL_TITLE[f.code],
                         (f"[{uz.FW[f.framework]}] " if f.framework else "") + f.message, uz.fdate(f.on)])
        fill_table(self.table, rows)
        self.count.setText(T("ctl.count", n=len(rows)))

    def _open(self):
        pid = selected_data(self.table)
        if pid is not None:
            self.open_project.emit(pid)


# ---------------------------------------------------------------- Hisobotlar
class ReportsPage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        self.lay.addWidget(page_title(T("rep.title")))
        g = QGroupBox(T("rep.title"))
        f = QFormLayout(g)
        today = service.today()
        self.d_from = DateEdit(date(today.year - 1, 1, 1))
        self.d_to = DateEdit(date(today.year - 1, 12, 31))
        self.d_at = DateEdit(today)
        f.addRow(T("rep.period_from"), self.d_from)
        f.addRow(T("rep.period_to"), self.d_to)
        f.addRow(T("rec.date"), self.d_at)
        self.signer = QLabel(f"{user.name} ({uz.ROLE[user.role]})")
        f.addRow(T("rep.signer"), self.signer)
        self.lay.addWidget(g)
        btns = QGroupBox("Fayllar")
        v = QVBoxLayout(btns)
        for key, kind, ext in (("rep.amort", "schedule", "xlsx"), ("rep.reconcile", "reconcile", "xlsx"),
                               ("rep.costs", "costs", "xlsx"), ("rep.note", "note", "docx"),
                               ("rep.audit", "audit_pdf", "pdf"), ("rep.audit_xlsx", "findings", "xlsx"),
                               ("rep.audit_log", "audit_log", "xlsx"), ("rep.template", "template", "xlsx")):
            b = QPushButton(T(key))
            b.setMinimumHeight(32)
            b.setStyleSheet("text-align: left; padding-left: 12px;")
            b.setEnabled(service.can(user, "report"))
            b.clicked.connect(lambda _=False, kind=kind, ext=ext, key=key: self._run(kind, ext, key))
            v.addWidget(b)
        self.lay.addWidget(btns)
        self.lay.addStretch()

    _NAMES = {"rep.amort": "amortizatsiya_jadvali", "rep.reconcile": "BHMS_MHXS_solishtirma",
              "rep.costs": "xarajatlar_jurnali", "rep.note": "izoh_BHMS11_IAS38", "rep.audit": "audit_qomitasi",
              "rep.audit_xlsx": "istisnolar", "rep.audit_log": "audit_jurnali", "rep.template": "xarajatlar_shablon"}

    def _run(self, kind, ext, key):
        if not can(self, self.service, self.user, "report"):
            return
        path, _ = QFileDialog.getSaveFileName(self, T(key), f"{self._NAMES[key]}.{ext}", f"*.{ext}")
        if not path:
            return
        try:
            self.service.export(self.user, kind, path, as_of=self.d_at.value(), start=self.d_from.value(),
                                end=self.d_to.value(),
                                analyses=self.service.analyze_all() if kind in ("schedule", "costs") else None)
        except PermissionError as e:
            error(self, str(e))
            return
        except Exception as e:      # report generation must not crash the program
            error(self, f"{type(e).__name__}: {e}")
            return
        info(self, T("rep.saved", path=path))


# ---------------------------------------------------------------- Sozlamalar
class SettingsPage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        self.lay.addWidget(page_title(T("set.title")))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        body = QWidget(); body.setObjectName("Page")
        grid = QGridLayout(body)
        scroll.setWidget(body)
        self.lay.addWidget(scroll, 1)

        gen = QGroupBox(T("set.title"))
        gf = QFormLayout(gen)
        self.org = QLineEdit()
        self.lang = QComboBox(); self.lang.addItem("O'zbek (lotin)", "uz")
        self.amort = combo({m: T(f"amort_start.{m}") for m in AMORT_START_MODES})
        self.nas_max = QSpinBox(); self.nas_max.setRange(1, 60); self.nas_max.setSuffix(" oy")
        gf.addRow(T("set.org"), self.org)
        gf.addRow(T("set.lang"), self.lang)
        gf.addRow(T("set.amort_start"), self.amort)
        gf.addRow(T("set.nas_max"), self.nas_max)
        grid.addWidget(gen, 0, 0)

        thr = QGroupBox(T("set.thresholds"))
        tf = QFormLayout(thr)
        self.thr = {}
        for k in DEFAULT_CONTROLS:
            sp = QSpinBox(); sp.setRange(0, 2_000_000_000); sp.setGroupSeparatorShown(True)
            self.thr[k] = sp
            tf.addRow(T(f"thr.{k}"), sp)
        grid.addWidget(thr, 0, 1)

        acc = QGroupBox(T("set.accounts"))
        af = QFormLayout(acc)
        self.acc = {}
        for k in DEFAULT_ACCOUNTS:
            e = QLineEdit(); e.setMaxLength(4); e.setFixedWidth(70)
            self.acc[k] = e
            af.addRow(T(f"acc.{k}"), e)
        hint = QLabel("9410 (Sotish xarajatlari) ITTKI uchun ishlatilmaydi. 0830 — muallif taklifi, "
                      "BHMS 21 Yo'riqnomasi bilan solishtiring.")
        hint.setWordWrap(True); hint.setObjectName("Muted")
        af.addRow(hint)
        grid.addWidget(acc, 1, 0)

        cats = QGroupBox(T("set.categories") + " / " + T("set.sources"))
        cv = QVBoxLayout(cats)
        self.cat_table = QTableWidget(len(CATEGORY_ORDER), 4)
        self.cat_table.setHorizontalHeaderLabels([T("col.category"), "IAS 38", "BHMS 11", "Kt"])
        self.cat_table.verticalHeader().setVisible(False)
        self.cat_checks, self.src = {}, {}
        for i, c in enumerate(CATEGORY_ORDER):
            self.cat_table.setCellWidget(i, 0, QLabel(" " + uz.CATEGORY[c]))
            for j, fw in enumerate(FRAMEWORKS, 1):
                cb = QCheckBox(); w = QWidget(); hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0)
                hl.addWidget(cb, alignment=Qt.AlignCenter)
                self.cat_table.setCellWidget(i, j, w)
                self.cat_checks[(c, fw)] = cb
            e = QLineEdit(); e.setMaxLength(4)
            self.src[c] = e
            self.cat_table.setCellWidget(i, 3, e)
        self.cat_table.horizontalHeader().setStretchLastSection(False)
        self.cat_table.setColumnWidth(0, 300)
        self.cat_table.setColumnWidth(3, 70)
        self.cat_table.setMinimumHeight(30 * len(CATEGORY_ORDER) + 30)
        cv.addWidget(self.cat_table)
        n = QLabel("Toifalar ruxsatini o'zgartirish audit jurnaliga yoziladi (masalan, 'o'qitish' — muallif "
                   "pozitsiyasi).")
        n.setWordWrap(True); n.setObjectName("Muted")
        cv.addWidget(n)
        grid.addWidget(cats, 1, 1)

        h = QHBoxLayout()
        h.addStretch()
        self.b_save = QPushButton(T("btn.save")); self.b_save.setObjectName("Primary")
        self.b_save.clicked.connect(self._save)
        self.b_save.setEnabled(service.can(user, "settings"))
        h.addWidget(self.b_save)
        self.lay.addLayout(h)

    def refresh(self):
        s = self.service.settings
        self.org.setText(s.organization)
        self.amort.setCurrentIndex(self.amort.findData(s.engine.amort_start))
        self.nas_max.setValue(s.engine.nas_max_months)
        for k, sp in self.thr.items():
            sp.setValue(getattr(s.controls, k))
        for k, e in self.acc.items():
            e.setText(getattr(s.accounts, k))
        for (c, fw), cb in self.cat_checks.items():
            cb.setChecked(c in s.engine.categories(fw))
        for c, e in self.src.items():
            e.setText(s.accounts.source[c])

    def _save(self):
        if not can(self, self.service, self.user, "settings"):
            return
        try:
            inc = {fw: {c for c in CATEGORY_ORDER if self.cat_checks[(c, fw)].isChecked()} for fw in FRAMEWORKS}
            new = AppSettings(
                engine=Settings(self.amort.currentData(), self.nas_max.value(), inc),
                accounts=Accounts(**{k: e.text().strip() for k, e in self.acc.items()},
                                  source={c: e.text().strip() for c, e in self.src.items()}),
                controls=ControlSettings(**{k: sp.value() for k, sp in self.thr.items()}),
                organization=self.org.text().strip(), language=self.lang.currentData())
            changed = self.service.save_settings(self.user, new)
        except PermissionError as e:
            error(self, str(e))
            return
        except (AssertionError, ValueError, TypeError) as e:
            error(self, T("set.invalid", error=e))
            return
        info(self, T("set.saved") + (f" ({len(changed)})" if changed else ""))
        self.changed.emit()


# ---------------------------------------------------------------- Audit jurnali
class AuditPage(Page):
    def __init__(self, service, user, parent=None):
        super().__init__(service, user, parent)
        self.lay.addWidget(page_title(T("nav.audit")))
        n = QLabel("Har bir o'zgarish: kim (F.I.Sh., rol), qachon, nima edi → nima bo'ldi. Yozuvlarni o'chirib "
                   "yoki tahrirlab bo'lmaydi.")
        n.setObjectName("Muted")
        self.lay.addWidget(n)
        h = QHBoxLayout()
        tz = QLabel("Vaqt Toshkent vaqtida (UTC+5) ko'rsatiladi; bazada UTC saqlanadi.")
        tz.setObjectName("Muted")
        h.addWidget(tz)
        h.addStretch()
        self.b_export = QPushButton(T("btn.export"))
        self.b_export.setEnabled(service.can(user, "report"))
        self.b_export.clicked.connect(self._export)
        h.addWidget(self.b_export)
        self.lay.addLayout(h)
        self.table = make_table([T("col.when"), T("col.who"), T("col.role"), T("col.action"), T("col.object"),
                                 T("col.before"), T("col.after")], stretch=6)
        self.lay.addWidget(self.table, 1)

    def refresh(self):
        import json
        rows = []
        for r in reversed(self.repo.audit_log()):
            def j(v):
                s = json.dumps(v, ensure_ascii=False) if v is not None else ""
                return s if len(s) < 160 else s[:157] + "..."
            rows.append([clock.fmt_tashkent(r.at), r.actor, uz.ROLE.get(r.role, r.role), r.action,
                         f"{r.entity} #{r.entity_id}" if r.entity_id is not None else r.entity, j(r.before),
                         j(r.after)])
        fill_table(self.table, rows)

    def _export(self):
        if not can(self, self.service, self.user, "report"):
            return
        path, _ = QFileDialog.getSaveFileName(self, T("rep.audit_log"), "audit_jurnali.xlsx", "*.xlsx")
        if path:
            self.service.export(self.user, "audit_log", path)
            info(self, T("rep.saved", path=path))
