"""TZ 7: a project with 1 000 costs is recalculated in < 1 s."""
import random
import time
from datetime import date as d, timedelta

from ittki.db.repository import CostRecord, ProjectRecord, Repository, User
from ittki.services import Service
from tests.test_db import all_yes

U = User("P", "accountant")


def test_1000_costs_recalculated_under_one_second():
    repo = Repository()
    pid = repo.save_project(ProjectRecord("PERF", "1000 xarajat", useful_life_months=96,
                                          development_start=d(2022, 1, 1), available_for_use=d(2026, 1, 1)), U)
    repo.add_assessment(all_yes(pid, d(2022, 3, 1)), User("L", "leader"))
    rnd = random.Random(1)
    cats = ["salary", "materials", "services", "training", "general_admin", "depreciation"]
    repo.add_costs([CostRecord(pid, d(2021, 6, 1) + timedelta(days=rnd.randint(0, 1600)), rnd.randint(1, 10**8),
                               rnd.choice(cats)) for _ in range(1000)], U)
    svc = Service(repo, today=lambda: d(2026, 10, 11))
    t = time.perf_counter()
    a = svc.analyze(pid)
    elapsed = time.perf_counter() - t
    assert len(a.res["IAS38"]["rows"]) == 1000
    assert elapsed < 1.0, f"{elapsed:.3f} s"
