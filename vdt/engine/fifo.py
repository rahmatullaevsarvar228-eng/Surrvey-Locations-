"""Bazaviy FIFO dispetcher — "kim birinchi kelsa, o'sha birinchi ketadi"."""
from .model import HEADWAY, HORIZON, path, is_terminal, run_time


def simulate_fifo(st, trains, disruption=None, headway=HEADWAY, horizon=HORIZON):
    """
    Daqiqama-daqiqa dispetcher. Poyezd keyingi peregonga kiradi, agar:
      peregon bo'sh (+headway), peregon yopilmagan va keyingi bekatda bo'sh yo'l bor.
    Qaytaradi: (ok, jadval, deadlock_info)
    deadlock_info (tupikda): stuck_trains, at_station, stuck_rows (poyezd -> (bekat, kelish)).
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
        for t in trains:                                   # jo'nash so'rovlari
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
            # peregon yopilgan bo'lsa yoki harakat paytida yopilsa — kirmaydi
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
    rows = {tid: (S[tid]["p"][S[tid]["pos"]], S[tid]["arr"]) for tid in stuck
            if S[tid]["moving_until"] is None}
    return False, sched, dict(stuck_trains=stuck, at_station=where, stuck_rows=rows)
