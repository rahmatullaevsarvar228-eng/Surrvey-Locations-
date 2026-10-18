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
    kind: str = "bekat"          # "bekat" | "obgon" — peregon o'rtasidagi quvib o'tish punkti


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


def run_time(st, i, j, tr):
    """Peregondagi yurish vaqti. Obgon punkti peregonni ikkiga bo'ladi, lekin umumiy yurish
    vaqti o'zgarmaydi (yaxlitlash qo'shimcha daqiqa bermasligi uchun)."""
    a, b = min(i, j), max(i, j)
    if st[b].kind == "obgon" and b + 1 < len(st):          # a — bekat, b — obgon
        full = _rt(st[b + 1].km - st[a].km, tr)
        f = (st[b].km - st[a].km) / (st[b + 1].km - st[a].km)
        return max(1, min(full - 1, round(full * f)))
    if st[a].kind == "obgon" and a - 1 >= 0:               # a — obgon, b — bekat
        full = _rt(st[b].km - st[a - 1].km, tr)
        f = (st[a].km - st[a - 1].km) / (st[b].km - st[a - 1].km)
        return full - max(1, min(full - 1, round(full * f)))
    return _rt(abs(st[j].km - st[i].km), tr)


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
