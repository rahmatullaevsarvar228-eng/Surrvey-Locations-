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


@dataclass
class Train:
    id: str
    kind: str                    # "yuk" | "yolovchi" | "tezyurar"
    direction: int               # +1 = A→B, -1 = B→A
    speed: float                 # km/soat
    release: int                 # boshlang'ich bekatdan eng erta jo'nash, daqiqa
    weight: int                  # ustuvorlik vazni
    stops: dict = field(default_factory=dict)   # bekat indeksi -> minimal turish, daqiqa


def run_time(st, i, j, tr):
    return max(1, math.ceil(abs(st[j].km - st[i].km) / tr.speed * 60))


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
