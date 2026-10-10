"""Ko'rsatkichlar."""
from .model import free_run, path, run_time


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


def free_run_times(st, tr):
    """To'siqsiz harakatda har bekatdan jo'nash vaqtlari: {bekat: jo'nash}."""
    p = path(st, tr)
    t, out = tr.release, {}
    for k in range(len(p) - 1):
        if k > 0:
            t += tr.stops.get(p[k], 0)
        out[p[k]] = t
        t += run_time(st, p[k], p[k + 1], tr)
    return out


def recovery_time(st, trains, sched, event):
    """
    Tiklanish vaqti (navbatni bo'shatish): hodisa joyidagi peregondan o'tishi kerak bo'lgan va
    to'siqsiz rejada hodisa tugashidan oldin unga kirishi kerak bo'lgan poyezdlar ("navbat")
    peregondan to'liq o'tib bo'lguncha, hodisa tugaganidan keyin o'tgan daqiqalar.
    event: dict(segment=(a, b), start, end). Navbat bo'lmasa — 0.
    """
    key = frozenset(event["segment"])
    last = None
    for t in trains:
        fr = free_run_times(st, t)
        rows = sched[t.id]
        for k in range(len(rows) - 1):
            a, _, dep = rows[k]
            b, arr, _ = rows[k + 1]
            if frozenset((a, b)) == key and fr[a] < event["end"] and dep >= event["start"]:
                last = arr if last is None else max(last, arr)
    if last is None:
        return 0
    return max(0, last - event["end"])


def breakdown_event(st, trains, sched, train_id, station):
    """Poyezd buzilishini hodisa sifatida ifodalash: buzilgan poyezd keyingi peregonni egallaydi."""
    tr = next(t for t in trains if t.id == train_id)
    p = path(st, tr)
    nxt = p[p.index(station) + 1]
    row = next(r for r in sched[train_id] if r[0] == station)
    return dict(segment=(station, nxt), start=row[1], end=row[2])
