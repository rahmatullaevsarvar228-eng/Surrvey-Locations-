"""
Bosqichma-bosqich reja: har bir peregonga ikki yo'lli qo'shimcha (obgon uchastkasi, ~4 km) — poyezdlar
unda to'xtamasdan uchrashadi va quvib o'tadi.
Punktlar bittadan qo'shiladi — bitta punkt reytingi (data/cache/obgon.json) bo'yicha eng
foydalisidan boshlab; teng bo'lsa uzunroq peregon birinchi. Har bosqich oldingi bosqich rejasidan
boshlaydi (yangi sxemaga o'tkazilgan va validatordan o'tgan), shuning uchun natija bosqichdan
bosqichga yomonlashmaydi. Oxirgi bosqich — barcha peregonlarda punkt ("to'liq reja").
Natija: data/cache/obgon.json ichiga "bosqichlar" va "toliq" qo'shiladi.
"""
import json, os, sys, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import (preset, optimise, objective_value, verify, metrics, sched_rows, scenario_dict,
                    add_passing_loop, add_passing_loops, map_schedule)

TL = float(os.environ.get("TL", 30)); SEEDS = (1,); W = int(os.environ.get("WORKERS", 4))
PATH = os.path.join(ROOT, "data/cache/obgon.json")


def best(st, tr, dis, hint):
    b = hint
    for sd in SEEDS:
        ok, sc, _ = optimise(st, tr, dis, objective="umumiy", time_limit=TL, seed=sd, extra_hint=b, workers=W)
        if ok and objective_value(st, tr, sc, "umumiy") < objective_value(st, tr, b, "umumiy"):
            b = sc
    return b


data = json.load(open(PATH))
for name in ("osish30", "oddiy", "avariya"):
    st, tr, dis = preset(name)
    S = data["ssenariylar"][name]
    cache = json.load(open(os.path.join(ROOT, f"data/cache/{name}.json")))
    base = {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in cache["ai"]["umumiy"]["schedule"].items()}
    ctrl = best(st, tr, dis, base)
    vc = objective_value(st, tr, ctrl, "umumiy")
    order = sorted(S["reyting"], key=lambda r: (-r["tejaldi_daq"], -r["uzunlik_km"]))
    ks, cur = [], (st, tr, dis, ctrl)
    steps = []
    for r in order:
        k = r["k"]
        st_p, tr_p, d_p, s_p = cur
        idx = k + 2 * sum(1 for x in ks if x < k)          # peregonning joriy sxemadagi indeksi (har qo'shimcha +2 nuqta)
        st2, tr2, d2, _ = add_passing_loop(st_p, tr_p, idx, d_p)
        hint = map_schedule(st2, tr2, s_p, idx)
        assert not verify(st2, tr2, hint, d2)
        sc = best(st2, tr2, d2, hint)
        ks.append(k)
        cur = (st2, tr2, d2, sc)
        v = objective_value(st2, tr2, sc, "umumiy")
        steps.append(dict(n=len(ks), qoshildi=r["peregon"], punktlar=[x["peregon"] for x in order[:len(ks)]],
                          qiymat=v, tejaldi_daq=vc - v, xatolar=len(verify(st2, tr2, sc, d2))))
        print(name, steps[-1]["n"], r["peregon"], v, vc - v, steps[-1]["xatolar"], flush=True)
    st2, tr2, d2, sc = cur
    _, _, _, oldin = add_passing_loops(st, tr, ks, dis, ctrl)          # nazorat rejasi yangi sxemada
    S["nazorat"] = vc
    S["bosqichlar"] = steps
    S["toliq"] = dict(scenario=scenario_dict(st2, tr2, d2), oldin=sched_rows(oldin), keyin=sched_rows(sc),
                      metrics_oldin=metrics(st2, tr2, oldin), metrics_keyin=metrics(st2, tr2, sc),
                      xatolar=verify(st2, tr2, sc, d2), punktlar=len(ks))
    data["reja_yaratilgan"] = dt.datetime.now().isoformat(timespec="seconds")
    json.dump(data, open(PATH, "w"), ensure_ascii=False)
    print("saqlandi", name, flush=True)
