"""Application services: combine repository + engine + journal + controls. No UI imports;
used by the PySide6 windows and by the report generators."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

from . import clock
from .core import engine, journal as jr
from .core.appsettings import AppSettings
from .core.controls import Finding, check_project
from .core.rules import rule_code
from .db.repository import (AssessmentRecord, CostRecord, ImpairmentTest, ProjectRecord, Repository, User)
from .permissions import PermissionDenied, allowed, enforce
from .i18n import uz

FWS = engine.FRAMEWORKS


@dataclass
class Analysis:
    record: ProjectRecord
    project: engine.Project
    as_of: date
    res: dict                  # fw -> engine.evaluate() result
    schedule: dict             # fw -> engine.schedule()
    journal: dict              # fw -> list[journal.Entry]
    carrying: dict             # fw -> carrying amount at as_of
    status: dict               # fw -> criteria status at as_of ('met' | 'no' | 'pending')
    findings: list
    reconcile: dict
    reasons: list = field(default_factory=list)
    costs: list = field(default_factory=list)       # repository CostRecord (with primary documents)

    @property
    def in_scope(self) -> bool:
        return self.project.scope == "rnd"


class DemoRefused(ValueError):
    """Demo data are loaded only into an empty database."""


REPORT_KINDS = ("schedule", "reconcile", "costs", "findings", "note", "audit_pdf", "template", "audit_log")


class Service:
    """Single entry point for every action of the interface. Each action is checked here against
    ittki.permissions (`enforce`), and refused attempts are written to the audit log."""

    def __init__(self, repo: Repository, today: Callable[[], date] = clock.today):
        self.repo = repo
        self._today = today

    def today(self) -> date:
        return self._today()

    @property
    def settings(self) -> AppSettings:
        return self.repo.settings()

    # ---- permissions ------------------------------------------------------------
    def authorize(self, user: User, action: str):
        """Raises PermissionDenied (and audits the attempt) if `user` may not do `action`."""
        enforce(self.repo, user, action)

    @staticmethod
    def can(user: User, action: str) -> bool:
        """For enabling buttons only: no audit record."""
        return allowed(user.role, action)

    def can_load_demo(self, user: User) -> bool:
        return self.can(user, "demo") and not self.repo.projects()

    # ---- actions (each one checked) ---------------------------------------------
    def save_project(self, user: User, rec: ProjectRecord) -> int:
        self.authorize(user, "project")
        return self.repo.save_project(rec, user)

    def change_stage(self, user: User, pid: int, to_stage: str, on: date, note: str = "",
                     useful_life_months: Optional[int] = None) -> ProjectRecord:
        self.authorize(user, "stage")
        if useful_life_months is not None:
            rec = self.repo.project(pid)
            if rec.useful_life_months != useful_life_months:
                rec.useful_life_months = useful_life_months
                self.repo.save_project(rec, user)
        return self.repo.change_stage(pid, to_stage, on, user, note)

    def add_assessment(self, user: User, a: AssessmentRecord) -> int:
        self.authorize(user, "assessment")
        return self.repo.add_assessment(a, user)

    def add_cost(self, user: User, c: CostRecord) -> int:
        self.authorize(user, "cost")
        return self.repo.add_cost(c, user)

    def update_cost(self, user: User, c: CostRecord):
        self.authorize(user, "cost")
        return self.repo.update_cost(c, user)

    def delete_cost(self, user: User, cost_id: int):
        self.authorize(user, "cost")
        return self.repo.delete_cost(cost_id, user)

    def read_import(self, user: User, pid: int, path) -> tuple[list, list]:
        """Parse an import file (checked: 'import'). Returns (records, errors)."""
        self.authorize(user, "import")
        from .reports.excel_import import read_costs
        return read_costs(path, pid)

    def import_costs(self, user: User, records: list) -> int:
        self.authorize(user, "import")
        return self.repo.add_costs(records, user)

    def set_impairment_event(self, user: User, pid: int, on: Optional[date], recoverable: Optional[int]):
        self.authorize(user, "impairment")
        return self.repo.set_impairment_event(pid, on, recoverable, user)

    def add_impairment_test(self, user: User, t: ImpairmentTest) -> int:
        self.authorize(user, "impairment")
        return self.repo.add_impairment_test(t, user)

    def delete_impairment_test(self, user: User, test_id: int):
        self.authorize(user, "impairment")
        return self.repo.delete_impairment_test(test_id, user)

    def save_settings(self, user: User, new: AppSettings) -> list[str]:
        self.authorize(user, "settings")
        return self.repo.save_settings(new, user)

    def load_demo(self, user: User) -> int:
        self.authorize(user, "demo")
        if self.repo.projects():
            raise DemoRefused(uz.t("home.demo_not_empty"))
        from .demo import load_demo
        n = load_demo(self.repo)
        with self.repo._tx():
            self.repo._audit(user, "create", "demo", None, None, {"projects": n})
        return n

    def backup(self, user: User, path) -> None:
        self.authorize(user, "backup")
        self.repo.backup(path)

    def export(self, user: User, kind: str, path, as_of: Optional[date] = None, start: Optional[date] = None,
               end: Optional[date] = None, analyses: Optional[list] = None) -> None:
        """All reports and exports. `analyses` limits the report to given projects (e.g. one card)."""
        self.authorize(user, "report")
        from .reports import excel, excel_import, pdf, word
        st = self.settings
        at = as_of or self.today()
        if kind == "template":
            return excel_import.write_template(path)
        if kind == "audit_log":
            return excel.export_audit_log(self.repo.audit_log(), path, st)
        if kind == "note":
            return word.export_note(analyses or self.analyze_all(end), path, st, start, end)
        an = analyses or self.analyze_all(at)
        if kind == "schedule":
            return excel.export_schedule(an, path, st)
        if kind == "reconcile":
            return excel.export_reconcile(an, path, st)
        if kind == "costs":
            return excel.export_costs(an, path, st)
        if kind == "findings":
            return excel.export_findings(an, path, st, user, at)
        if kind == "audit_pdf":
            return pdf.export_audit_report(an, path, st, user, at)
        raise ValueError(kind)

    # ---- analysis ---------------------------------------------------------
    def analyze(self, pid: int, as_of: Optional[date] = None, settings: Optional[AppSettings] = None) -> Analysis:
        st = settings or self.settings
        as_of = as_of or self.today()
        rec = self.repo.project(pid)
        p = self.repo.engine_project(pid)
        s = st.engine
        res = {fw: engine.evaluate(p, fw, s, as_of=as_of) for fw in FWS}
        sch = {fw: engine.schedule(res[fw], p, s) for fw in FWS}
        jn = {fw: jr.journal(res[fw], p, s, st.accounts) for fw in FWS}
        car = {fw: engine.carrying_amount(res[fw], p, as_of, s) for fw in FWS}
        status = {fw: engine.status_on(p, fw, as_of) for fw in FWS}
        findings = check_project(p, as_of, s, st.controls, budget=rec.budget, start_date=rec.start_date)
        rec_ = engine.reconcile(p, as_of, s)
        a = Analysis(rec, p, as_of, res, sch, jn, car, status, findings, rec_)
        a.reasons = reconcile_reasons(a)
        a.costs = self.repo.costs(pid)
        return a

    def analyze_all(self, as_of: Optional[date] = None) -> list[Analysis]:
        st = self.settings
        return [self.analyze(r.id, as_of, st) for r in self.repo.projects()]

    def findings_all(self, as_of: Optional[date] = None) -> list[tuple[ProjectRecord, Finding]]:
        return [(a.record, f) for a in self.analyze_all(as_of) for f in a.findings]

    def totals(self, analyses: list[Analysis]) -> dict:
        t = {"projects": len(analyses)}
        for fw in FWS:
            t[f"capitalized.{fw}"] = sum(a.res[fw]["capitalized"] for a in analyses)
            t[f"expensed.{fw}"] = sum(a.res[fw]["expensed"] for a in analyses)
            t[f"carrying.{fw}"] = sum(a.carrying[fw] for a in analyses)
        f = [x for a in analyses for x in a.findings]
        t["findings"] = len(f)
        for lv in ("high", "medium", "info"):
            t[f"findings.{lv}"] = sum(1 for x in f if x.level == lv)
        return t


# ---------------------------------------------------------------- M8 reasons
def reconcile_reasons(a: Analysis) -> list[str]:
    R = uz.REC_REASON
    if not a.in_scope:
        return [R["scope"]]
    ias, nas = a.res["IAS38"], a.res["NAS11"]
    out = []
    # K3 is the only criterion IAS 38 requires and BHMS 11 does not
    if ias["capitalized"] < nas["capitalized"]:
        if any(x.answers.get("K3_ability_use_or_sell") != "yes" for x in a.project.assessments):
            out.append(R["k3"])
    rows_i = _rows_by_cost(ias)
    rows_n = _rows_by_cost(nas)
    for key in sorted(set(rows_i) | set(rows_n)):
        ti, tn = rows_i.get(key, []), rows_n.get(key, [])
        if _summ(ti) != _summ(tn):
            d, cat, amount = key
            out.append(R["row"].format(date=uz.fdate(d), category=uz.CATEGORY[cat], amount=uz.money(amount),
                                       ias=_desc(ti), nas=_desc(tn)))
    if nas["nas_criteria_writeoff"]:
        out.append(R["nas_writeoff"].format(amount=uz.money(nas["nas_criteria_writeoff"])))
    r8 = sum(r["amount"] for r in nas["rows"] if rule_code(r["reason"]) == "R8")
    if r8:
        out.append(R["limit"].format(amount=uz.money(r8)))
    if ias["amort_months"] != nas["amort_months"] and ias["amort_months"] and nas["amort_months"]:
        out.append(R["months"].format(ias=ias["amort_months"], nas=nas["amort_months"]))
    return out or [R["none"]]


def _rows_by_cost(res):
    """Group decision rows by (date, category, total amount); R8 splits one cost into two rows."""
    out = {}
    for r in res["rows"]:
        out.setdefault((r["date"], r["category"]), []).append(r)
    return {(d, cat, sum(x["amount"] for x in rows)): rows for (d, cat), rows in out.items()}


def _summ(rows):
    return sorted((r["treatment"], r["amount"]) for r in rows)


def _desc(rows):
    return "; ".join(f"{uz.TREATMENT[r['treatment']].lower()} {uz.money(r['amount'])} ({rule_code(r['reason'])})"
                     for r in rows)


# ---------------------------------------------------------------- M9 movement
MOVEMENT_KEYS = ("wip_open", "capitalized", "wip_writeoff", "transfer", "wip_close",
                 "gross_open", "gross_close", "accum_open", "amortization", "impairment", "disposal_accum",
                 "accum_close", "disposal_gross", "restored", "expensed_rnd", "expensed_other")


def movement(a: Analysis, fw: str, start: date, end: date, acc: jr.Accounts) -> dict:
    """Roll-forward of capitalized R&D for [start, end] (BHMS 11, 20-band; IAS 38.118), from journal entries."""
    e = a.journal[fw]
    before = start - timedelta(days=1)
    inside = [x for x in e if start <= x.on <= end]

    def s(op):
        return sum(x.amount for x in inside if x.op == op)

    m = dict.fromkeys(MOVEMENT_KEYS, 0)
    m["wip_open"] = jr.balance(e, acc.capitalize, before)
    m["wip_close"] = jr.balance(e, acc.capitalize, end)
    m["capitalized"] = s(jr.OP_CAPITALIZE)
    m["wip_writeoff"] = s(jr.OP_NAS_WRITEOFF) + s(jr.OP_PRE_IMPAIRMENT) + s(jr.OP_ABANDON_WRITEOFF)
    m["transfer"] = s(jr.OP_TRANSFER)
    m["gross_open"] = jr.balance(e, acc.asset, before)
    m["gross_close"] = jr.balance(e, acc.asset, end)
    m["accum_open"] = -jr.balance(e, acc.accumulated, before)
    m["accum_close"] = -jr.balance(e, acc.accumulated, end)
    m["amortization"] = s(jr.OP_AMORTIZATION)
    m["impairment"] = s(jr.OP_IMPAIRMENT)
    m["disposal_accum"] = s(jr.OP_DISPOSAL_ACCUM)
    m["disposal_gross"] = s(jr.OP_DISPOSAL_ACCUM) + s(jr.OP_DISPOSAL_RESIDUAL)
    m["disposal_residual"] = s(jr.OP_DISPOSAL_RESIDUAL)
    exp = [x for x in inside if x.op == jr.OP_EXPENSE]
    m["expensed_rnd"] = sum(x.amount for x in exp if rule_code(x.reason) != "R1")
    m["expensed_other"] = sum(x.amount for x in exp if rule_code(x.reason) == "R1")
    m["carrying_open"] = m["wip_open"] + m["gross_open"] - m["accum_open"]
    m["carrying_close"] = m["wip_close"] + m["gross_close"] - m["accum_close"]
    return m


def movement_total(analyses: list[Analysis], fw: str, start: date, end: date, acc: jr.Accounts) -> dict:
    tot: dict = {}
    for a in analyses:
        if not a.in_scope:
            continue
        for k, v in movement(a, fw, start, end, acc).items():
            tot[k] = tot.get(k, 0) + v
    return tot or {k: 0 for k in MOVEMENT_KEYS + ("disposal_residual", "carrying_open", "carrying_close")}


def cost_rows(a: Analysis, fw: str) -> list[list[dict]]:
    """Decision rows of each cost, aligned with repository order (costs sorted by date, then id —
    the same stable order the engine uses). R8 may split one cost into a capitalized and an expensed row."""
    rows = list(a.res[fw]["rows"])
    out, i = [], 0
    for c in sorted(a.project.costs, key=lambda c: c.on):
        if i >= len(rows):
            out.append([])
            continue
        got = [rows[i]]
        i += 1
        if got[0]["amount"] < c.amount and i < len(rows) and rows[i]["date"] == c.on:
            got.append(rows[i])
            i += 1
        out.append(got)
    return out
