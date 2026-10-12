"""
"Yangi razyezd qayerda?" — yangilangan protokol.
Har bir oraliq bekatga +1 yo'l qo'shiladi va AI (umumiy kechikish) qayta hisoblanadi.
  * Boshlang'ich reja — keshdagi eng yaxshi AI jadvali (data/cache/<ssenariy>.json).
  * Nazorat guruhi — yangi yo'lsiz, xuddi shu vaqt va seedlar bilan; variantlar nazorat
    rejasidan boshlaydi, shuning uchun tejash >= 0 va faqat yangi yo'ldan kelib chiqadi.
Natija: data/cache/razyezd.json (reyting + eng yaxshi 2 bekat uchun oldin/keyin jadvali).
"""
import json, os, sys, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import preset, Station, optimise, objective_value, verify, metrics, sched_rows

TL = float(os.environ.get("TL", 30)); SEEDS = (1, 2); W = int(os.environ.get("WORKERS", 4))


def best(stations, tr, dis, hint):
    b = hint
    for sd in SEEDS:
        ok, sc, _ = optimise(stations, tr, dis, objective="umumiy", time_limit=TL, seed=sd, extra_hint=b, workers=W)
        if ok and objective_value(stations, tr, sc, "umumiy") < objective_value(stations, tr, b, "umumiy"):
            b = sc
    return b


out = dict(yaratilgan=dt.datetime.now().isoformat(timespec="seconds"), hisob_s=TL, seedlar=list(SEEDS), ssenariylar={})
for name in ("oddiy", "avariya"):
    st, tr, dis = preset(name)
    cache = json.load(open(os.path.join(ROOT, f"data/cache/{name}.json")))
    base = {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in cache["ai"]["umumiy"]["schedule"].items()}
    v0 = objective_value(st, tr, base, "umumiy")
    ctrl = best(st, tr, dis, base)
    vc = objective_value(st, tr, ctrl, "umumiy")
    rows, scheds = [], {}
    for i in range(1, len(st) - 1):
        st2 = [Station(s.name, s.km, s.tracks + (1 if j == i else 0)) for j, s in enumerate(st)]
        sc = best(st2, tr, dis, ctrl)
        v = objective_value(st2, tr, sc, "umumiy")
        rows.append(dict(bekat=st[i].name, indeks=i, yollar=st[i].tracks, tejaldi_daq=vc - v,
                         sezilarli=(vc - v) > max(v0 - vc, 1), xatolar=len(verify(st2, tr, sc, dis))))
        scheds[i] = (st2, sc)
        print(name, rows[-1], flush=True)
    rows.sort(key=lambda r: -r["tejaldi_daq"])
    variants = []
    for r in rows[:2]:
        st2, sc = scheds[r["indeks"]]
        variants.append(dict(bekat=r["bekat"], indeks=r["indeks"], yollar_oldin=r["yollar"], yollar_keyin=r["yollar"] + 1,
                             qiymat=objective_value(st2, tr, sc, "umumiy"), tejaldi_daq=r["tejaldi_daq"],
                             schedule=sched_rows(sc), metrics=metrics(st2, tr, sc), xatolar=verify(st2, tr, sc, dis)))
    out["ssenariylar"][name] = dict(boshlangich=v0, nazorat=dict(qiymat=vc, schedule=sched_rows(ctrl),
                                    metrics=metrics(st, tr, ctrl), xatolar=verify(st, tr, ctrl, dis)),
                                    shovqin=v0 - vc, reyting=rows, variantlar=variants)
    json.dump(out, open(os.path.join(ROOT, "data/cache/razyezd.json"), "w"), ensure_ascii=False)
    print("saqlandi", name, flush=True)
