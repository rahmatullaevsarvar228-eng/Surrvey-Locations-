"""Viloyatlar markazlari (lokatsiya yuborilmasa). Ob-havo 0,1° setkada olinadi — markaz koordinatasi taxminiy."""
from __future__ import annotations

# kalit: (o‘zbekcha, ruscha, lat, lon)
REGIONS: dict[str, tuple[str, str, float, float]] = {
    "qoraqalpogiston": ("Qoraqalpog‘iston (Nukus)", "Каракалпакстан (Нукус)", 42.46, 59.60),
    "xorazm": ("Xorazm (Urganch)", "Хорезм (Ургенч)", 41.55, 60.63),
    "navoiy": ("Navoiy", "Навои", 40.10, 65.37),
    "buxoro": ("Buxoro", "Бухара", 39.77, 64.42),
    "samarqand": ("Samarqand", "Самарканд", 39.65, 66.96),
    "qashqadaryo": ("Qashqadaryo (Qarshi)", "Кашкадарья (Карши)", 38.86, 65.79),
    "surxondaryo": ("Surxondaryo (Termiz)", "Сурхандарья (Термез)", 37.22, 67.28),
    "jizzax": ("Jizzax", "Джизак", 40.12, 67.84),
    "sirdaryo": ("Sirdaryo (Guliston)", "Сырдарья (Гулистан)", 40.49, 68.78),
    "toshkent": ("Toshkent viloyati", "Ташкентская обл.", 41.04, 69.36),
    "namangan": ("Namangan", "Наманган", 41.00, 71.67),
    "andijon": ("Andijon", "Андижан", 40.78, 72.34),
    "fargona": ("Farg‘ona", "Фергана", 40.39, 71.78),
}


def region_name(key: str, lang: str) -> str:
    uz, ru, _, _ = REGIONS[key]
    return ru if lang == "ru" else uz
