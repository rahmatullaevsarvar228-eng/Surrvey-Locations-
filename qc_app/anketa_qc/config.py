# -*- coding: utf-8 -*-
"""Настройки проекта (сопоставление колонок, пороги, правила, список значений)
и «умные» подсказки колонок по умолчанию.

Настройки — обычный JSON-совместимый dict: так их легко сохранить в SQLite,
передать в интерфейс и обратно без отдельной схемы сериализации.
"""
import re
import copy

# Роли колонок. required=True — без неё проверки не запускаются.
ROLES = [
    # Нет Device ID — цепочка по времени строится по интервьюеру
    dict(key="device", label="Device ID (телефон)", required=False,
         patterns=["deviceid", "device_id", "device id", "imei"]),
    dict(key="start", label="Старт анкеты", required=True,
         patterns=["start", "начало", "boshlanish"]),
    dict(key="end", label="Финиш анкеты", required=True,
         patterns=["end", "оконч", "tugash"]),
    dict(key="city", label="Город / регион", required=True,
         patterns=["город", "shahar", "shahr", "city", "регион", "hudud"]),
    dict(key="inter", label="Код интервьюера", required=True,
         patterns=["код интервьюера", "интервьюер", "interviewer", "intervyuer", "inter"]),
    dict(key="id", label="ID анкеты", required=False,
         patterns=["_id", "id анкеты", "anketa"]),
    dict(key="phone", label="Телефон респондента", required=False,
         patterns=["телефон", "phone", "telefon"]),
    dict(key="name", label="ФИО респондента", required=False,
         patterns=["как вас зовут", "фио", "имя респондента", "ismingiz", "respondent name", "имя"]),
    dict(key="lat", label="GPS: широта", required=False,
         patterns=["_latitude", "latitude", "широта", "kenglik"]),
    dict(key="lon", label="GPS: долгота", required=False,
         patterns=["_longitude", "longitude", "долгота", "uzunlik"]),
]
ROLE_KEYS = [r["key"] for r in ROLES]
REQUIRED_ROLES = [r["key"] for r in ROLES if r["required"]]

# Заглушки «не знаю» в открытых вопросах — из main.py. Точные строки, чтобы не
# задеть реальные названия (например «Xazna»), плюс подстроки для семейства
# «больше не знаю» с десятками вариантов написания.
DEFAULT_INVALID_EXACT = [
    "999", "99", "0", "-", "—",
    "не знаю", "незнаю", "н е знаю", "нет знаю",
    "нет", "yoq", "йук", "не помню",
]
DEFAULT_INVALID_SUBSTR = [
    "билма", "bilma", "незна", "не знае", "не знат", "бильма",
    "курмаган", "kurmagan", "ko'rmagan", "kormagan", "koʻrmagan",
    "не знаю", "не знают",
]

DEFAULT_CONFIG = {
    "sheet": None,
    "mapping": {k: None for k in ROLE_KEYS},
    # Колонки-признаки «интервью дошло до конца» (например ФИО/телефон в конце
    # анкеты). Пусто — все анкеты считаются завершёнными.
    "completed_cols": [],
    "thresholds": {
        "min_interval_min": 2,
        "min_duration_min": 5,
        "max_duration_min": 30,
        "max_share_city_pct": 50,
        "min_inters_per_city": 2,
        "mass_window_min": 10,
        "mass_min_count": 6,
        "phone_missing_city_pct": 20,
        # «массовое открытие»: столько анкет открыто на одном устройстве за
        # mass_open_sec секунд — анкеты открыли заранее и заполняют потом
        "mass_open_sec": 120,
        "mass_open_count": 3,
    },
    # Технические записи (видео/фото по заданию, не интервью): колонка и её
    # значения. Такие записи не проверяются как интервью и не идут в квоты.
    "technical": {"col": None, "values": [], "mode": "values", "auto": True},
    # Блоки анкеты: [{"name", "start": колонка, "required": bool, "grid": bool}].
    # Пусто — берутся группы Kobo из заголовков («grp/вопрос»).
    "sections": [],
    # Брак, уже отмеченный вручную (группа мониторинга по аудио ставит «1»):
    # колонка и значения; auto — найти колонку самому.
    "rejected": {"col": None, "values": ["1"], "auto": True},
    "night": {"enabled": True, "work_start_hour": 7, "work_end_hour": 22, "severity": "warning"},
    "duplicates": {"phone_severity": "defect", "name_severity": "warning"},
    "probing": {
        "blocks": [],            # [{"label", "columns": [...], "min_n"}]
        "severity": "warning",   # анкета ниже минимума в блоке
        "low_avg_pct": 70,       # интервьюер ниже X% медианы волны по числу ответов
        "low_avg_severity": "defect",
        "invalid_exact": list(DEFAULT_INVALID_EXACT),
        "invalid_substr": list(DEFAULT_INVALID_SUBSTR),
    },
    "rules": [],                 # см. engine.check_rules
    "repetition": {
        "columns": [],
        "values": [],            # [{"name": "Uzum Bank", "variants": ["uzum", "узум"]}]
        "red_pct": 70, "red_min_n": 10,
        "yellow_pct": 50, "yellow_min_n": 5,
    },
    "status": {"red_pct": 50, "yellow_pct": 20},
    "geo": {
        "max_dist_km": 2.0,          # дальше от плановой точки — отмечаем
        "max_per_point": 20,         # максимум анкет интервьюера в одном месте
        "min_sep_km": 1.5,           # радиус «одного места» для скоплений
        "same_point_min": 3,         # столько анкет с одинаковыми координатами — подозрительно
        "far_severity": "warning",
        "cluster_severity": "warning",
        "same_severity": "warning",
        "no_gps_severity": "warning",
        "max_speed_kmh": 60,         # «телепорт»: быстрее этого между анкетами не переместиться
        "min_jump_km": 1.0,
        "jump_severity": "warning",
        # «не в своём городе»: дальше границы города (радиус из справочника
        # городов или по плановым точкам + запас)
        "city_check": True,
        "city_margin_km": 2.0,
        "city_severity": "defect",
        "plan": {},                  # {город: {"points": [{lat, lon, street_ru}]}}
    },
    "quotas": {"by_city": True, "dims": [], "plan": []},
    # Международные методы контроля: копии анкет (percent match), время по
    # блокам (поля-отметки времени в форме), необычные ответы интервьюера.
    "quality": {"near_dup": True, "near_dup_pct": 85, "near_dup_min_q": 15, "near_dup_severity": "warning",
                "near_dup_defect_pct": 95,
                "block_fast_pct": 25, "block_severity": "warning", "patterns": True},
    # Выборка на прослушку аудио: доля случайных анкет у каждого интервьюера
    "listen": {"base_pct": 5, "new_pct": 15, "risk_pct": 20},
    # Норма анкет в день на интервьюера (засчитанных, без брака); 0 — не задана.
    # team — список кодов интервьюеров, чтобы видеть и тех, кто ничего не прислал.
    "daily": {"min": 0, "team": []},
    "remote_sources": [],        # ID таблиц Google Sheets проекта на сервере доступа
    "source_sheets": {},         # {ID таблицы: лист, который проверять}; пусто — лист по умолчанию
    # Технические задания на отдельном листе / в отдельной таблице
    "tech_tabs": {},             # {ID таблицы: лист с ТЗ}
    "tech_sources": [],          # ID таблиц, где только ТЗ
    "tech_sheet": None,          # лист с ТЗ в файле Excel
    "auto_refresh_min": 15,      # автообновление анкет из таблиц, 0 — выключено
}


def default_config():
    return copy.deepcopy(DEFAULT_CONFIG)


def merge_config(saved):
    """Накладывает сохранённые настройки на значения по умолчанию — чтобы
    конфиг из старой версии приложения не падал на новых ключах."""
    cfg = default_config()
    if not saved:
        return cfg
    for key, val in saved.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    return cfg


def _tokens(text):
    return [t for t in re.split(r"[^0-9a-zа-яёʻ'ғқҳў]+", text) if t]


def smart_default(columns, patterns):
    """Точное совпадение названия; затем длинный образец внутри названия
    («код интервьюера» в «Код интервьюера (2 цифры)»); короткий («end»,
    «start», «inter», «city») — только целым словом, иначе «end» найдётся в
    «Gender» или «Recommend», а «city» — в «Electricity»."""
    lowered = [(c, str(c).strip().lower()) for c in columns]
    for p in patterns:
        for c, cl in lowered:
            if cl == p:
                return c
    for c, cl in lowered:
        toks = _tokens(cl)
        for p in patterns:
            if len(p.strip("_ ")) <= 5:
                if p.strip("_ ") in toks:
                    return c
            elif p in cl:
                return c
    return None


def suggest_mapping(columns, current=None):
    """Подсказки по умолчанию; уже выбранные пользователем колонки, которые
    есть в файле, не трогаем."""
    current = current or {}
    out = {}
    for role in ROLES:
        cur = current.get(role["key"])
        out[role["key"]] = cur if cur in columns else smart_default(columns, role["patterns"])
    return out


def missing_required(mapping):
    labels = {r["key"]: r["label"] for r in ROLES}
    return [labels[k] for k in REQUIRED_ROLES if not mapping.get(k)]
