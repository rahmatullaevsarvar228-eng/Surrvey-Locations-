"""M6 journal entries."""
import random
from datetime import date as d

import pytest

from ittki.core.engine import Settings, carrying_amount, evaluate, schedule, FRAMEWORKS, AMORT_START_MODES
from ittki.core.journal import (Accounts, balance, journal, OP_ABANDON_WRITEOFF, OP_AMORTIZATION,
                                OP_CAPITALIZE, OP_DISPOSAL_ACCUM, OP_DISPOSAL_RESIDUAL, OP_EXPENSE,
                                OP_IMPAIRMENT, OP_NAS_WRITEOFF, OP_PRE_IMPAIRMENT, OP_TRANSFER)
from tests.test_engine import M, proj, yes_all
from tests.test_invariants import random_project

A = Accounts()


def ops(entries, op):
    return [e for e in entries if e.op == op]


def total(entries, op):
    return sum(e.amount for e in ops(entries, op))


def test_base_project_postings():
    p = proj()
    for fw in FRAMEWORKS:
        res = evaluate(p, fw)
        j = journal(res, p)
        assert total(j, OP_EXPENSE) == 390 * M
        assert all(e.debit == "9420" for e in ops(j, OP_EXPENSE))
        cap = ops(j, OP_CAPITALIZE)
        assert [(e.on, e.amount, e.debit, e.credit) for e in cap] == [
            (d(2024, 8, 10), 300 * M, "0830", "6710"), (d(2024, 11, 10), 250 * M, "0830", "0230")]
        (t,) = ops(j, OP_TRANSFER)
        assert (t.on, t.debit, t.credit, t.amount) == (d(2025, 1, 1), "0490", "0830", 550 * M)
        am = ops(j, OP_AMORTIZATION)
        assert len(am) == (96 if fw == "IAS38" else 60) and total(j, OP_AMORTIZATION) == 550 * M
        assert all((e.debit, e.credit) == ("9420", "0590") for e in am)
        assert balance(j, "0830") == 0
        assert balance(j, "0490") + balance(j, "0590", d(2025, 12, 31)) == carrying_amount(res, p, d(2025, 12, 31))


def test_source_accounts_by_category():
    p = proj()
    j = journal(evaluate(p, "IAS38"), p)
    by_cat = {e.category: e.credit for e in j if e.category}
    assert by_cat == {"salary": "6710", "materials": "1010", "training": "6010",
                      "general_admin": "6010", "depreciation": "0230"}


def test_expense_account_9430_by_policy_and_amortization_to_production():
    p = proj()
    acc = Accounts(expense="9430", amortization_debit="2510", asset="0410", accumulated="0510")
    j = journal(evaluate(p, "NAS11"), p, acc=acc)
    assert {e.debit for e in ops(j, OP_EXPENSE)} == {"9430"}
    assert {(e.debit, e.credit) for e in ops(j, OP_AMORTIZATION)} == {("2510", "0510")}
    assert ops(j, OP_TRANSFER)[0].debit == "0410"


def test_s7_abandoned_before_ready_writeoff():
    p = proj(available_for_use=None, abandoned_on=d(2025, 3, 1))
    j = journal(evaluate(p, "IAS38"), p)
    (w,) = ops(j, OP_ABANDON_WRITEOFF)
    assert (w.on, w.debit, w.credit, w.amount) == (d(2025, 3, 1), "9430", "0830", 550 * M)
    assert not ops(j, OP_TRANSFER) and balance(j, "0830") == 0


def test_s11_nas_writeoff_entry():
    p = proj(assessments=[yes_all(d(2024, 7, 1)), yes_all(d(2024, 9, 1), K4="no")])
    j = journal(evaluate(p, "NAS11"), p)
    (w,) = ops(j, OP_NAS_WRITEOFF)
    assert (w.on, w.debit, w.credit, w.amount) == (d(2024, 9, 1), "9430", "0830", 300 * M)
    assert not ops(journal(evaluate(p, "IAS38"), p), OP_NAS_WRITEOFF)   # IAS 38: indicator only


def test_s12_disposal_after_ready():
    p = proj(abandoned_on=d(2025, 7, 10))
    for fw, life in (("IAS38", 96), ("NAS11", 60)):
        res = evaluate(p, fw)
        j = journal(res, p)
        (acc_,) = ops(j, OP_DISPOSAL_ACCUM)
        (resid,) = ops(j, OP_DISPOSAL_RESIDUAL)
        assert acc_.amount == 6 * (550 * M // life) and (acc_.debit, acc_.credit) == ("0590", "0490")
        assert resid.amount == res["writeoff"] == 550 * M - 6 * (550 * M // life)
        assert (resid.debit, resid.credit) == ("9430", "0490")
        assert balance(j, "0490") == balance(j, "0590") == balance(j, "0830") == 0


def test_s10_s14_impairment_entries():
    p = proj(impairment_event=(d(2025, 12, 31), 300 * M))
    j = journal(evaluate(p, "IAS38"), p)
    (i,) = ops(j, OP_IMPAIRMENT)
    assert (i.on, i.debit, i.credit) == (d(2025, 12, 31), "9430", "0590")
    p = proj(impairment_event=(d(2024, 12, 15), 400 * M))
    j = journal(evaluate(p, "IAS38"), p)
    (i,) = ops(j, OP_PRE_IMPAIRMENT)
    assert (i.on, i.debit, i.credit, i.amount) == (d(2024, 12, 15), "9430", "0830", 150 * M)
    assert ops(j, OP_TRANSFER)[0].amount == 400 * M


def test_no_double_writeoff_when_assessed_after_abandonment():
    # project abandoned before ready; a later 'no' assessment must not write the balance off again
    p = proj(available_for_use=None, abandoned_on=d(2025, 3, 1),
             assessments=[yes_all(d(2024, 7, 1)), yes_all(d(2025, 6, 1), K4="no")])
    res = evaluate(p, "NAS11")
    j = journal(res, p)
    assert total(j, OP_ABANDON_WRITEOFF) == 550 * M and not ops(j, OP_NAS_WRITEOFF)
    assert balance(j, "0830") == 0


def test_out_of_scope_has_no_entries():
    p = proj(scope="mineral_exploration")
    assert journal(evaluate(p, "IAS38"), p) == []


@pytest.mark.parametrize("bad", ["9410", "941", "abcd", 9420])
def test_invalid_or_forbidden_account_rejected(bad):
    with pytest.raises(ValueError):
        Accounts(expense=bad)
    with pytest.raises(ValueError):
        Accounts(source={**Accounts().source, "salary": bad})


def test_9410_never_appears_in_defaults():
    assert "9410" not in Accounts().all_codes()


def test_journal_invariants_random():
    """Asset accounts always equal the engine carrying amount; cost postings equal total costs."""
    random.seed(7)
    checked = 0
    for _ in range(1500):
        p = random_project()
        for fw in FRAMEWORKS:
            for mode in AMORT_START_MODES:
                s = Settings(amort_start=mode)
                res = evaluate(p, fw, s, as_of=d(2026, 6, 30))
                j = journal(res, p, s)
                assert all(e.amount > 0 and "9410" not in (e.debit, e.credit) for e in j)
                if p.scope != "rnd":
                    assert j == []
                    continue
                assert total(j, OP_CAPITALIZE) == res["capitalized"]
                assert total(j, OP_EXPENSE) == res["expensed"]
                assert total(j, OP_CAPITALIZE) + total(j, OP_EXPENSE) == sum(c.amount for c in p.costs)
                if p.abandoned_on and res["writeoff"]:
                    assert total(j, OP_ABANDON_WRITEOFF) + total(j, OP_DISPOSAL_RESIDUAL) == res["writeoff"]
                # engine quirk (see docs/doubts): BHMS 11 write-off dated after availability
                writeoffs = total(j, OP_NAS_WRITEOFF) + total(j, OP_PRE_IMPAIRMENT) + total(j, OP_ABANDON_WRITEOFF)
                assert writeoffs <= res["capitalized"]          # never written off twice
                quirk = p.available_for_use and any(w >= p.available_for_use for w, _ in res["nas_writeoff_rows"])
                if quirk:
                    continue
                for at in (d(2023, 12, 31), d(2024, 6, 30), d(2024, 12, 31), d(2025, 6, 30), d(2025, 12, 31),
                           d(2027, 12, 31), d(2040, 1, 1)):
                    bal = balance(j, "0830", at) + balance(j, "0490", at) + balance(j, "0590", at)
                    assert bal == carrying_amount(res, p, at, s), (fw, mode, at)
                checked += 1
    assert checked > 5000
