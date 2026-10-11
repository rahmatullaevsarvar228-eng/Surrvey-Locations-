"""
10 seed bo'yicha tajriba (TZ 4-bo'lim protokoli): har ssenariy uchun FIFO vs AI,
AI har biri 8 s, ikki maqsad. Natija: data/experiment.json.
"Avariya" qoidasi: S6–S7 peregoni 180–270-daqiqa yopiq (barcha seedlarda bir xil).
"""
import json, os, sys, statistics as stt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import make_scenario, simulate_fifo, optimise, verify, objective_value, AVARIYA_DISRUPTION

TL = float(os.environ.get("TL", 8))
res = {}
checked = violations = 0
for name, n_tr, dis in [("oddiy", 18, None), ("avariya", 18, AVARIYA_DISRUPTION), ("osish30", 24, None)]:
    rows = []
    for seed in range(1, 11):
        st, tr = make_scenario(seed, n_trains=n_tr)
        okf, sf, dl = simulate_fifo(st, tr, dis)
        if okf:
            checked += 1; violations += len(verify(st, tr, sf, dis))
        row = dict(seed=seed, fifo_tupik=not okf, stuck=len(dl["stuck_trains"]) if dl else 0)
        for obj in ("umumiy", "ustuvorlik"):
            ok, sa, status = optimise(st, tr, dis, objective=obj, time_limit=TL, workers=4)
            checked += 1; violations += len(verify(st, tr, sa, dis))
            va = objective_value(st, tr, sa, obj)
            vf = objective_value(st, tr, sf, obj) if okf else None
            row[obj] = dict(ai=va, fifo=vf, pct=None if vf in (None, 0) else round((va - vf) / vf * 100, 1))
        rows.append(row)
        print(name, row, flush=True)
    summ = {}
    for obj in ("umumiy", "ustuvorlik"):
        p = [r[obj]["pct"] for r in rows if r[obj]["pct"] is not None]
        summ[obj] = dict(ortacha=round(stt.mean(p), 1), min=min(p), max=max(p), n=len(p))
    res[name] = dict(rows=rows, xulosa=summ, tupik=sum(r["fifo_tupik"] for r in rows))
res["validator"] = dict(jadvallar=checked, buzilishlar=violations, ai_soniya=TL)
json.dump(res, open(os.path.join(ROOT, "data", "experiment.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: (v["xulosa"], v["tupik"]) if k != "validator" else v for k, v in res.items()}, ensure_ascii=False))
