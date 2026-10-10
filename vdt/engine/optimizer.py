"""AI optimallashtiruvchi: CP-SAT (Google OR-Tools) — butun koridor bo'yicha global reja."""
from ortools.sat.python import cp_model

from .model import HEADWAY, HORIZON, path, is_terminal, run_time, free_run
from .fifo import simulate_fifo
from .validator import verify


def objective_value(st, trains, sched, objective):
    return sum((t.weight if objective == "ustuvorlik" else 1) * (sched[t.id][-1][1] - free_run(st, t))
               for t in trains)


def optimise(st, trains, disruption=None, objective="umumiy", headway=HEADWAY,
             horizon=HORIZON, time_limit=10.0, workers=8, seed=42, warm_start=True,
             extra_hint=None):
    """
    objective: "umumiy"     — umumiy kechikishni minimallashtirish
               "ustuvorlik" — vazn × kechikish (tezyurar va yo'lovchi muhimroq)
    warm_start: AI dispetcherning (FIFO) rejasidan boshlaydi va faqat yaxshilaydi —
                natija hech qachon FIFO dan yomon bo'lmaydi.
    extra_hint: qo'shimcha boshlang'ich reja (masalan, investitsiya rejimida asosiy yechim).
    Qaytaradi: (ok, jadval, status)
    """
    candidates = []
    if warm_start:
        okf, sf, _ = simulate_fifo(st, trains, disruption, headway, horizon)
        if okf:
            candidates.append(sf)
    if extra_hint is not None:
        candidates.append(extra_hint)
    candidates = [c for c in candidates if not verify(st, trains, c, disruption, headway)]
    hint = min(candidates, key=lambda c: objective_value(st, trains, c, objective)) if candidates else None
    ok, sched, status = _solve_cp(st, trains, disruption, objective, headway, horizon,
                                  time_limit, workers, seed, hint)
    if hint is not None and (not ok or objective_value(st, trains, sched, objective)
                             > objective_value(st, trains, hint, objective)):
        return True, hint, "BOSHLANGICH_REJA_SAQLANDI"
    return ok, sched, status


def _solve_cp(st, trains, disruption, objective, headway, horizon, time_limit, workers, seed, hint):
    n = len(st)
    m = cp_model.CpModel()
    A, D = {}, {}
    seg_iv, sta_iv, obj = {}, {i: [] for i in range(n)}, []

    for t in trains:
        p = path(st, t)
        for k, s in enumerate(p):
            A[t.id, s] = m.NewIntVar(0, horizon, f"a_{t.id}_{s}")
            D[t.id, s] = m.NewIntVar(0, horizon, f"d_{t.id}_{s}")
            dwell = t.stops.get(s, 0) if 0 < k < len(p) - 1 else 0
            m.Add(D[t.id, s] >= A[t.id, s] + dwell)
        m.Add(A[t.id, p[0]] == t.release)
        m.Add(D[t.id, p[-1]] == A[t.id, p[-1]])
        for k in range(len(p) - 1):
            a, b = p[k], p[k + 1]
            rt = run_time(st, a, b, t)
            m.Add(A[t.id, b] == D[t.id, a] + rt)
            # peregon band: [jo'nash, yetib kelish + headway)
            seg_iv.setdefault(frozenset((a, b)), []).append(
                m.NewIntervalVar(D[t.id, a], rt + headway, A[t.id, b] + headway, f"seg_{t.id}_{a}_{b}"))
            if not is_terminal(st, b):
                dur = m.NewIntVar(1, horizon, f"dur_{t.id}_{b}")
                m.Add(dur == D[t.id, b] + 1 - A[t.id, b])      # bekatda kamida 1 daqiqa band
                sta_iv[b].append(m.NewIntervalVar(A[t.id, b], dur, D[t.id, b] + 1, f"st_{t.id}_{b}"))
        delay = m.NewIntVar(0, horizon, f"delay_{t.id}")
        m.Add(delay == A[t.id, p[-1]] - free_run(st, t))
        obj.append((t.weight if objective == "ustuvorlik" else 1) * delay)

    for key, ivs in seg_iv.items():
        if disruption and key == frozenset(disruption["segment"]):
            ivs = ivs + [m.NewFixedSizeIntervalVar(disruption["start"],
                                                   disruption["end"] - disruption["start"], "yopiq")]
        m.AddNoOverlap(ivs)
    for i in range(1, n - 1):
        if sta_iv[i]:
            m.AddCumulative(sta_iv[i], [1] * len(sta_iv[i]), st[i].tracks)

    if hint is not None:                       # issiq start: FIFO rejasi
        for t in trains:
            for s, a, d in hint[t.id]:
                m.AddHint(A[t.id, s], a)
                m.AddHint(D[t.id, s], d)
    m.Minimize(sum(obj))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    res = solver.Solve(m)
    if res not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return False, None, solver.StatusName(res)
    sched = {t.id: [(s, solver.Value(A[t.id, s]), solver.Value(D[t.id, s])) for s in path(st, t)]
             for t in trains}
    return True, sched, solver.StatusName(res)
