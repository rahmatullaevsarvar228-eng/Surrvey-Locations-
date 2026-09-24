# -*- coding: utf-8 -*-
"""GPS-контроль анкет (логика из geo_app.py).

  - анкета слишком далеко от плановой точки опроса своего города;
  - «скопление»: у одного интервьюера в одном месте набралось больше анкет,
    чем разрешено на точку (жадная кластеризация по факту координат);
  - одинаковые до метра координаты в нескольких анкетах одного интервьюера —
    признак копирования анкет или подмены GPS;
  - нет координат в анкете.

План точек хранится в настройках проекта: {город: {"points": [{lat, lon,
street_ru}]}}. Встроенный план (14 городов, 97 точек) — из geo_app.py.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088
DEFAULT_PLAN_FILE = Path(__file__).resolve().parent / "geo_plan_default.json"


def default_plan():
    return json.loads(DEFAULT_PLAN_FILE.read_text(encoding="utf-8"))


def haversine_km(lat1, lon1, lat2, lon2):
    """Расстояние по сфере, векторно на numpy (быстрее geopy на тысячах анкет;
    разница с эллипсоидом — метры, для порогов в километры не важна)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2.0) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_coords(lat_series, lon_series=None):
    """Широта/долгота как числа. Kobo иногда отдаёт одну колонку geopoint
    вида «41.31 69.24 450 5» — тогда достаточно указать её как широту."""
    def num(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return np.nan

    if lon_series is None:
        def split(v):
            parts = _NUM.findall(str(v)) if v is not None else []
            return (num(parts[0]), num(parts[1])) if len(parts) >= 2 else (np.nan, np.nan)
        pairs = lat_series.map(split)
        lat = pairs.map(lambda p: p[0])
        lon = pairs.map(lambda p: p[1])
    else:
        lat, lon = lat_series.map(num), lon_series.map(num)
    bad = ~lat.between(-90, 90) | ~lon.between(-180, 180) | ((lat == 0) & (lon == 0))
    return lat.where(~bad).astype(float), lon.where(~bad).astype(float)


def cluster(lat, lon, min_sep_km):
    """Жадная онлайн-кластеризация (как в geo_app.py): анкета идёт к
    ближайшему скоплению, если до его центра ≤ min_sep_km, иначе создаёт
    новое. Возвращает номер скопления для каждой анкеты и центры."""
    c_lat, c_lon, counts, labels = [], [], [], []
    for la, lo in zip(lat, lon):
        if c_lat:
            d = haversine_km(la, lo, np.array(c_lat), np.array(c_lon))
            i = int(np.argmin(d))
            if d[i] <= min_sep_km:
                n = counts[i]
                c_lat[i] = (c_lat[i] * n + la) / (n + 1)
                c_lon[i] = (c_lon[i] * n + lo) / (n + 1)
                counts[i] += 1
                labels.append(i)
                continue
        c_lat.append(la)
        c_lon.append(lo)
        counts.append(1)
        labels.append(len(counts) - 1)
    return labels, list(zip(c_lat, c_lon, counts))


def _plan_lookup(plan):
    return {str(city).strip().lower(): (city, data.get("points") or []) for city, data in (plan or {}).items()}


def check(df, cfg, add):
    """Добавляет GPS-проблемы к анкетам через add(mask, code, severity, text_fn)
    и возвращает сводку для интерфейса. df уже отсортирован движком."""
    g = cfg["geo"]
    has_gps = df["lat"].notna() & df["lon"].notna()
    add(~has_gps, "no_gps", g.get("no_gps_severity", "warning"), lambda i: "нет GPS-координат")

    plan = _plan_lookup(g.get("plan"))
    max_dist = float(g.get("max_dist_km", 2.0))
    df["geo_dist"] = np.nan
    df["geo_point"] = None
    unmatched = set()
    for city, grp in df[has_gps].groupby("city"):
        found = plan.get(str(city).strip().lower())
        if not found or not found[1]:
            unmatched.add(city)
            continue
        pts = found[1]
        p_lat = np.array([float(p["lat"]) for p in pts])
        p_lon = np.array([float(p["lon"]) for p in pts])
        labels = [p.get("street_ru") or p.get("name") or f"Точка {k + 1}" for k, p in enumerate(pts)]
        dist = haversine_km(grp["lat"].to_numpy()[:, None], grp["lon"].to_numpy()[:, None],
                            p_lat[None, :], p_lon[None, :])
        best = dist.argmin(axis=1)
        df.loc[grp.index, "geo_dist"] = dist[np.arange(len(grp)), best]
        df.loc[grp.index, "geo_point"] = [labels[b] for b in best]
    far = df["geo_dist"] > max_dist
    add(far, "geo_far", g.get("far_severity", "warning"),
        lambda i: f"в {df.at[i, 'geo_dist']:.1f} км от ближайшей точки опроса «{df.at[i, 'geo_point']}» "
                  f"(> {max_dist:g} км)")

    # скопления по факту координат — у каждого интервьюера в каждом городе
    max_per_point = int(g.get("max_per_point", 20))
    min_sep = float(g.get("min_sep_km", 1.5))
    clusters = []
    df["geo_cluster_n"] = 0
    for (city, inter), grp in df[has_gps].sort_values("start").groupby(["city", "inter"]):
        lbl, centers = cluster(grp["lat"].to_numpy(), grp["lon"].to_numpy(), min_sep)
        for k, (c_lat, c_lon, n) in enumerate(centers):
            idx = grp.index[np.array(lbl) == k]
            df.loc[idx, "geo_cluster_n"] = n
            clusters.append({"Город": city, "Интервьюер": inter, "Точка": f"Т{k + 1}", "Анкет": n,
                             "Лимит": max_per_point, "Статус": "RED" if n > max_per_point else "GREEN",
                             "lat": round(c_lat, 6), "lon": round(c_lon, 6)})
    add(df["geo_cluster_n"] > max_per_point, "geo_cluster", g.get("cluster_severity", "warning"),
        lambda i: f"скопление: {int(df.at[i, 'geo_cluster_n'])} анкет интервьюера в радиусе "
                  f"{min_sep:g} км (> {max_per_point})")

    # одинаковые до ~1 м координаты у разных анкет одного интервьюера
    same_min = int(g.get("same_point_min", 3))
    key = df["lat"].round(5).astype(str) + "," + df["lon"].round(5).astype(str)
    df["geo_same_n"] = 0
    gps = df[has_gps]
    if len(gps):
        df.loc[gps.index, "geo_same_n"] = gps.groupby([gps["inter"].fillna("—"), key[has_gps]])["row_id"].transform("size")
    add(df["geo_same_n"] >= same_min, "geo_same", g.get("same_severity", "warning"),
        lambda i: f"точно такие же координаты ещё в {int(df.at[i, 'geo_same_n']) - 1} анкет(ах) "
                  f"этого интервьюера — похоже на копирование или подмену GPS")

    points = [{
        "id": r.row_id, "city": r.city, "inter": r.inter, "lat": round(float(r.lat), 6), "lon": round(float(r.lon), 6),
        "dist": None if pd.isna(r.geo_dist) else round(float(r.geo_dist), 2), "point": r.geo_point,
        "far": bool(r.geo_dist > max_dist) if not pd.isna(r.geo_dist) else False,
        "cluster": bool(r.geo_cluster_n > max_per_point), "same": bool(r.geo_same_n >= same_min),
    } for r in df[has_gps].itertuples()]
    return {
        "enabled": True,
        "with_gps": int(has_gps.sum()), "without_gps": int((~has_gps).sum()),
        "far": int(far.sum()), "clusters_over": sum(1 for c in clusters if c["Статус"] == "RED"),
        "same": int((df["geo_same_n"] >= same_min).sum()),
        "max_dist_km": max_dist, "max_per_point": max_per_point, "min_sep_km": min_sep,
        "unmatched_cities": sorted(map(str, unmatched)),
        "plan": {city: data for city, data in (g.get("plan") or {}).items()},
        "points": points,
        "clusters": sorted(clusters, key=lambda c: -c["Анкет"]),
    }


def plan_from_frame(df):
    """План точек из Excel: колонки «Город», «Широта», «Долгота» и
    необязательная «Название»/«Адрес»."""
    cols = {str(c).strip().lower(): c for c in df.columns}

    def pick(*names):
        for n in names:
            for low, orig in cols.items():
                if low == n or low.startswith(n):
                    return orig
        return None
    c_city, c_lat, c_lon = pick("город", "city", "shahar"), pick("широта", "lat"), pick("долгота", "lon")
    c_name = pick("название", "адрес", "точка", "name")
    if not (c_city and c_lat and c_lon):
        raise ValueError("В файле плана нужны колонки «Город», «Широта», «Долгота»")
    plan = {}
    for _, r in df.iterrows():
        try:
            lat, lon = float(str(r[c_lat]).replace(",", ".")), float(str(r[c_lon]).replace(",", "."))
        except ValueError:
            continue
        if pd.isna(r[c_city]) or np.isnan(lat) or np.isnan(lon):
            continue
        city = re.sub(r"^г\.\s*", "", str(r[c_city]).strip())
        point = {"lat": lat, "lon": lon}
        if c_name and not pd.isna(r[c_name]):
            point["street_ru"] = str(r[c_name]).strip()
        plan.setdefault(city, {"points": []})["points"].append(point)
    if not plan:
        raise ValueError("В файле плана не нашлось ни одной точки с координатами")
    return plan
