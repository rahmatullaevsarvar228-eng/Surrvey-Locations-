# -*- coding: utf-8 -*-
"""Настройки проекта (сопоставление колонок, пороги, правила, список значений)
и «умные» подсказки колонок по умолчанию.

Настройки — обычный JSON-совместимый dict: так их легко сохранить в SQLite,
передать в интерфейс и обратно без отдельной схемы сериализации.
"""
import copy

# Роли колонок. required=True — без неё проверки не запускаются.
ROLES = [
    dict(key="device", label="Device ID", required=True,
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
         patterns=["как вас зовут", "фио", "имя респондента", "ismingiz", "name"]),
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
    },
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
    "remote_sources": [],        # ID таблиц Google Sheets проекта на сервере доступа
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


def smart_default(columns, patterns):
    lowered = [(c, str(c).lower()) for c in columns]
    for p in patterns:
        for c, cl in lowered:
            if cl == p:
                return c
    for c, cl in lowered:
        for p in patterns:
            if p in cl:
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
