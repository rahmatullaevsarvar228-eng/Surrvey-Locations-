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
