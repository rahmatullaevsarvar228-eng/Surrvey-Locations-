"""
VIRTUAL DOUBLE-TRACK — hisob yadrosi (reference engine)
Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar

Model: bir yo‘lli (single-track) temir yo‘l uchastkasi.
  * Bekatlar (stansiyalar) orasidagi peregonda bir vaqtda faqat 1 ta poyezd bo‘ladi.
  * Peregon bo‘shagach, keyingi poyezd kamida HEADWAY daqiqadan keyin kira oladi
    (xavfsizlik oralig‘i).
  * Bekatda bir vaqtda yo‘llar sonidan ko‘p poyezd turmaydi.
Bazaviy usul : FIFO dispetcher — "kim birinchi kelsa, o‘sha birinchi ketadi"
               (teng holatda ustuvorligi yuqori poyezd).
AI usul      : CP-SAT (Google OR-Tools) — butun koridor bo‘yicha uchrashuv/o‘tkazib
               yuborish qarorlarini global optimallashtirish.
Mustaqil validator: har qanday jadvalni xavfsizlik qoidalari bo‘yicha tekshiradi.
Barcha vaqtlar — butun daqiqalarda.
"""
import json
import math
import random
from dataclasses import dataclass, field, asdict

from ortools.sat.python import cp_model

HEADWAY = 3          # peregon bo‘shagandan keyingi minimal oraliq, daqiqa
HORIZON = 3000       # modellashtirish gorizonti, daqiqa


@dataclass
class Station:
    name: str
    km: float
    tracks: int                  # asosiy yo‘l bilan birga yo‘llar soni


@dataclass
class Train:
    id: str
    kind: str                    # "yuk" | "yolovchi" | "tezyurar"
    direction: int               # +1 = A→B, -1 = B→A
    speed: float                 # km/soat
    release: int                 # boshlang‘ich bekatdan eng erta jo‘nash, daqiqa
    weight: int                  # ustuvorlik vazni
    stops: dict = field(default_factory=dict)   # bekat indeksi -> minimal turish, daqiqa


# ------------------------------------------------------------------ yordamchi
def run_time(st, i, j, tr):
    return max(1, math.ceil(abs(st[j].km - st[i].km) / tr.speed * 60))


def path(st, tr):
    n = len(st)
    return list(range(n)) if tr.direction == 1 else list(range(n - 1, -1, -1))


def is_terminal(st, i):
    return i == 0 or i == len(st) - 1


def free_run(st, tr):
    """To‘siqsiz harakatdagi manzilga yetib kelish vaqti."""
    p = path(st, tr)
    t = tr.release
    for k in range(len(p) - 1):
        if k > 0:
            t += tr.stops.get(p[k], 0)
        t += run_time(st, p[k], p[k + 1], tr)
    return t


def _blocked(dis, key, minute):
    return bool(dis) and key == frozenset(dis["segment"]) and dis["start"] <= minute < dis["end"]


# ------------------------------------------------------------------ bazaviy FIFO
def simulate_fifo(st, trains, disruption=None, headway=HEADWAY, horizon=HORIZON):
    """
    Daqiqama-daqiqa dispetcher. Poyezd keyingi peregonga kiradi, agar:
      peregon bo‘sh (+headway), peregon yopilmagan va keyingi bekatda bo‘sh yo‘l bor.
    Qaytaradi: (ok, jadval, deadlock_info)
    """
    n = len(st)
    seg_free_at = {}
    occ = [0] * n
    S = {}
    sched = {t.id: [] for t in trains}
    for t in trains:
        S[t.id] = dict(pos=0, p=path(st, t), arr=t.release, ready=t.release,
                       moving_until=None, done=False, left_origin=False)

    for minute in range(horizon):
        for t in trains:                                   # yetib kelishlar
            s = S[t.id]
            if s["moving_until"] == minute:
                s["moving_until"] = None
                s["pos"] += 1
                b = s["p"][s["pos"]]
                s["arr"] = minute
                if s["pos"] == len(s["p"]) - 1:
                    s["done"] = True
                    sched[t.id].append((b, minute, minute))
                else:
                    s["ready"] = minute + t.stops.get(b, 0)
        if all(S[t.id]["done"] for t in trains):
            return True, sched, None

        reqs = []
        for t in trains:                                   # jo‘nash so‘rovlari
            s = S[t.id]
            if not s["done"] and s["moving_until"] is None and minute >= s["ready"]:
                reqs.append((s["ready"], -t.weight, t.id, t))
        reqs.sort()
        for _, _, _, t in reqs:
            s = S[t.id]
            a, b = s["p"][s["pos"]], s["p"][s["pos"] + 1]
            key = frozenset((a, b))
            rt = run_time(st, a, b, t)
            if seg_free_at.get(key, -10**9) > minute:
                continue
            # peregon yopilgan bo‘lsa yoki harakat paytida yopilsa — kirmaydi
            if disruption and key == frozenset(disruption["segment"]) and \
                    minute < disruption["end"] and minute + rt + headway > disruption["start"]:
                continue
            if not is_terminal(st, b) and occ[b] >= st[b].tracks:
                continue
            seg_free_at[key] = minute + rt + headway
            if not is_terminal(st, b):
                occ[b] += 1
            if not is_terminal(st, a):
                occ[a] -= 1
            sched[t.id].append((a, s["arr"], minute))
            s["moving_until"] = minute + rt

    stuck = [t.id for t in trains if not S[t.id]["done"]]
    where = {tid: st[S[tid]["p"][S[tid]["pos"]]].name for tid in stuck}
    return False, sched, dict(stuck_trains=stuck, at_station=where)


# ------------------------------------------------------------------ AI: CP-SAT
def objective_value(st, trains, sched, objective):
    return sum((t.weight if objective == "ustuvorlik" else 1) * (sched[t.id][-1][1] - free_run(st, t))
               for t in trains)


def optimise(st, trains, disruption=None, objective="umumiy", headway=HEADWAY,
             horizon=HORIZON, time_limit=10.0, workers=8, seed=42, warm_start=True,
             extra_hint=None):
    """
    objective: "umumiy"     — umumiy kechikishni minimallashtirish
               "ustuvorlik" — vazn × kechikish (tezyurar va yo‘lovchi muhimroq)
    warm_start: AI dispetcherning (FIFO) rejasidan boshlaydi va faqat yaxshilaydi —
                natija hech qachon FIFO dan yomon bo‘lmaydi.
    extra_hint: qo‘shimcha boshlang‘ich reja (masalan, investitsiya rejimida asosiy yechim).
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
            # peregon band: [jo‘nash, yetib kelish + headway)
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


# ------------------------------------------------------------------ mustaqil validator
def verify(st, trains, sched, disruption=None, headway=HEADWAY):
    """Xavfsizlik qoidalari buzilishlari ro‘yxatini qaytaradi (bo‘sh = 0 konflikt)."""
    errs = []
    seg = {}
    for t in trains:
        rows = sched[t.id]
        for k in range(len(rows) - 1):
            a, _, dep = rows[k]
            b, arr, _ = rows[k + 1]
            if arr - dep < run_time(st, a, b, t):
                errs.append(f"{t.id}: {a}-{b} juda tez")
            seg.setdefault(frozenset((a, b)), []).append((dep, arr, t.id))
    for key, ivs in seg.items():
        ivs.sort()
        for (s1, e1, i1), (s2, e2, i2) in zip(ivs, ivs[1:]):
            if s2 < e1 + headway:
                errs.append(f"peregon {sorted(key)}: {i1} va {i2} to‘qnashuvi")
        if disruption and key == frozenset(disruption["segment"]):
            for s, e, i in ivs:
                if s < disruption["end"] and e > disruption["start"]:
                    errs.append(f"{i}: yopiq peregonga kirdi")
    for i in range(1, len(st) - 1):
        ev = []
        for t in trains:
            for s, a, d in sched[t.id]:
                if s == i:
                    ev.append((a, +1))
                    ev.append((d + 1, -1))
        ev.sort(key=lambda x: (x[0], x[1]))
        cur = 0
        for _, dlt in ev:
            cur += dlt
            if cur > st[i].tracks:
                errs.append(f"bekat {st[i].name}: sig‘im oshdi")
                break
    return errs


# ------------------------------------------------------------------ ko‘rsatkichlar
def metrics(st, trains, sched):
    tot = wtot = waits = 0
    by_kind = {}
    for t in trains:
        rows = sched[t.id]
        d = rows[-1][1] - free_run(st, t)
        tot += d
        wtot += t.weight * d
        by_kind.setdefault(t.kind, []).append(d)
        p = path(st, t)
        for k in range(1, len(rows) - 1):
            s, a, dep = rows[k]
            if dep - a > t.stops.get(p[k], 0):
                waits += 1
    makespan = max(r[-1][1] for r in sched.values())
    return dict(
        umumiy_kechikish_daq=tot,
        ortacha_kechikish_daq=round(tot / len(trains), 1),
        vaznli_kechikish=wtot,
        tur_boyicha_ortacha={k: round(sum(v) / len(v), 1) for k, v in by_kind.items()},
        kutish_toxtashlari=waits,
        oxirgi_yetib_kelish_daq=makespan,
    )


# ------------------------------------------------------------------ ssenariylar
def make_scenario(seed=1, n_st=12, n_trains=18, window=600):
    """Sintetik 'Corridor-12' ssenariysi (real ma’lumot emas)."""
    rnd = random.Random(seed)
    st, km = [], 0.0
    for i in range(n_st):
        tracks = 99 if i in (0, n_st - 1) else rnd.choice([2, 2, 2, 3])
        st.append(Station(f"S{i}", round(km, 1), tracks))
        km += rnd.uniform(9, 16)
    kinds = [("yuk", 55, 1), ("yolovchi", 90, 3), ("tezyurar", 140, 5)]
    trains = []
    for k in range(n_trains):
        kind, sp, w = rnd.choices(kinds, weights=[6, 3, 1])[0]
        stops = {i: 3 for i in range(1, n_st - 1) if rnd.random() < 0.4} if kind == "yolovchi" else {}
        prefix = {"yuk": "YK", "yolovchi": "YL", "tezyurar": "TZ"}[kind]
        trains.append(Train(f"{prefix}{k:02d}", kind, 1 if k % 2 == 0 else -1,
                            sp, rnd.randint(0, window), w, stops))
    return st, trains


def _best_of_seeds(st, trains, objective, time_limit, seeds, hint):
    best = hint
    for sd in seeds:
        ok, sc, _ = optimise(st, trains, objective=objective, time_limit=time_limit,
                             seed=sd, extra_hint=best)
        if ok and (best is None or objective_value(st, trains, sc, objective)
                   < objective_value(st, trains, best, objective)):
            best = sc
    return best


def investment_ranking(st, trains, objective="umumiy", time_limit=60.0,
                       base_time_limit=120.0, seeds=(1, 2, 3)):
    """
    "Yangi razyezd qayerda?" — har bir oraliq bekatga +1 yo‘l qo‘shib, AI natijasini
    qayta hisoblaydi. Ilmiy protokol:
      1) Asosiy yechim har bir variantga boshlang‘ich reja sifatida beriladi —
         tejash hech qachon manfiy bo‘lmaydi (qo‘shimcha yo‘l zarar qilmaydi).
      2) NAZORAT GURUHI: yangi yo‘lsiz, xuddi shu vaqt va seed’lar bilan qayta hisob.
         Aks holda "tejash" yangi yo‘ldan emas, qo‘shimcha hisob vaqtidan chiqishi mumkin.
      3) Shovqin chegarasi = nazorat guruhida topilgan yaxshilanish. Undan kichik farq
         "sezilarli emas" deb belgilanadi.
    Uzoq hisob (o‘nlab daqiqa) — sahna uchun OLDINDAN hisoblab, keshga saqlang.
    """
    ok, base0, _ = optimise(st, trains, objective=objective, time_limit=base_time_limit)
    v0 = objective_value(st, trains, base0, objective)
    ctrl = _best_of_seeds(st, trains, objective, time_limit, seeds, base0)
    base_val = objective_value(st, trains, ctrl, objective)
    noise = v0 - base_val
    out = []
    for i in range(1, len(st) - 1):
        st2 = [Station(s.name, s.km, s.tracks + (1 if j == i else 0)) for j, s in enumerate(st)]
        sc = _best_of_seeds(st2, trains, objective, time_limit, seeds, ctrl)
        gain = base_val - objective_value(st2, trains, sc, objective)
        out.append(dict(bekat=st[i].name, tejaldi_daq=gain, sezilarli=gain > max(noise, 1)))
    return dict(asosiy_qiymat=base_val, shovqin_chegarasi=noise,
                reyting=sorted(out, key=lambda x: -x["tejaldi_daq"]))


def to_json(st, trains, sched):
    """Frontend uchun eksport."""
    return json.dumps(dict(stations=[asdict(s) for s in st],
                           trains=[asdict(t) for t in trains],
                           schedule={k: [dict(bekat=s, kelish=a, ketish=d) for s, a, d in v]
                                     for k, v in sched.items()}), ensure_ascii=False)


if __name__ == "__main__":
    st, tr = make_scenario(1)
    ok, sb, dl = simulate_fifo(st, tr)
    ok2, sa, status = optimise(st, tr, time_limit=10)
    print("FIFO:", metrics(st, tr, sb) if ok else dl, "| xato:", len(verify(st, tr, sb)) if ok else "-")
    print("AI  :", metrics(st, tr, sa), status, "| xato:", len(verify(st, tr, sa)))
