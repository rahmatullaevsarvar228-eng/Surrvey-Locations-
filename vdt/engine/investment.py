"""'Yangi razyezd qayerda?' — investitsiya simulyatori (ilmiy protokol bilan)."""
from .model import Station
from .optimizer import optimise, objective_value


def _best_of_seeds(st, trains, objective, time_limit, seeds, hint, workers=8):
    best = hint
    for sd in seeds:
        ok, sc, _ = optimise(st, trains, objective=objective, time_limit=time_limit,
                             seed=sd, extra_hint=best, workers=workers)
        if ok and (best is None or objective_value(st, trains, sc, objective)
                   < objective_value(st, trains, best, objective)):
            best = sc
    return best


def investment_ranking(st, trains, objective="umumiy", time_limit=60.0,
                       base_time_limit=120.0, seeds=(1, 2, 3), workers=8, progress=None):
    """
    Har bir oraliq bekatga +1 yo'l qo'shib, AI natijasini qayta hisoblaydi. Ilmiy protokol:
      1) Asosiy yechim har bir variantga boshlang'ich reja sifatida beriladi —
         tejash hech qachon manfiy bo'lmaydi (qo'shimcha yo'l zarar qilmaydi).
      2) NAZORAT GURUHI: yangi yo'lsiz, xuddi shu vaqt va seed'lar bilan qayta hisob.
         Aks holda "tejash" yangi yo'ldan emas, qo'shimcha hisob vaqtidan chiqishi mumkin.
      3) Shovqin chegarasi = nazorat guruhida topilgan yaxshilanish. Undan kichik farq
         "sezilarli emas" deb belgilanadi.
    """
    ok, base0, _ = optimise(st, trains, objective=objective, time_limit=base_time_limit,
                            workers=workers)
    v0 = objective_value(st, trains, base0, objective)
    ctrl = _best_of_seeds(st, trains, objective, time_limit, seeds, base0, workers)
    base_val = objective_value(st, trains, ctrl, objective)
    noise = v0 - base_val
    out = []
    for i in range(1, len(st) - 1):
        st2 = [Station(s.name, s.km, s.tracks + (1 if j == i else 0)) for j, s in enumerate(st)]
        sc = _best_of_seeds(st2, trains, objective, time_limit, seeds, ctrl, workers)
        gain = base_val - objective_value(st2, trains, sc, objective)
        out.append(dict(bekat=st[i].name, yollar=st[i].tracks, tejaldi_daq=gain,
                        sezilarli=gain > max(noise, 1)))
        if progress:
            progress(i, out[-1])
    return dict(asosiy_qiymat=base_val, boshlangich_qiymat=v0, shovqin_chegarasi=noise,
                reyting=sorted(out, key=lambda x: -x["tejaldi_daq"]))
