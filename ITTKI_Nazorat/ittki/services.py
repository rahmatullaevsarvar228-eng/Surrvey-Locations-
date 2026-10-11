"""Application services: combine repository + engine + journal + controls. No UI imports;
used by the PySide6 windows and by the report generators."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

from .core import engine, journal as jr
from .core.appsettings import AppSettings
from .core.controls import Finding, check_project
from .core.rules import rule_code
from .db.repository import ProjectRecord, Repository
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


class Service:
    def __init__(self, repo: Repository, today: Callable[[], date] = date.today):
        self.repo = repo
        self._today = today

    def today(self) -> date:
        return self._today()

    @property
    def settings(self) -> AppSettings:
        return self.repo.settings()

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
