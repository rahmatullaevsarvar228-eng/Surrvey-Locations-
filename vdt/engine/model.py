"""Ma'lumotlar modeli va yordamchi funksiyalar (bir yo'lli uchastka)."""
import math
from dataclasses import dataclass, field

HEADWAY = 3          # peregon bo'shagandan keyingi minimal oraliq, daqiqa
HORIZON = 3000       # modellashtirish gorizonti, daqiqa


@dataclass
class Station:
    name: str
    km: float
    tracks: int                  # asosiy yo'l bilan birga yo'llar soni
    kind: str = "bekat"          # "bekat" | "jl" / "jr" — obgon uchastkasining boshi / oxiri


@dataclass
class Train:
    id: str
    kind: str                    # "yuk" | "yolovchi" | "tezyurar"
    direction: int               # +1 = A→B, -1 = B→A
    speed: float                 # km/soat
    release: int                 # boshlang'ich bekatdan eng erta jo'nash, daqiqa
    weight: int                  # ustuvorlik vazni
    stops: dict = field(default_factory=dict)   # bekat indeksi -> minimal turish, daqiqa


def _rt(km, tr):
    return max(1, math.ceil(km / tr.speed * 60))


def is_real(st, i):
    """Haqiqiy bekat (ikki yo'lli qo'shimchaning boshi/oxiri emas)."""
    return st[i].kind == "bekat"


def seg_capacity(st, i, j):
    """Peregon bo'lagining sig'imi: obgon uchastkasida (asosiy yo'l + chap va o'ng aylanma yo'l)
    bir vaqtda 3 ta poyezd, har biri o'z yo'lida; qolgan bo'laklarda — 1."""
    return 3 if {st[i].kind, st[j].kind} == {"jl", "jr"} else 1


def _cum(st, P, Q, x, full):
    """P..Q asl peregon ichidagi x nuqtagacha yurish vaqti (yig'indi asl vaqtga teng bo'ladi)."""
    if x == P:
        return 0
    if x == Q:
        return full
    prev = 0
    pts = list(range(P + 1, Q))
    for n, y in enumerate(pts):
        f = (st[y].km - st[P].km) / (st[Q].km - st[P].km)
        v = max(prev + 1, min(round(full * f), full - (len(pts) - n)))
        if y == x:
            return v
        prev = v
    raise ValueError(x)


def run_time(st, i, j, tr):
    """Yurish vaqti. Peregon ichidagi qo'shimcha nuqtalar (ikki yo'lli qo'shimcha) uni bo'laklarga
    bo'ladi, lekin bekatdan bekatgacha umumiy yurish vaqti o'zgarmaydi."""
    a, b = min(i, j), max(i, j)
    if is_real(st, a) and is_real(st, b):
        return _rt(abs(st[b].km - st[a].km), tr)
    P = a
    while not is_real(st, P):
        P -= 1
    Q = b
    while not is_real(st, Q):
        Q += 1
    full = _rt(st[Q].km - st[P].km, tr)
    return _cum(st, P, Q, b, full) - _cum(st, P, Q, a, full)


def path(st, tr):
    n = len(st)
    return list(range(n)) if tr.direction == 1 else list(range(n - 1, -1, -1))


def is_terminal(st, i):
    return i == 0 or i == len(st) - 1


def free_run(st, tr):
    """To'siqsiz harakatdagi manzilga yetib kelish vaqti."""
    p = path(st, tr)
    t = tr.release
    for k in range(len(p) - 1):
        if k > 0:
            t += tr.stops.get(p[k], 0)
        t += run_time(st, p[k], p[k + 1], tr)
    return t
