# -*- coding: utf-8 -*-
"""Блоки анкеты и технические записи.

Блок — часть анкеты (например «Знание банков», «Реклама», «Паспортичка»).
Нужен, чтобы у каждого брака было видно, в каком именно блоке ошибка.
Блоки берутся:
  1. из настроек проекта: [{"name", "start"}] — блок начинается с колонки
     start и идёт до начала следующего блока (в порядке колонок выгрузки);
  2. иначе — из групп Kobo в заголовках («grp_bank/q1» → «grp bank»).
Проблемы, которые не относятся к вопросам (время, устройство, GPS), идут
в служебные разделы.

Техническая запись — анкета, где интервьюер не проводит опрос, а выполняет
задание (например, снимает видео, что рядом нет рекламы). Её не проверяют
как интервью: длительность, интервалы, «конвейер», зондаж и правила к ней
не применяются, в квоты она не идёт.
"""
import re

import pandas as pd

TIME = "Время интервью"
DEVICE = "Устройство и интервьюер"
GPS = "GPS и место опроса"
CONTACTS = "Контакты респондента"
OPEN = "Открытые вопросы"
LOGIC = "Логика анкеты"

CODE_AREA = {
    "no_device": DEVICE, "device_multi_inter": DEVICE, "inter_multi_device": DEVICE,
    "too_long": TIME, "too_short": TIME, "start_gap": TIME, "no_rest": TIME, "conveyor": TIME,
    "overlap": TIME, "mass_open": TIME, "night": TIME,
    "no_gps": GPS, "geo_far": GPS, "geo_cluster": GPS, "geo_same": GPS, "geo_jump": GPS, "geo_city": GPS,
    "probe_low_avg": OPEN,
    "external": "Аудиоконтроль / мониторинг",
    "near_dup": "Ответы анкеты (сравнение с другими)",
    "logic": "Логика ответов",
    "gps_bad": "GPS и место опроса",
    "fast": "Время интервью",
    "screen_fail": "Отбор респондента",
    "logic_dup": "Логика ответов",
    "screenout": "Заполнение анкеты",
    "block_fast": TIME,
}


def _pretty_group(prefix):
    name = prefix.rsplit("/", 1)[-1]
    name = re.sub(r"^(grp|group|gr|block|blok)[_\- ]*", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").strip()
    return name[:1].upper() + name[1:] if name else prefix


def build_sections(columns, cfg):
    """[{"name", "columns", "required", "grid"}] в порядке анкеты."""
    columns = [str(c) for c in columns]
    configured = [s for s in cfg.get("sections") or [] if s.get("name") and s.get("start") in columns]
    if configured:
        pos = {c: i for i, c in enumerate(columns)}
        configured = sorted(configured, key=lambda s: pos[s["start"]])
        out = []
        for k, s in enumerate(configured):
            a = pos[s["start"]]
            b = pos[configured[k + 1]["start"]] if k + 1 < len(configured) else len(columns)
            out.append({"name": s["name"].strip(), "columns": columns[a:b],
                        "required": bool(s.get("required")), "grid": bool(s.get("grid"))})
        return out
    # группы Kobo в заголовках
    out = []
    for c in columns:
        if "/" not in c:
            continue
        name = _pretty_group(c.rsplit("/", 1)[0])
        if out and out[-1]["name"] == name:
            out[-1]["columns"].append(c)
        else:
            out.append({"name": name, "columns": [c], "required": False, "grid": False, "auto": True})
    return out


def section_of(sections):
    m = {}
    for s in sections:
        for c in s["columns"]:
            m.setdefault(c, s["name"])
    return m


def issue_block(code, text, cfg, sec_of):
    """Блок анкеты, к которому относится проблема."""
    if code in CODE_AREA:
        return CODE_AREA[code]
    mapping = cfg["mapping"]
    if code in ("dup_phone", "dup_name"):
        col = mapping.get("phone" if code == "dup_phone" else "name")
        return sec_of.get(col) or CONTACTS
    if code in ("block_empty", "grid_same"):
        return text.split("»")[0].split("«")[-1] if "«" in text else LOGIC
    if code == "probe_depth":
        label = text.split(":")[0]
        for b in cfg["probing"].get("blocks") or []:
            if (b.get("label") or "Блок") == label:
                for c in b.get("columns") or []:
                    if c in sec_of:
                        return sec_of[c]
        return label or OPEN
    if code.startswith("rule:"):
        name = code[5:]
        rule = next((r for r in cfg.get("rules") or [] if (r.get("name") or "").strip() == name), None)
        if rule:
            for c in (rule.get("then_col"), rule.get("if_col")):
                if c in sec_of:
                    return sec_of[c]
        return LOGIC
    return LOGIC


# ─────────────────────────────────────────────────────────────────────────
# Технические записи
# ─────────────────────────────────────────────────────────────────────────
# Значения, означающие техническую запись. Без голого «тех»/«texn» — иначе
# профессия «Техник» в анкете стала бы техническим заданием.
TECH_HINTS = ("техническ", "тех. зад", "тех.зад", "тех зад", "техзад", "texnik vazifa", "texnik topshiriq",
              "technical", "задани", "vazifa", "topshiriq", "топшир", "вазифа", "видео", "video",
              "съёмк", "съемк", "suratga", "ролик", "фотоотч", "фото отч")
# Короткие обозначения — только целым словом («тз» есть и внутри «отзыв»).
TECH_TOKENS = {"тз", "т.з", "т.з.", "tz", "t.z", "t.z.", "ts"}
MEDIA_EXT = re.compile(r"\.(mp4|mov|3gp|webm|avi|mkv|m4v)$", re.IGNORECASE)
# Отдельный лист / таблица с техническими заданиями: программа ставит такой
# отметку при объединении с анкетами.
TECH_SHEET_COL = "Техническое задание (отдельный лист)"


def is_tech_value(v):
    s = str(v).strip().lower()
    if any(h in s for h in TECH_HINTS):
        return True
    return any(t in TECH_TOKENS for t in re.split(r"[\s,;:()/«»\"'-]+", s))


NAME_HINTS = ("тип", "type", "tur", "вид", "техн", "texn", "techn", "задани", "vazifa", "topshiriq", "топшир", "вазифа",
              "анкета тури", "режим", "формат анкет",
              "запис", "формат", "video", "видео")
# Названия, по которым колонку можно взять автоматически, без вопроса:
# явно служебные («Тип записи», «Вид работы», «Задание»…). По «Тип жилья» или
# «Вид рекламы» — только подсказка.
NAME_STRONG = ("тип запис", "тип анкет", "тип форм", "тип работ", "вид запис", "вид работ", "вид задан", "вид анкет",
               "record type", "form type", "anketa turi", "анкета тури", "ish turi", "задани", "техническ",
               "texnik", "vazifa", "topshiriq", "топшир", "вазифа", "режим")
# Колонка с файлом видео/фото по заданию: если заполнена — это техническая запись.
MEDIA_NAME_HINTS = ("видео", "video", "техн", "texn", "задани", "vazifa", "topshiriq", "reklama yo", "нет рекламы")


def technical_candidates(raw):
    """Колонки, похожие на признак технической записи:
      - «тип записи: Интервью / Техническое задание (видео)» — режим values;
      - колонка файла видео по заданию, заполненная только у части строк —
        режим filled (заполнено → техническая запись).
    Возвращает [{"col", "mode", "values", "n", "sure"}]; sure — в названии
    колонки есть явный признак, такую можно применять автоматически."""
    out = []
    n_rows = max(len(raw), 1)
    for c in raw.columns:
        s = raw[c].dropna()
        if s.empty:
            continue
        name = str(c).lower()
        vals = s.astype(str).str.strip()
        vals = vals[vals != ""]
        uniq = vals.value_counts()
        name_hint = any(h in name for h in NAME_HINTS)
        name_sure = any(h in name for h in NAME_STRONG) or bool(re.search(r"(^|[^а-яa-z])тз([^а-яa-z]|$)", name))
        if 2 <= len(uniq) <= 8:
            hits = [v for v in uniq.index if is_tech_value(v)]
            if hits and len(hits) < len(uniq):
                out.append({"col": str(c), "mode": "values", "values": hits, "n": int(uniq[hits].sum()),
                            "sure": name_sure, "score": int(uniq[hits].sum()) + (10_000 if name_sure else 1_000 if name_hint else 0)})
                continue
        share = len(vals) / n_rows
        is_video = vals.map(lambda v: bool(MEDIA_EXT.search(v))).mean() > 0.8
        if (any(h in name for h in MEDIA_NAME_HINTS) or is_video) and 0 < share < 0.6 and len(uniq) > 0.5 * len(vals):
            # почти все значения разные (имена файлов) и заполнено не у всех
            out.append({"col": str(c), "mode": "filled", "values": [], "n": int(len(vals)),
                        "sure": True, "score": int(len(vals)) + 5_000})
    out.sort(key=lambda x: -x["score"])
    for x in out:
        x.pop("score")
    return out


def suggest_technical(raw, limit=3):
    return technical_candidates(raw)[:limit]


def resolve_technical(raw, cfg):
    """(маска технических записей, описание откуда она взялась или None).

    Если руководитель сам выбрал колонку — берём её. Иначе (auto, по
    умолчанию) — первую «уверенную» подсказку: колонку типа записи или
    колонку видео по заданию. Колонку ответа вроде «Где видели рекламу:
    видео в интернете» автоматически не берём — у неё нет признака в
    названии."""
    t = cfg.get("technical") or {}
    # Технические задания с отдельного листа/таблицы — отмечены программой
    extra = (raw[TECH_SHEET_COL].notna() if TECH_SHEET_COL in raw.columns
             else pd.Series(False, index=raw.index)).astype(bool)
    mask, info = _resolve_technical_col(raw, t)
    if extra.any():
        mask = mask | extra
        info = dict(info or {}, n=int(mask.sum()), sheet_rows=int(extra.sum()))
        info.setdefault("col", TECH_SHEET_COL)
        info.setdefault("auto", True)
        info.setdefault("mode", "sheet")
        info.setdefault("values", [])
    return mask, info


def _resolve_technical_col(raw, t):
    col, mode = t.get("col"), t.get("mode") or "values"
    values = [str(v).strip().lower() for v in t.get("values") or [] if str(v).strip()]
    auto = False
    if not col and t.get("auto", True):
        sure = [x for x in technical_candidates(raw) if x["sure"]]
        if sure:
            col, mode, values, auto = sure[0]["col"], sure[0]["mode"], [v.lower() for v in sure[0]["values"]], True
    if not col or col not in raw.columns or (mode == "values" and not values):
        return pd.Series(False, index=raw.index), None
    if mode == "filled":
        mask = raw[col].map(lambda v: pd.notna(v) and str(v).strip() != "")
    else:
        mask = raw[col].map(lambda v: str(v).strip().lower() in values if pd.notna(v) else False)
    mask = mask.astype(bool)
    return mask, {"col": str(col), "mode": mode, "values": sorted({str(v) for v in raw.loc[mask, col].dropna()})[:5]
                  if mode == "values" else [], "n": int(mask.sum()), "auto": auto}


def technical_mask(raw, cfg):
    return resolve_technical(raw, cfg)[0]


# ─────────────────────────────────────────────────────────────────────────
# Брак, уже отмеченный вручную (группа мониторинга по аудиозаписи и т.п.)
# ─────────────────────────────────────────────────────────────────────────
# «брак» — но не «в браке»; «ОТК» — отдельным словом, не «отказ».
REJECT_NAME_RE = re.compile(r"(брак(?!е|ом|а\b)|\bbrak|аудио|audio|мониторинг|monitoring|прослуш|(^|[^а-я])отк([^а-я]|$)|"
                            r"nuqson|yaroqsiz|reject)", re.IGNORECASE)
# Похоже на вопрос респонденту, а не на служебную отметку
QUESTION_RE = re.compile(r"(\?|браке|замуж|женат|семейн|супруг|oila|turmush)", re.IGNORECASE)
# Автоматически принимаем только явную отметку «1»/«брак»; «да» — нет:
# «да» бывает ответом респондента.
REJECT_AUTO_YES = ("1", "брак", "x", "х", "+")
REJECT_YES = ("1", "да", "брак", "yes", "x", "х", "+", "true", "ha")
REJECT_NO = ("0", "нет", "no", "-", "false", "yo'q", "yoq", "норма", "ок", "ok")


def _norm_mark(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip().lower()
    return s[:-2] if s.endswith(".0") else s


def rejected_candidates(raw, skip=()):
    """Колонки, куда вручную ставят «1» = брак: в названии есть «брак»,
    «аудио», «мониторинг»… (но не вопрос вроде «Состоите ли вы в браке?»),
    значения — только 1/брак (и пусто/0/нет), помечено меньше 30% анкет."""
    out = []
    n_rows = max(len(raw), 1)
    for c in raw.columns:
        if c in skip:
            continue
        name = str(c).lower()
        if not REJECT_NAME_RE.search(name) or QUESTION_RE.search(name):
            continue
        vals = raw[c].map(_norm_mark)
        filled = vals[vals != ""]
        if filled.empty:
            continue
        yes = filled[filled.isin(REJECT_AUTO_YES)]
        # Мониторинг бракует меньшинство анкет; если «1» у трети и больше — это,
        # скорее всего, ответ на вопрос («Брак зарегистрирован: 1/0»), а не отметка.
        if yes.empty or not filled.isin(REJECT_YES + REJECT_NO).all() or len(yes) / n_rows >= 0.3:
            continue
        out.append({"col": str(c), "values": sorted(set(yes)), "n": int(len(yes))})
    out.sort(key=lambda x: -x["n"])
    return out


def resolve_rejected(raw, cfg, skip=()):
    """(маска анкет, уже забракованных вручную, описание или None)."""
    r = cfg.get("rejected") or {}
    col = r.get("col")
    values = [_norm_mark(v) for v in r.get("values") or []] or list(REJECT_YES)
    auto = False
    if not col and r.get("auto", True):
        cand = rejected_candidates(raw, skip)
        if cand:
            col, values, auto = cand[0]["col"], cand[0]["values"], True
    if not col or col not in raw.columns:
        return pd.Series(False, index=raw.index), None
    mask = raw[col].map(_norm_mark).isin(values)
    return mask.astype(bool), {"col": str(col), "values": values, "n": int(mask.sum()), "auto": auto}
