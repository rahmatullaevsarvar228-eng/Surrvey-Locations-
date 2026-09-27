# -*- coding: utf-8 -*-
"""Полевой тест на НАСТОЯЩИХ ответах людей.

Берём реальные наборы ответов (открытые данные из R-пакетов psych и Zelig,
идут в пакете pydataset): ответы живых респондентов остаются как есть.
Поверх них моделируем «поле» в формате выгрузки Kobo: интервьюеры, телефоны,
время, GPS по городам Узбекистана, технические задания (видео) между
интервью, отметки группы мониторинга. Части интервьюеров подмешиваем
известные нарушения, остальных не трогаем — и проверяем:
  * ловит ли программа каждое нарушение (полнота);
  * не бракует ли честных (ложные тревоги).

Запуск: pip download --no-deps pydataset && python tools/field_test.py <папка с resources>
"""
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anketa_qc import config, engine  # noqa: E402

PLAN = json.loads((Path(__file__).resolve().parents[1] / "anketa_qc" / "geo_plan_default.json").read_text("utf-8"))
CITIES = ["Ташкент", "Самарканд", "Бухара", "Фергана", "Ургенч", "Нукус"]

# Нарушения по интервьюерам: код → что делает
FRAUD = {
    "copy": "копирует анкеты (свои прошлые целиком, меняя 1–2 ответа)",
    "fabricate": "придумывает ответы сам (почти всё одно и то же)",
    "speed": "проводит интервью за 2–4 минуты",
    "home": "сидит дома за городом",
    "batch": "открывает анкеты пачкой и заполняет параллельно",
}


def load_real(res, name):
    path = {"bfi": "psych/bfi.csv", "epi": "psych/epi.csv", "msq": "psych/msq.csv",
            "mexico": "Zelig/mexico.csv"}[name]
    df = pd.read_csv(Path(res) / "rdata" / "csv" / path)
    df = df.drop(columns=[c for c in df.columns if c.lower().startswith("unnamed") or c in ("X", "rownames")],
                 errors="ignore")
    return df.dropna(thresh=int(df.shape[1] * 0.7)).reset_index(drop=True)


def build_project(real, seed, n_inter=30, duration=(12, 25)):
    """Kobo-подобная выгрузка из реальных ответов + истинные метки нарушений."""
    rnd = random.Random(seed)
    answers = real.sample(frac=1, random_state=seed).reset_index(drop=True)
    inters = [f"Inter {i + 1:02d}" for i in range(n_inter)]
    kinds = list(FRAUD)
    cheat = {inters[i]: kinds[i % len(kinds)] for i in range(len(kinds))}       # по одному на нарушение
    rows, truth = [], {}
    per = len(answers) // n_inter
    rid = 100000
    for n_i, inter in enumerate(inters):
        city = CITIES[n_i % len(CITIES)]
        pts = PLAN[city]["points"]
        dev = f"collect:{rnd.randrange(10 ** 14, 10 ** 15)}"
        kind = cheat.get(inter)
        t = pd.Timestamp("2025-10-06 09:00") + pd.Timedelta(minutes=rnd.randint(0, 40))
        last = None
        batch_start = None
        for k in range(per):
            a = answers.iloc[n_i * per + k].to_dict()
            fraud = None
            # техническое задание (видео) перед каждым 6-м интервью
            if k % 6 == 5:
                rid += 1
                p = pts[(k // 5) % len(pts)]
                rows.append({"_id": rid, "_uuid": f"u{rid}", "start": t.isoformat(), "end": (t + pd.Timedelta(seconds=50)).isoformat(),
                             "deviceid": dev, "Код интервьюера": inter, "Город": city, "Тип записи": "Техническое задание (видео)",
                             "_Координаты_latitude": p["lat"] + rnd.uniform(-0.002, 0.002),
                             "_Координаты_longitude": p["lon"] + rnd.uniform(-0.002, 0.002)})
                t += pd.Timedelta(seconds=50 + rnd.randint(5, 40))          # интервью через 5–40 с после видео
            dur = rnd.uniform(*duration)
            gap = rnd.uniform(4, 20)
            if kind == "speed" and k % 2:
                dur, fraud = rnd.uniform(2, 4), "speed"
            if kind == "copy" and last is not None and k % 3 == 0:
                a = dict(last)
                for col in rnd.sample(list(a), 2):
                    a[col] = answers.iloc[rnd.randrange(len(answers))][col]
                fraud = "copy"
            if kind == "fabricate" and k % 2:
                mode = {c: answers[c].mode().iloc[0] for c in answers.columns}
                a = {c: (mode[c] if rnd.random() < 0.9 else a[c]) for c in a}
                fraud = "fabricate"
            start, end = t, t + pd.Timedelta(minutes=dur)
            if kind == "batch" and 8 <= k <= 11:
                batch_start = batch_start or t
                start = batch_start + pd.Timedelta(seconds=25 * (k - 8))
                end = start + pd.Timedelta(minutes=12 + 8 * (k - 8))
                fraud = "batch"
            t = max(t, end) + pd.Timedelta(minutes=gap)
            if (k + 1) % 9 == 0:                       # следующий рабочий день
                t = (t.normalize() + pd.Timedelta(days=1, hours=9, minutes=rnd.randint(0, 40)))
            p = pts[(k // 5) % len(pts)]
            lat, lon = p["lat"] + rnd.uniform(-0.004, 0.004), p["lon"] + rnd.uniform(-0.004, 0.004)
            if kind == "home" and k % 2:
                lat, lon, fraud = pts[0]["lat"] + 0.2, pts[0]["lon"] + 0.2, "home"
            rid += 1
            row = {"_id": rid, "_uuid": f"u{rid}", "start": start.isoformat(), "end": end.isoformat(),
                   "_submission_time": (end + pd.Timedelta(minutes=rnd.randint(1, 90))).isoformat(),
                   "deviceid": dev, "Код интервьюера": inter, "Город": city, "Тип записи": "Интервью",
                   "Номер телефона респондента": f"+998 9{rnd.randint(0, 9)} {rnd.randint(1000000, 9999999)}",
                   "_Координаты_latitude": lat, "_Координаты_longitude": lon,
                   "Брак (аудиоконтроль)": 1 if (n_i == 12 and k in (3, 7)) else None}
            row.update({f"{c}": v for c, v in a.items()})
            rows.append(row)
            truth[rid] = fraud or ("monitoring" if row["Брак (аудиоконтроль)"] == 1 else None)
            last = a
    return pd.DataFrame(rows), truth, cheat


def evaluate(name, raw, truth, cheat):
    cfg = config.default_config()
    cfg["mapping"] = config.suggest_mapping(list(raw.columns))
    cfg["geo"]["plan"] = PLAN
    t0 = time.time()
    res = engine.run(raw, cfg)
    sec = time.time() - t0
    df = res["df"]
    df["truth"] = df["row_id"].map(lambda x: truth.get(int(x)) if str(x).isdigit() else None)
    honest = df[~df["technical"] & df["inter"].map(lambda i: i not in cheat)]
    iv = df[~df["technical"]]
    out = {"project": name, "anketas": len(iv), "tech": int(df["technical"].sum()), "sec": round(sec, 1)}
    # ложные тревоги у честных
    codes_h = Counter(c for xs in honest["issues"] for c, s, _ in xs if s == "defect")
    out["honest_defect_pct"] = round(honest["is_defect"].mean() * 100, 2)
    out["honest_defect_codes"] = dict(codes_h.most_common(5))
    # после ТЗ интервью через 5–40 с — не брак
    out["after_tech_flagged"] = int((df["prev_tech"].fillna(False).astype(bool)
                                     & df["issues"].map(lambda xs: any(c in ("no_rest", "start_gap") for c, _, _ in xs))).sum())
    # полнота по видам нарушений
    catch = {}
    for kind in list(FRAUD) + ["monitoring"]:
        sub = iv[iv["truth"] == kind]
        if len(sub):
            flagged = sub["is_defect"] | sub["is_warning"]
            catch[kind] = f"{int(flagged.sum())}/{len(sub)} (брак {int(sub['is_defect'].sum())})"
    out["caught"] = catch
    # статус интервьюеров-нарушителей
    st = {r["Интервьюер"]: r["Статус"] for r in res["interviewers"]}
    out["cheater_status"] = {cheat[i]: st.get(i) for i in cheat}
    out["honest_red"] = sorted(i for i, s in st.items() if s == "RED" and i not in cheat)
    out["patterns"] = [(p["inter"], cheat.get(p["inter"], "честный")) for p in res["answer_patterns"]]
    return out


def main(res):
    report = []
    for seed, name in enumerate(["bfi", "epi", "msq", "mexico"]):
        real = load_real(res, name)
        raw, truth, cheat = build_project(real, seed + 1)
        r = evaluate(name, raw, truth, cheat)
        report.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    main(sys.argv[1])
