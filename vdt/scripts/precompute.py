"""
Kesh generatori: tayyor ssenariylarni (oddiy / avariya / osish30) oldindan hisoblab,
data/cache/*.json ga saqlaydi. Sahnada faqat shu kesh ko'rsatiladi.

  python scripts/precompute.py                 # ssenariylar (120 s) + investitsiya reytingi
  python scripts/precompute.py --skip-investment
  python scripts/precompute.py --only-investment
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import (preset, scenario_dict, investment_ranking, DEMO_SEED,  # noqa: E402
                    recovery_time)
from engine.run import fifo_result, ai_result  # noqa: E402

CACHE = os.path.join(ROOT, "data", "cache")
OBJECTIVES = ("umumiy", "ustuvorlik")


def save(name, obj):
    os.makedirs(CACHE, exist_ok=True)
    tmp = os.path.join(CACHE, name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(CACHE, name))


def log(*a):
    print(f"[{dt.datetime.now():%H:%M:%S}]", *a, flush=True)


def scenarios(time_limit, workers):
    index = []
    for name in ("oddiy", "avariya", "osish30"):
        st, tr, dis = preset(name)
        fifo, fsched = fifo_result(st, tr, dis)
        out = dict(nomi=name, seed=DEMO_SEED, sintetik=True, time_limit=time_limit,
                   yaratilgan=dt.datetime.now().isoformat(timespec="seconds"),
                   scenario=scenario_dict(st, tr, dis), fifo=fifo, ai={})
        scheds = {}
        for obj in OBJECTIVES:
            log(f"{name}/{obj}: CP-SAT {time_limit} s ...")
            res, sched = ai_result(st, tr, dis, obj, time_limit, workers)
            out["ai"][obj] = res
            scheds[obj] = sched
            log(f"  {res['status']} kechikish={res['metrics']['umumiy_kechikish_daq'] if res['ok'] else '-'}"
                f" xato={len(res['xatolar'] or [])}")
        if dis:
            out["tiklanish"] = dict(
                fifo=None if fsched is None else recovery_time(st, tr, fsched, dis),
                ai={o: recovery_time(st, tr, scheds[o], dis) for o in OBJECTIVES})
            # sahna uchun: AI qisqa vaqtda ham yechim topadimi
            quick, _ = ai_result(st, tr, dis, "umumiy", 5.0, workers)
            out["tez_hisob"] = dict(soniya=quick["hisob_soniya"], status=quick["status"],
                                    umumiy_kechikish=quick["metrics"]["umumiy_kechikish_daq"],
                                    xatolar=len(quick["xatolar"]))
        save(f"{name}.json", out)
        index.append(name)
        log(f"saqlandi: {name}.json")
    return index


def refresh_recovery():
    """Keshdagi jadvallardan tiklanish vaqtini qayta hisoblash (uzoq hisobni takrorlamasdan)."""
    path_ = os.path.join(CACHE, "avariya.json")
    with open(path_, encoding="utf-8") as f:
        out = json.load(f)
    st, tr, dis = preset("avariya")

    def tup(rows):
        return {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in rows.items()}
    out["tiklanish"] = dict(
        fifo=None if not out["fifo"]["ok"] else recovery_time(st, tr, tup(out["fifo"]["schedule"]), dis),
        ai={o: recovery_time(st, tr, tup(out["ai"][o]["schedule"]), dis) for o in OBJECTIVES})
    save("avariya.json", out)
    log("tiklanish yangilandi:", out["tiklanish"])


def investment(time_limit, base_time_limit, workers):
    st, tr, _ = preset("oddiy")
    t0 = time.time()
    meta = dict(ssenariy="oddiy", seed=DEMO_SEED, maqsad="umumiy", sintetik=True,
                protokol=dict(asosiy_hisob_s=base_time_limit, variant_hisob_s=time_limit,
                              seedlar=[1, 2, 3], nazorat_guruhi=True))
    partial = []

    def progress(i, row):
        partial.append(row)
        log(f"  investitsiya {row['bekat']}: tejaldi {row['tejaldi_daq']} daq")
        save("investment.json", dict(meta, tugallangan=False, reyting=sorted(
            partial, key=lambda x: -x["tejaldi_daq"])))

    log("investitsiya reytingi boshlandi (uzoq hisob) ...")
    res = investment_ranking(st, tr, "umumiy", time_limit, base_time_limit, (1, 2, 3),
                             workers, progress)
    save("investment.json", dict(meta, **res, tugallangan=True,
                                 hisob_daqiqa=round((time.time() - t0) / 60, 1),
                                 yaratilgan=dt.datetime.now().isoformat(timespec="seconds")))
    log("saqlandi: investment.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit", type=float, default=120.0)
    ap.add_argument("--inv-time-limit", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-investment", action="store_true")
    ap.add_argument("--only-investment", action="store_true")
    ap.add_argument("--recovery-only", action="store_true")
    a = ap.parse_args()
    if a.recovery_only:
        refresh_recovery()
        sys.exit(0)
    if not a.only_investment:
        scenarios(a.time_limit, a.workers)
    if not a.skip_investment:
        investment(a.inv_time_limit, a.time_limit, a.workers)
