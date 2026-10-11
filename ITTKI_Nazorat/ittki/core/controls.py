"""M10. Control exceptions E1–E10 (pure functions, no UI)."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from . import engine
from .defaults import DEFAULT_CONTROLS
from ..i18n import uz

LEVELS = {"E1": "high", "E2": "medium", "E3": "high", "E4": "medium", "E5": "high",
          "E6": "medium", "E7": "info", "E8": "high", "E9": "info", "E10": "medium"}
_LEVEL_ORDER = {"high": 0, "medium": 1, "info": 2}


@dataclass
class ControlSettings:
    e2_days: int = DEFAULT_CONTROLS["e2_days"]
    e3_days: int = DEFAULT_CONTROLS["e3_days"]
    e4_pct: int = DEFAULT_CONTROLS["e4_pct"]
    e6_days: int = DEFAULT_CONTROLS["e6_days"]
    e9_amount: int = DEFAULT_CONTROLS["e9_amount"]
    e10_months: int = DEFAULT_CONTROLS["e10_months"]

    def __post_init__(self):
        for k, v in vars(self).items():
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(f"{k} must be a non-negative integer, got {v!r}")


@dataclass(frozen=True)
class Finding:
    code: str
    project: str
    message: str
    on: Optional[date] = None
    framework: Optional[str] = None

    @property
    def level(self) -> str:
        return LEVELS[self.code]


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _f(code, p, on=None, framework=None, **kw):
    return Finding(code, p.name, uz.CONTROL_MSG[code].format(**kw), on, framework)


def _closed(p: engine.Project, as_of: date) -> bool:
    """Finished (available for use) or abandoned on or before `as_of`."""
    return bool((p.available_for_use and p.available_for_use <= as_of)
                or (p.abandoned_on and p.abandoned_on <= as_of))


def check_project(p: engine.Project, as_of: date, s: engine.Settings = engine.Settings(),
                  ctl: ControlSettings = None, budget: Optional[int] = None,
                  start_date: Optional[date] = None) -> list[Finding]:
    ctl = ctl or ControlSettings()
    out: list[Finding] = []
    asm = sorted(p.assessments, key=lambda a: a.on)       # stable: same-day order preserved
    asm_now = [a for a in asm if a.on <= as_of]
    rnd = p.scope == "rnd"
    res = {fw: engine.evaluate(p, fw, s, as_of=as_of) for fw in engine.FRAMEWORKS}

    if rnd:
        # E1 — 'Ha' without evidence
        for a in asm:
            for k in engine.CRITERIA:
                if a.answers.get(k) == "yes" and not a.evidence.get(k):
                    out.append(_f("E1", p, a.on, date=uz.fdate(a.on), criterion=uz.CRITERION[k]))

        # E2 — in development, costs expensed (status != met) for longer than N days
        if p.development_start and p.development_start <= as_of and not _closed(p, as_of):
            for fw in engine.FRAMEWORKS:
                since: Optional[date] = date.min
                for a in asm_now:
                    st, _ = engine._assessment_status(a, fw)
                    if st == "met":
                        since = None
                    elif since is None:
                        since = a.on
                if since is None:
                    continue
                since = max(since, p.development_start)
                days = (as_of - since).days
                r6 = [r for r in res[fw]["rows"] if r["reason"].startswith("R6") and since <= r["date"] <= as_of]
                if days > ctl.e2_days and r6:
                    out.append(_f("E2", p, since, fw, fw=uz.FW[fw], since=uz.fdate(since), days=days))

        # E3 — no assessment within N days after the move to development
        if p.development_start:
            deadline = p.development_start + timedelta(days=ctl.e3_days)
            if as_of > deadline and not any(a.on <= deadline for a in asm):
                out.append(_f("E3", p, deadline, start=uz.fdate(p.development_start), days=ctl.e3_days))

    # E4 — costs exceed budget by more than N %
    total = sum(c.amount for c in p.costs if c.on <= as_of)
    if budget and total * 100 > budget * (100 + ctl.e4_pct):
        pct = (total - budget) * 100 // budget
        out.append(_f("E4", p, as_of, total=uz.money(total), budget=uz.money(budget), pct=pct))

    if rnd:
        # E5 — IAS 36.10(a) annual test (rule is in the engine; reported here)
        for w in res["IAS38"]["warnings"]:
            m = re.match(r"E5: (\d{4})", w)
            if m:
                y = int(m.group(1))
                out.append(_f("E5", p, date(y, 12, 31), "IAS38", year=y))

        # E6 — 'expert' answer pending for more than N days (latest assessment as of as_of)
        if asm_now and not _closed(p, as_of):
            last = asm_now[-1]
            for k in engine.CRITERIA:
                if last.answers.get(k) != "expert":
                    continue
                since = last.on
                for a in reversed(asm_now):
                    if a.answers.get(k) != "expert":
                        break
                    since = a.on
                days = (as_of - since).days
                if days > ctl.e6_days:
                    out.append(_f("E6", p, since, criterion=uz.CRITERION[k], since=uz.fdate(since), days=days))

        # E7 — non-admissible category, expensed automatically
        for c in sorted(p.costs, key=lambda c: c.on):
            fws = [fw for fw in engine.FRAMEWORKS if c.category not in s.categories(fw)]
            if fws:
                out.append(_f("E7", p, c.on, fws[0] if len(fws) == 1 else None, date=uz.fdate(c.on),
                              category=uz.CATEGORY[c.category], amount=uz.money(c.amount),
                              fw=", ".join(uz.FW[x] for x in fws)))

    # E8 — available for use without useful life
    if p.available_for_use and not p.useful_life_months:
        out.append(_f("E8", p, p.available_for_use, date=uz.fdate(p.available_for_use)))

    # E9 — NAS/IFRS difference above threshold
    if rnd:
        r = engine.reconcile(p, as_of, s)
        if abs(r["difference"]) > ctl.e9_amount:
            out.append(_f("E9", p, as_of, date=uz.fdate(as_of), diff=uz.money(r["difference"]),
                          ias=uz.money(r["IAS38_carrying"]), nas=uz.money(r["NAS11_carrying"])))

    # E10 — no costs and no assessments for more than N months, project still open
    if not _closed(p, as_of):
        dates = [c.on for c in p.costs if c.on <= as_of] + [a.on for a in asm_now]
        dates += [d for d in (p.development_start, start_date) if d and d <= as_of]
        if dates:
            last = max(dates)
            if as_of > add_months(last, ctl.e10_months):
                out.append(_f("E10", p, last, last=uz.fdate(last), months=ctl.e10_months))

    return sorted(out, key=lambda f: (_LEVEL_ORDER[f.level], int(f.code[1:]), f.on or date.min))
