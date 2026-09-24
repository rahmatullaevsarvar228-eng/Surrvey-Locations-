# -*- coding: utf-8 -*-
"""Генерирует демо-выгрузку в формате Kobo (лист «data» + вспомогательный лист)
с несколькими «нечестными» интервьюерами — чтобы посмотреть приложение в деле
без реальных данных. Запуск: python tools/make_demo.py demo.xlsx"""
import random
import sys

import pandas as pd

random.seed(7)
BRANDS = ["Uzum Bank", "Узум", "uzum", "TBC", "тбс банк", "Kapitalbank", "Капитал", "Payme", "Click",
          "Agrobank", "Anor bank", "Hamkor", "Xalq banki", "Ipoteka", "NBU"]
CITIES = {"г. Ташкент": 6, "Самарканд": 3, "Бухара": 2, "Фергана": 2, "Нукус": 1}
NAMES = ["Азиз", "Дилноза", "Шахзод", "Малика", "Бобур", "Нигора", "Жасур", "Сардор", "Камола", "Улугбек",
         "Зарина", "Отабек", "Гулноза", "Фаррух", "Севара", "Тимур", "Мадина", "Рустам", "Лола", "Икром"]
SURNAMES = ["Каримов", "Юсупова", "Рахимов", "Алиева", "Турсунов", "Норматова", "Исмоилов", "Хасанова",
            "Абдуллаев", "Мирзаева", "Холматов", "Саидова", "Эргашев", "Назарова", "Усмонов", "Қодирова",
            "Бекмуродов", "Жўраева", "Шарипов", "Ахмедова", "Раҳмонов", "Собирова", "Олимов", "Тошпўлатова"]


def main(out):
    rows, rid = [], 5000
    inter_no = 0
    for city, n_inter in CITIES.items():
        for _ in range(n_inter):
            inter_no += 1
            code = f"Inter {inter_no:02d}"
            device = f"collect:{random.randrange(10**15, 10**16)}"
            cheater = inter_no in (3, 8)            # конвейер, короткие, один бренд
            lazy = inter_no == 11                   # слабый зондаж
            day = pd.Timestamp("2025-09-15 09:00")
            t = day + pd.Timedelta(minutes=random.randint(0, 40))
            for k in range(random.randint(18, 34)):
                if cheater and k > 8:
                    dur = random.uniform(2.5, 4.5)
                    gap = random.uniform(0.3, 1.5)
                else:
                    dur = random.uniform(9, 24)
                    gap = random.uniform(4, 25)
                if k and k % 11 == 0:
                    t = t.normalize() + pd.Timedelta(days=1, hours=9)
                if inter_no == 5 and k == 3:
                    t = t.normalize() + pd.Timedelta(hours=1, minutes=40)   # ночная анкета
                start, end = t, t + pd.Timedelta(minutes=dur)
                t = end + pd.Timedelta(minutes=gap)
                if cheater:
                    tom = ["Uzum Bank", "Узум", "uzum bank", "Payme"][: random.randint(2, 4)]
                elif lazy:
                    tom = random.sample(BRANDS, random.randint(1, 2))
                else:
                    tom = random.sample(BRANDS, random.randint(3, 6))
                if random.random() < 0.06:
                    tom = ["не знаю"]
                tom += [None] * (7 - len(tom))
                age = random.randint(18, 65)
                phone = f"+998 9{random.randint(0, 9)} {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"
                name = f"{random.choice(NAMES)} {random.choice(SURNAMES)}"
                if inter_no == 6 and k in (4, 5):
                    phone, name = "+998 90 555-12-34", "Дилноза Юсупова"          # дубликат респондента
                income = 0 if age < 18 else random.choice([0, 1, 2, 3])
                if inter_no == 9 and k == 2:
                    age, income = 16, 3                                        # нарушение правила
                rid += 1
                row = {
                    "start": start.strftime("%Y-%m-%dT%H:%M:%S.000+05:00"),
                    "end": end.strftime("%Y-%m-%dT%H:%M:%S.000+05:00"),
                    "deviceid": device, "Город": city, "Код интервьюера": code,
                    "Пол респондента": random.choice(["Мужской", "Женский"]),
                    "Сколько вам полных лет?": age,
                    "1. Название какого банка первым приходит Вам на ум?": tom[0],
                }
                for j in range(2, 8):
                    row[f"2.{j}. А ещё какой банк?"] = tom[j - 1]
                row["Доход (1-3)"] = income
                row["Скажите пожалуйста как вас зовут?"] = name
                row["Номер телефона респондента"] = phone if random.random() > 0.05 else None
                row["_id"] = rid
                rows.append(row)
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(out) as w:
        df.to_excel(w, sheet_name="data", index=False)
        df.groupby("Город").size().rename("Анкет").to_frame().to_excel(w, sheet_name="Свод")
    print(f"{out}: {len(df)} анкет")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo.xlsx")
