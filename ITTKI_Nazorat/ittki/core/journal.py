"""M6. Journal entries derived from an engine result. Nothing here is stored: entries are
recomputed from `evaluate()` / `schedule()` every time (TZ section 5).

All account codes come from `Accounts` (M12 settings); defaults are in `defaults.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from . import engine
from .defaults import DEFAULT_ACCOUNTS, DEFAULT_SOURCE_ACCOUNTS, FORBIDDEN_ACCOUNTS

# Operation codes (labels are in ittki.i18n.uz.JOURNAL_OPS)
OP_EXPENSE = "expense"                  # cost expensed
OP_CAPITALIZE = "capitalize"            # cost capitalized
OP_NAS_WRITEOFF = "nas_writeoff"        # BHMS 11, 18-band (criteria became 'no')
OP_PRE_IMPAIRMENT = "pre_impairment"    # impairment before available for use
OP_ABANDON_WRITEOFF = "abandon_writeoff"  # abandonment before available for use
OP_TRANSFER = "transfer"                # asset available for use: 0830 -> 0490
OP_AMORTIZATION = "amortization"
OP_IMPAIRMENT = "impairment"            # impairment of an asset available for use
OP_DISPOSAL_ACCUM = "disposal_accum"    # abandonment after availability: accumulated part
OP_DISPOSAL_RESIDUAL = "disposal_residual"  # abandonment after availability: carrying amount

_CODE = re.compile(r"^\d{4}$")


@dataclass
class Accounts:
    expense: str = DEFAULT_ACCOUNTS["expense"]
    capitalize: str = DEFAULT_ACCOUNTS["capitalize"]
    asset: str = DEFAULT_ACCOUNTS["asset"]
    accumulated: str = DEFAULT_ACCOUNTS["accumulated"]
    amortization_debit: str = DEFAULT_ACCOUNTS["amortization_debit"]
    writeoff: str = DEFAULT_ACCOUNTS["writeoff"]
    source: dict = field(default_factory=lambda: dict(DEFAULT_SOURCE_ACCOUNTS))

    def __post_init__(self):
        codes = {k: getattr(self, k) for k in DEFAULT_ACCOUNTS}
        codes.update({f"source.{k}": v for k, v in self.source.items()})
        missing = set(engine.ALL_CATEGORIES) - set(self.source)
        if missing:
            raise ValueError(f"source account missing for: {sorted(missing)}")
        for k, v in codes.items():
            if not isinstance(v, str) or not _CODE.match(v):
                raise ValueError(f"{k}: account code must be 4 digits, got {v!r}")
            if v in FORBIDDEN_ACCOUNTS:
                raise ValueError(f"{k}: account {v} must not be used for R&D (9410 = Sotish xarajatlari)")

    def all_codes(self) -> set:
        return {getattr(self, k) for k in DEFAULT_ACCOUNTS} | set(self.source.values())


@dataclass(frozen=True)
class Entry:
    on: date
    debit: str
    credit: str
    amount: int
    op: str
    framework: str
    reason: str = ""
    category: Optional[str] = None


def journal(res: dict, p: engine.Project, s: engine.Settings = engine.Settings(),
            acc: Accounts = None) -> list[Entry]:
    """Entries for one framework, sorted by date (stable: costs before period-end postings)."""
    acc = acc or Accounts()
    fw = res["framework"]
    out: list[Entry] = []

    def add(on, dt, kt, amount, op, reason="", category=None):
        if amount > 0:
            out.append(Entry(on, dt, kt, amount, op, fw, reason, category))

    if res["decision"] == "STANDART QO'LLANILMAYDI":
        return out   # R0: costs are not classified by this program

    # 1. every cost row (R1–R8)
    for r in res["rows"]:
        src = acc.source[r["category"]]
        if r["treatment"] == "capitalize":
            add(r["date"], acc.capitalize, src, r["amount"], OP_CAPITALIZE, r["reason"], r["category"])
        else:
            add(r["date"], acc.expense, src, r["amount"], OP_EXPENSE, r["reason"], r["category"])

    ready = p.available_for_use
    abandoned = p.abandoned_on
    transferred = bool(ready and (not abandoned or ready <= abandoned))

    # 2. BHMS 11, 18-band write-offs. The engine removes them from the amortizable base from the
    #    start, so one dated on/after availability is posted on the availability date (from 0830).
    #    One dated on/after abandonment is not posted: the abandonment write-off already
    #    derecognised the whole balance (the engine reports both — see docs/doubts.md).
    for wd, amt in res["nas_writeoff_rows"]:
        if abandoned and wd >= abandoned:
            continue
        on = min(wd, ready) if transferred else wd
        add(on, acc.writeoff, acc.capitalize, amt, OP_NAS_WRITEOFF, "BHMS 11, 18-band")

    # 3. impairment before availability (IAS 36.10(a), 36.59; BHMS 11, 18-band)
    pre = engine._pre_availability_impairment(res, p)
    if pre:
        add(p.impairment_event[0], acc.writeoff, acc.capitalize, pre, OP_PRE_IMPAIRMENT,
            "IAS 36.59 / BHMS 11, 18-band")

    base = res["capitalized"] - res["nas_criteria_writeoff"] - pre
    if not transferred:
        # 4. abandonment before availability: the whole capitalized balance is written off
        if abandoned:
            add(abandoned, acc.writeoff, acc.capitalize, res["writeoff"], OP_ABANDON_WRITEOFF,
                "IAS 38.112-113 / BHMS 11, 18-band")
        return _sorted(out)

    # 5. available for use: 0830 -> 0490
    add(ready, acc.asset, acc.capitalize, base, OP_TRANSFER, "IAS 38.97 / BHMS 11, 15-band")

    # 6. amortization and impairment after availability
    accumulated = 0
    for row in engine.schedule(res, p, s):
        add(row["period_end"], acc.amortization_debit, acc.accumulated, row["amortization"], OP_AMORTIZATION,
            "IAS 38.97 / BHMS 11, 15-16-band")
        add(row["period_end"], acc.writeoff, acc.accumulated, row["impairment"], OP_IMPAIRMENT,
            "IAS 36.59, 36.63 / BHMS 11, 18-band")
        accumulated += row["amortization"] + row["impairment"]

    # 7. abandonment after availability: derecognition (IAS 38.112-113)
    if abandoned and base > 0:
        add(abandoned, acc.accumulated, acc.asset, accumulated, OP_DISPOSAL_ACCUM, "IAS 38.112-113")
        add(abandoned, acc.writeoff, acc.asset, base - accumulated, OP_DISPOSAL_RESIDUAL, "IAS 38.112-113")
    return _sorted(out)


def _sorted(entries):
    return sorted(entries, key=lambda e: e.on)


def balance(entries: list[Entry], account: str, at: Optional[date] = None) -> int:
    """Debit minus credit on `account` up to and including `at`."""
    t = 0
    for e in entries:
        if at is not None and e.on > at:
            continue
        if e.debit == account:
            t += e.amount
        if e.credit == account:
            t -= e.amount
    return t
