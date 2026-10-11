"""The ported engine must give exactly the same results as reference/engine_reference.py."""
import importlib.util
import random
import sys
from dataclasses import fields
from datetime import date
from pathlib import Path

from ittki.core import engine as new
from tests.test_invariants import random_project

_spec = importlib.util.spec_from_file_location("engine_reference", Path(__file__).parent.parent / "reference" / "engine_reference.py")
ref = importlib.util.module_from_spec(_spec)
sys.modules["engine_reference"] = ref
_spec.loader.exec_module(ref)


def to_ref(p):
    kw = {f.name: getattr(p, f.name) for f in fields(p)}
    kw["assessments"] = [ref.Assessment(a.on, dict(a.answers), dict(a.evidence)) for a in p.assessments]
    kw["costs"] = [ref.Cost(c.on, c.amount, c.category, c.note) for c in p.costs]
    return ref.Project(**kw)


def test_engine_equals_reference():
    random.seed(42)
    for _ in range(2000):
        p = random_project(); q = to_ref(p)
        for fw in new.FRAMEWORKS:
            for mode in new.AMORT_START_MODES:
                s, rs = new.Settings(amort_start=mode), ref.Settings(amort_start=mode)
                a = new.evaluate(p, fw, s, as_of=date(2026, 6, 30))
                b = ref.evaluate(q, fw, rs, as_of=date(2026, 6, 30))
                assert a == b
                assert new.schedule(a, p, s) == ref.schedule(b, q, rs)
                for at in (date(2024, 12, 31), date(2025, 12, 31), date(2030, 1, 1)):
                    assert new.carrying_amount(a, p, at, s) == ref.carrying_amount(b, q, at, rs)
        assert new.reconcile(p, date(2025, 12, 31)) == ref.reconcile(q, date(2025, 12, 31))


def test_category_override_is_opt_in():
    s = new.Settings(included={"IAS38": new.INCLUDED["IAS38"], "NAS11": new.INCLUDED["NAS11"] | {"training"}})
    assert s.categories("NAS11") >= {"training"} and "training" not in new.Settings().categories("NAS11")
