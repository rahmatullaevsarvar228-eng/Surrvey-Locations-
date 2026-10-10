"""Bitta holat uchun FIFO va AI natijalarini frontendga tayyor ko'rinishda hisoblash."""
import time

from .fifo import simulate_fifo
from .optimizer import optimise
from .validator import verify
from .metrics import metrics
from .export import sched_rows


def fifo_result(st, trains, disruption=None):
    ok, sched, dl = simulate_fifo(st, trains, disruption)
    rows = sched_rows(sched)
    out = dict(ok=ok, deadlock=None, metrics=None, xatolar=None, schedule=rows)
    if ok:
        out["metrics"] = metrics(st, trains, sched)
        out["xatolar"] = verify(st, trains, sched, disruption)
    else:
        # tupikda qolgan poyezdlarning oxirgi holati: bekatda turibdi, jo'nash yo'q
        for tid, (s, a) in dl["stuck_rows"].items():
            rows[tid].append(dict(bekat=s, kelish=a, ketish=None))
        last_move = max([d for v in sched.values() for _, _, d in v], default=0)
        out["deadlock"] = dict(stuck_trains=dl["stuck_trains"], at_station=dl["at_station"],
                               vaqt=last_move)
    return out, (sched if ok else None)


def ai_result(st, trains, disruption=None, objective="umumiy", time_limit=10.0,
              workers=8, seed=42):
    t0 = time.time()
    ok, sched, status = optimise(st, trains, disruption, objective=objective,
                                 time_limit=time_limit, workers=workers, seed=seed)
    secs = round(time.time() - t0, 1)
    if not ok:
        return dict(ok=False, status=status, hisob_soniya=secs, schedule=None,
                    metrics=None, xatolar=None), None
    return dict(ok=True, status=status, hisob_soniya=secs, time_limit=time_limit,
                schedule=sched_rows(sched), metrics=metrics(st, trains, sched),
                xatolar=verify(st, trains, sched, disruption)), sched


def run_case(st, trains, disruption=None, objective="umumiy", time_limit=10.0, workers=8):
    f, _ = fifo_result(st, trains, disruption)
    a, _ = ai_result(st, trains, disruption, objective, time_limit, workers)
    return dict(fifo=f, ai=a)
