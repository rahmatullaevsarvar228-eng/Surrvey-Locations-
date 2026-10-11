"""
ITTKI (R&D) capitalization decision engine — reference implementation v3.
Pure Python, no UI. Evaluates one project under two frameworks:
  IAS38 — IAS 38 Intangible Assets (+ IAS 36 Impairment of Assets)
  NAS11 — BHMS No.11 (2024) "Ilmiy-tadqiqot va tajriba-konstruktorlik ishlari bo'yicha
          xarajatlar" (MEF order No.137 of 14.06.2024, MoJ reg. No.3535 of 25.07.2024)
Money: int (so'm). Dates: datetime.date.
"""
from __future__ import annotations
import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

FRAMEWORKS = ("IAS38", "NAS11")

# ------------------------------------------------------------------ criteria
CRITERIA = {
    "K1_technical_feasibility": {"IAS38": "IAS 38.57(a)", "NAS11": "BHMS 11, 12-band (2)"},
    "K2_intention":             {"IAS38": "IAS 38.57(b)", "NAS11": "BHMS 11, 12-band (3)"},
    "K3_ability_use_or_sell":   {"IAS38": "IAS 38.57(c)", "NAS11": None},  # no separate NAS criterion
    "K4_future_benefits":       {"IAS38": "IAS 38.57(d)", "NAS11": "BHMS 11, 12-band (4)"},
    "K5_adequate_resources":    {"IAS38": "IAS 38.57(e)", "NAS11": "BHMS 11, 12-band (5)"},
    "K6_reliable_measurement":  {"IAS38": "IAS 38.57(f)", "NAS11": "BHMS 11, 12-band (1)"},
    "K7_clearly_defined":       {"IAS38": "IAS 38.12",    "NAS11": "BHMS 11, 12-band (1)"},
}
def required(fw: str) -> list[str]:
    return [k for k, v in CRITERIA.items() if v[fw] is not None]

# ------------------------------------------------------------------ cost categories
INCLUDED = {
    # IAS 38.66 (directly attributable); 38.67 excludes selling, admin and general overhead
    # (unless directly attributable), inefficiencies/initial operating losses, training
    "IAS38": {"salary", "materials", "services", "depreciation", "direct_overhead",
              "patent_amortization", "legal_registration"},
    # BHMS 11, 7-band (all costs directly related or attributable to R&D) and 8-band list
    # (a) staff pay, (b) materials and services, (c) depreciation of fixed assets used,
    # (d) directly related overheads, (e) other costs e.g. patent/licence amortization.
    # 9-band excludes realization (selling) costs. Training of staff to operate the asset is
    # treated as not attributable (author's reading, aligned with IAS 38.67(c)).
    "NAS11": {"salary", "materials", "services", "depreciation", "direct_overhead",
              "patent_amortization", "legal_registration"},
}
ALL_CATEGORIES = INCLUDED["IAS38"] | {"selling", "general_admin", "training", "other"}

SCOPES = {"rnd", "mineral_exploration", "contract_for_customer"}

# ------------------------------------------------------------------ data model
@dataclass
class Assessment:
    on: date
    answers: dict                      # key -> "yes" | "no" | "expert"
    evidence: dict = field(default_factory=dict)   # key -> document reference; required for "yes"

@dataclass
class Cost:
    on: date
    amount: int
    category: str
    note: str = ""

@dataclass
class Project:
    name: str
    phases_separable: bool                    # IAS 38.53
    development_start: Optional[date]         # None = never left research
    available_for_use: Optional[date]         # acceptance act date
    abandoned_on: Optional[date]
    useful_life_months: int
    assessments: list
    costs: list
    scope: str = "rnd"
    impairment_event: Optional[tuple] = None  # (date, recoverable_amount)
    expected_net_benefit: Optional[int] = None  # BHMS 11, 13-band limit (future benefits less future costs)
    impairment_test_dates: list = field(default_factory=list)

@dataclass
class Settings:
    amort_start: str = "auto"   # auto: same month if available on day 1, else next month
                                # | "same_month" | "next_month"
    nas_max_months: int = 60    # BHMS 11, 16-band: shorter of useful life and 5 years

    def __post_init__(self):
        assert self.amort_start in ("auto", "same_month", "next_month"), self.amort_start
        assert 1 <= self.nas_max_months <= 60, self.nas_max_months

def month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])

# ------------------------------------------------------------------ criteria status over time
def _assessment_status(a: Assessment, fw: str):
    """Returns ('met'|'no'|'pending', list_of_warnings)."""
    w, status = [], "met"
    for k in required(fw):
        ans = a.answers.get(k)
        if ans == "no":
            return "no", w
        if ans != "yes":
            status = "pending"
            continue
        if not a.evidence.get(k):
            w.append(f"E1 {a.on}: {k} = 'Ha', lekin dalil hujjati yo'q — bajarilmagan deb hisoblandi")
            status = "pending"
    return status, w

def status_on(p: Project, fw: str, d: date):
    st = "pending"
    for a in sorted(p.assessments, key=lambda x: x.on):
        if a.on <= d:
            st, _ = _assessment_status(a, fw)
    return st

# ------------------------------------------------------------------ evaluation
def evaluate(p: Project, fw: str, s: Settings = Settings(), as_of: Optional[date] = None) -> dict:
    assert fw in FRAMEWORKS and p.scope in SCOPES
    warnings: list[str] = []
    if p.scope != "rnd":
        ref = {"mineral_exploration": {"IAS38": "IAS 38.2(c)-(d), IFRS 6", "NAS11": "BHMS 11, 4-band"},
               "contract_for_customer": {"IAS38": "IFRS 15 / IAS 2", "NAS11": "BHMS 11, 5-band (BHMS 4, 17)"}}[p.scope][fw]
        return {"framework": fw, "decision": "STANDART QO'LLANILMAYDI", "out_of_scope_ref": ref,
                "capitalized": 0, "expensed": 0, "writeoff": 0, "nas_criteria_writeoff": 0, "nas_writeoff_rows": [],
                "amort_months": 0, "rows": [], "warnings": [f"Loyiha {ref} bo'yicha hisobga olinadi"],
                "first_met_on": None, "cap_rows": []}

    for a in p.assessments:
        warnings += _assessment_status(a, fw)[1]
    if not p.phases_separable:
        warnings.append("Tadqiqot va ishlanma bosqichlarini ajratib bo'lmaydi — barcha xarajatlar tadqiqot xarajati "
                        + ("(IAS 38.53)" if fw == "IAS38" else "(BHMS 11 da tartibga solinmagan; ehtiyotkorlik tamoyili)"))

    # status transitions (revocation)
    nas_writeoffs = []        # (date, amount) — BHMS 11, 18-band
    prev = "pending"
    for a in sorted(p.assessments, key=lambda x: x.on):
        st, _ = _assessment_status(a, fw)
        if prev == "met" and st != "met":
            if fw == "IAS38":
                warnings.append(f"{a.on}: mezonlar endi bajarilmayapti — keyingi xarajatlar xarajatga; "
                                "kapitallashtirilgan qoldiq qadrsizlanishga tekshirilsin (IAS 36.9, 36.12)")
            elif st == "no":
                nas_writeoffs.append(a.on)
            else:
                warnings.append(f"{a.on}: mezon 'Ekspert bahosi' holatida — kapitallashtirish to'xtatildi")
        prev = st

    rows, cap_rows = [], []
    exp = 0
    for c in sorted(p.costs, key=lambda x: x.on):
        assert c.category in ALL_CATEGORIES, c.category
        assert isinstance(c.amount, int) and c.amount >= 0
        if c.category not in INCLUDED[fw]:
            t, why = "expense", f"R1: '{c.category}' toifasi aktiv qiymatiga kiritilmaydi"
        elif not p.phases_separable:
            t, why = "expense", "R2: bosqichlar ajratilmagan"
        elif p.development_start is None or c.on < p.development_start:
            t, why = "expense", "R3: tadqiqot bosqichi (IAS 38.54 / BHMS 11, 10-band)"
        elif p.abandoned_on and c.on >= p.abandoned_on:
            t, why = "expense", "R4: loyiha to'xtatilgan"
        elif p.available_for_use and c.on >= p.available_for_use:
            t, why = "expense", "R5: aktiv foydalanishga tayyor bo'lgandan keyingi xarajat (IAS 38.66, 38.20)"
        elif status_on(p, fw, c.on) != "met":
            t, why = "expense", "R6: shu sanada mezonlar bajarilmagan; keyin kapitallashtirilmaydi (IAS 38.65, 38.71 / BHMS 11, 11-band)"
        elif (fw == "NAS11" and p.expected_net_benefit is not None
              and sum(a for _, a in cap_rows) + c.amount > p.expected_net_benefit):
            room = max(p.expected_net_benefit - sum(a for _, a in cap_rows), 0)
            if room:   # split: part up to the limit is capitalized, the rest expensed
                cap_rows.append((c.on, room))
                rows.append({"date": c.on, "amount": room, "category": c.category, "treatment": "capitalize",
                             "reason": "R7: barcha mezonlar bajarilgan (BHMS 11, 12-band) — 13-band chegarasigacha"})
            t, why = "expense", "R8: BHMS 11, 13-band — kelgusi iqtisodiy nafdan oshgan qism"
            rows.append({"date": c.on, "amount": c.amount - room, "category": c.category, "treatment": t, "reason": why})
            exp += c.amount - room
            continue
        else:
            t, why = "capitalize", "R7: barcha mezonlar bajarilgan (IAS 38.57 / BHMS 11, 12-band)"
        rows.append({"date": c.on, "amount": c.amount, "category": c.category, "treatment": t, "reason": why})
        if t == "capitalize":
            cap_rows.append((c.on, c.amount))
        else:
            exp += c.amount
    cap = sum(a for _, a in cap_rows)

    # BHMS 11, 18-band: criteria explicitly failed ('no') -> capitalized balance written off
    nas_wo, nas_wo_rows = 0, []
    for wd in nas_writeoffs:
        amt = sum(a for d, a in cap_rows if d < wd) - nas_wo
        if amt > 0:
            nas_wo += amt
            nas_wo_rows.append((wd, amt))
            warnings.append(f"{wd}: mezon 'Yo'q' — kapitallashtirilgan {amt:,} so'm hisobdan chiqarildi (BHMS 11, 18-band)")

    if fw == "IAS38" and p.expected_net_benefit is not None and cap > p.expected_net_benefit:
        warnings.append("Kapitallashtirilgan summa kutilayotgan sof nafdan oshadi — qadrsizlanish belgisi (IAS 36.12)")

    months = 0
    if p.available_for_use and cap - nas_wo > 0:
        months = p.useful_life_months if fw == "IAS38" else min(p.useful_life_months, s.nas_max_months)
        if not p.useful_life_months:
            warnings.append("E8: foydali xizmat muddati ko'rsatilmagan")

    # IAS 36.10(a): annual test for intangible not yet available for use
    if fw == "IAS38" and cap_rows:
        last = as_of or max([c.on for c in p.costs] + [d for d in [p.available_for_use, p.abandoned_on] if d])
        test_years = {d.year for d in p.impairment_test_dates}
        for y in range(cap_rows[0][0].year, last.year + 1):
            ye = date(y, 12, 31)
            if ye > last or ye < cap_rows[0][0]:
                continue
            if p.available_for_use and p.available_for_use <= ye:
                continue
            if p.abandoned_on and p.abandoned_on <= ye:
                continue
            if y not in test_years:
                warnings.append(f"E5: {y} yil — foydalanishga tayyor bo'lmagan nomoddiy aktiv qadrsizlanish testidan o'tkazilmagan (IAS 36.10(a))")

    first_met = next((a.on for a in sorted(p.assessments, key=lambda x: x.on)
                      if _assessment_status(a, fw)[0] == "met"), None)
    if not cap:
        decision = "XARAJAT SIFATIDA TAN OLINADI"
    elif p.abandoned_on:
        decision = "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN"
    elif nas_wo >= cap:
        decision = "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN"
    else:
        decision = "KAPITALLASHTIRILADI"
    res = {"framework": fw, "decision": decision, "first_met_on": first_met,
           "capitalized": cap, "expensed": exp, "nas_criteria_writeoff": nas_wo, "nas_writeoff_rows": nas_wo_rows,
           "amort_months": months, "rows": rows, "cap_rows": cap_rows, "warnings": warnings}
    res["writeoff"] = abandonment_writeoff(res, p, s)
    if res["writeoff"]:
        warnings.append(f"{p.abandoned_on}: loyiha to'xtatildi — qoldiq {res['writeoff']:,} so'm hisobdan chiqariladi")
    return res

# ------------------------------------------------------------------ amortization
def amort_start(p: Project, s: Settings) -> Optional[tuple]:
    a = p.available_for_use
    if not a:
        return None
    same = s.amort_start == "same_month" or (s.amort_start == "auto" and a.day == 1)
    y, m = a.year, a.month
    if not same:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return y, m

def _pre_availability_impairment(res, p):
    """Impairment of an asset not yet available for use (IAS 36.10(a), 36.59)."""
    if not p.impairment_event:
        return 0
    d, rec = p.impairment_event
    if p.available_for_use and d >= p.available_for_use:
        return 0
    base = (sum(a for x, a in res["cap_rows"] if x <= d)
            - sum(a for x, a in res["nas_writeoff_rows"] if x <= d))
    return max(base - rec, 0)

def schedule(res: dict, p: Project, s: Settings = Settings()) -> list[dict]:
    """Straight-line monthly schedule, posted at month end; last month takes the rounding
    remainder. Post-availability impairment: recognised at the end of the month containing
    the event, after that month's amortization (IAS 36.59); remaining amount spread over
    the remaining months (IAS 36.63). Stops at abandonment (derecognition, IAS 38.112-113)."""
    months = res["amort_months"]
    start = amort_start(p, s)
    base = res["capitalized"] - res["nas_criteria_writeoff"] - _pre_availability_impairment(res, p)
    if not months or not start or base <= 0:
        return []
    out, carrying, remaining, done = [], base, months, False
    y, m = start
    for _ in range(months):
        pe = month_end(y, m)
        if p.abandoned_on and p.abandoned_on <= pe:
            break
        opening = carrying
        amort = carrying if remaining == 1 else carrying // remaining
        carrying -= amort
        remaining -= 1
        imp = 0
        ev = p.impairment_event
        if ev and not done and p.available_for_use and ev[0] >= p.available_for_use and ev[0] <= pe:
            if ev[1] < carrying:
                imp, carrying = carrying - ev[1], ev[1]
            done = True
        out.append({"period_end": pe, "opening": opening, "amortization": amort, "impairment": imp, "closing": carrying})
        if carrying == 0:
            break
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out

def abandonment_writeoff(res: dict, p: Project, s: Settings = Settings()) -> int:
    if not p.abandoned_on or not res["capitalized"]:
        return 0
    return carrying_amount(res, p, p.abandoned_on, s, _before_abandon=True)

def carrying_amount(res: dict, p: Project, at: date, s: Settings = Settings(), _before_abandon=False) -> int:
    if p.abandoned_on and at >= p.abandoned_on and not _before_abandon:
        return 0
    if p.impairment_event is None or p.impairment_event[0] > at:
        pre_imp = 0
    else:
        pre_imp = _pre_availability_impairment(res, p)
    nas_wo = sum(a for d, a in res["nas_writeoff_rows"] if d <= at)
    base = sum(a for d, a in res["cap_rows"] if d <= at) - pre_imp - nas_wo
    sch = [r for r in schedule(res, p, s) if r["period_end"] <= at]
    if sch:
        return sch[-1]["closing"]
    return max(base, 0)

def reconcile(p: Project, at: date, s: Settings = Settings()) -> dict:
    a, b = evaluate(p, "IAS38", s), evaluate(p, "NAS11", s)
    ca, cb = carrying_amount(a, p, at, s), carrying_amount(b, p, at, s)
    return {"IAS38_capitalized": a["capitalized"], "NAS11_capitalized": b["capitalized"],
            "IAS38_carrying": ca, "NAS11_carrying": cb, "difference": ca - cb}
