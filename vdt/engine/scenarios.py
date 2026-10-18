"""Sintetik 'Corridor-12' ssenariylari (real ma'lumot emas)."""
import copy
import random

from .model import Station, Train


def make_scenario(seed=1, n_st=12, n_trains=18, window=600):
    """Sintetik 'Corridor-12' ssenariysi (real ma'lumot emas)."""
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


# Demo uchun tayyor ssenariylar (seed 4). "avariya": S6–S7 peregoni 180–270-daqiqada yopiq
# (90 daqiqa) — bu holatda FIFO tupikka tushadi, AI esa yechim topadi.
DEMO_SEED = 4
AVARIYA_DISRUPTION = dict(segment=(6, 7), start=180, end=270)

PRESETS = {
    "oddiy": dict(n_trains=18, disruption=None),
    "avariya": dict(n_trains=18, disruption=AVARIYA_DISRUPTION),
    "osish30": dict(n_trains=24, disruption=None),       # +30% poyezd (18 → 24)
}


def preset(name, seed=DEMO_SEED):
    cfg = PRESETS[name]
    st, trains = make_scenario(seed, n_trains=cfg["n_trains"])
    dis = dict(cfg["disruption"]) if cfg["disruption"] else None
    return st, trains, dis


def apply_breakdown(trains, train_id, station, minutes):
    """Poyezd buzilishi: poyezd oraliq bekatda qo'shimcha `minutes` daqiqa turib qoladi."""
    out = copy.deepcopy(trains)
    for t in out:
        if t.id == train_id:
            t.stops = dict(t.stops)
            t.stops[station] = t.stops.get(station, 0) + minutes
    return out


def add_passing_loop(st, trains, k, disruption=None, tracks=3):
    """
    k — (k, k+1) peregon o'rtasiga obgon punkti qo'shish: asosiy yo'l + chap va o'ng aylanma yo'l
    (tracks=3). Poyezdlar unda faqat kerak bo'lsa to'xtaydi (quvib o'tish yoki qarama-qarshi
    poyezd bilan uchrashuv). Qaytaradi: (st2, trains2, disruption2, eski->yangi indeks funksiyasi).
    """
    mid = round((st[k].km + st[k + 1].km) / 2, 1)
    st2 = st[:k + 1] + [Station(f"O{k}{k + 1}", mid, tracks, "obgon")] + st[k + 1:]
    f = lambda i: i + 1 if i > k else i
    tr2 = copy.deepcopy(trains)
    for t in tr2:
        t.stops = {f(i): v for i, v in t.stops.items()}
    d2 = None
    if disruption:
        a, b = disruption["segment"]
        if {a, b} == {k, k + 1}:
            # yopilgan peregon endi ikki qismdan iborat — ikkalasi ham yopiq bo'ladi;
            # soddalik uchun bunday variant ko'rib chiqilmaydi
            raise ValueError("yopiq peregonga obgon punkti qo'shilmaydi")
        d2 = dict(disruption, segment=(f(a), f(b)))
    return st2, tr2, d2, f


def map_schedule(st2, trains2, sched, k):
    """Eski jadvalni obgon punktli topologiyaga o'tkazish: punktdan to'xtamasdan o'tadi.
    Yurish vaqti yig'indisi o'zgarmagani uchun natija xavfsizlik qoidalarini saqlaydi."""
    from .model import run_time
    by_id = {t.id: t for t in trains2}
    out = {}
    for tid, rows in sched.items():
        rows = [(s + 1 if s > k else s, a, d) for s, a, d in rows]
        new = []
        for i, (s, a, d) in enumerate(rows):
            new.append((s, a, d))
            if i + 1 < len(rows) and {s, rows[i + 1][0]} == {k, k + 2}:
                am = d + run_time(st2, s, k + 1, by_id[tid])
                new.append((k + 1, am, am))
        out[tid] = new
    return out
