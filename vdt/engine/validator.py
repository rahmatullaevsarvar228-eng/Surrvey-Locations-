"""Mustaqil validator: har qanday jadvalni xavfsizlik qoidalari bo'yicha tekshiradi."""
from .model import HEADWAY, run_time


def verify(st, trains, sched, disruption=None, headway=HEADWAY):
    """Xavfsizlik qoidalari buzilishlari ro'yxatini qaytaradi (bo'sh = 0 konflikt)."""
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
                errs.append(f"peregon {sorted(key)}: {i1} va {i2} to'qnashuvi")
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
                errs.append(f"bekat {st[i].name}: sig'im oshdi")
                break
    return errs
