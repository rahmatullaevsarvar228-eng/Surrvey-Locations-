"""
"Obgon uchastkasi qayerga?" — peregon o'rtasiga ikki yo'lli qo'shimcha (asosiy yo'l + aylanma yo'l,
~4 km) qo'shilsa, kechikish qancha kamayadi. Unda poyezdlar to'xtamasdan uchrashadi va quvib o'tadi.
Protokol:
  * Boshlang'ich reja — keshdagi eng yaxshi AI jadvali (data/cache/<ssenariy>.json, 120 s).
  * Nazorat guruhi — obgon punktisiz, xuddi shu vaqt va seedlar bilan qayta hisob.
  * Har bir variant nazorat rejasidan boshlaydi (reja yangi topologiyaga o'tkaziladi va
    validatordan o'tadi), shuning uchun tejash >= 0 va faqat obgon punktidan kelib chiqadi.
  * Shovqin chegarasi = nazorat guruhida topilgan yaxshilanish (kamida 1 daqiqa).
Natija: data/cache/obgon.json
"""
import json, os, sys, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import (preset, optimise, objective_value, verify, metrics, sched_rows, scenario_dict,
                    add_passing_loop, map_schedule)

TL = float(os.environ.get("TL", 30)); SEEDS = (1,); W = int(os.environ.get("WORKERS", 4))


def best(st, tr, dis, hint):
    b = hint
    for sd in SEEDS:
        ok, sc, _ = optimise(st, tr, dis, objective="umumiy", time_limit=TL, seed=sd, extra_hint=b, workers=W)
        if ok and objective_value(st, tr, sc, "umumiy") < objective_value(st, tr, b, "umumiy"):
            b = sc
    return b


out = dict(yaratilgan=dt.datetime.now().isoformat(timespec="seconds"), hisob_s=TL, seedlar=list(SEEDS),
           qoshimcha_km=4, ssenariylar={})
for name in ("osish30", "avariya", "oddiy"):
    st, tr, dis = preset(name)
    cache = json.load(open(os.path.join(ROOT, f"data/cache/{name}.json")))
    base = {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in cache["ai"]["umumiy"]["schedule"].items()}
    v0 = objective_value(st, tr, base, "umumiy")
    ctrl = best(st, tr, dis, base)
    vc = objective_value(st, tr, ctrl, "umumiy")
    noise = max(v0 - vc, 1)
    rows, keep = [], {}
    for k in range(len(st) - 1):
        if dis and set(dis["segment"]) == {k, k + 1}:
            continue
        st2, tr2, d2, _ = add_passing_loop(st, tr, k, dis)
        hint = map_schedule(st2, tr2, ctrl, k)
        assert not verify(st2, tr2, hint, d2), "o'tkazilgan reja xavfsiz bo'lishi shart"
        sc = best(st2, tr2, d2, hint)
        v = objective_value(st2, tr2, sc, "umumiy")
        row = dict(peregon=f"{st[k].name}–{st[k + 1].name}", k=k, uzunlik_km=round(st[k + 1].km - st[k].km, 1),
                   tejaldi_daq=vc - v, sezilarli=(vc - v) > noise, xatolar=len(verify(st2, tr2, sc, d2)))
        rows.append(row)
        keep[k] = (st2, tr2, d2, hint, sc)
        print(name, row, flush=True)
    rows.sort(key=lambda r: -r["tejaldi_daq"])
    variants = []
    for r in rows[:3]:
        if r["tejaldi_daq"] <= 0:
            continue
        st2, tr2, d2, hint, sc = keep[r["k"]]
        variants.append(dict(peregon=r["peregon"], k=r["k"], punkt=st2[r["k"] + 1].name,
                             tejaldi_daq=r["tejaldi_daq"], scenario=scenario_dict(st2, tr2, d2),
                             oldin=sched_rows(hint), keyin=sched_rows(sc),
                             metrics_oldin=metrics(st2, tr2, hint), metrics_keyin=metrics(st2, tr2, sc),
                             xatolar=verify(st2, tr2, sc, d2)))
    out["ssenariylar"][name] = dict(boshlangich=v0, nazorat=vc, shovqin=noise, reyting=rows, variantlar=variants)
    json.dump(out, open(os.path.join(ROOT, "data/cache/obgon.json"), "w"), ensure_ascii=False)
    print("saqlandi", name, flush=True)
