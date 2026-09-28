# -*- coding: utf-8 -*-
"""Логика ответов: респондент сначала сказал одно, потом другое.

Это не брак, а «сомнительно»: люди путаются, интервьюер мог ошибиться при
вводе. Но если таких анкет много у одного интервьюера — повод послушать аудио.

Две проверки, которые работают без настройки на любом проекте Kobo:

1. «Сам назвал, а потом сказал «не знаю»». В начале анкеты респондент сам
   называет банки/бренды (открытые вопросы), а позже в списке «Знаю / Не
   знаю» говорит, что этот бренд не знает. Список узнаём по ответам
   (только «Знаю»/«Не знаю» или 1/99), название бренда — по заголовку
   колонки; открытые вопросы — текстовые колонки ДО списка.
2. «Ничего из перечисленного» и одновременно другой вариант в вопросе с
   несколькими ответами (колонки Kobo «Вопрос/Вариант» со значениями 0/1).
"""
import re

import pandas as pd

KNOW_YES = {"знаю", "слышал", "слышала", "слышал(а)", "да, знаю", "biladi", "bilaman", "eshitgan", "eshitganman",
            "tanishman", "know", "aware", "yes, know"}
KNOW_NO = {"не знаю", "не слышал", "не слышала", "не слышал(а)", "нет, не знаю", "bilmaydi", "bilmayman",
           "eshitmagan", "eshitmaganman", "don't know", "not aware", "no"}
NONE_OPTION = re.compile(r"ничего из|ни одн|никак|ни один|hech (biri|narsa|qaysi)|none of|не знаю|затрудняюсь|"
                         r"bilmayman|javob berishga qiyin", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")
SUFFIX = re.compile(r"\.\d+$")               # повтор колонки в Kobo: «Uzum Bank.1»
STOP = {"bank", "banki", "банк", "банки", "the", "and", "ooo", "aj", "atb", "ltd", "llc", "app", "ilova"}
KEY_MIN = 3

_TR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
       "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
       "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
       "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "x"}


def norm(text):
    """Латиница в нижнем регистре, без апострофов: «Ипотека банк» → «ipoteka bank».
    h и x считаем одной буквой («Хамкор» = «Hamkor»)."""
    s = TAG.sub(" ", str(text)).lower()
    s = "".join(_TR.get(ch, ch) for ch in s)
    s = re.sub(r"[ʻʼ’‘`']", "", s).replace("h", "x")
    return re.sub(r"[^0-9a-z]+", " ", s).strip()


def brand_label(col):
    name = SUFFIX.sub("", str(col))
    return TAG.sub("", name.split("/")[-1]).strip()


def brand_keys(label):
    """«NBU / Milliy bank» → {nbu, milliy}; «Kapitalbank» → {kapital}."""
    keys = set()
    for w in norm(label).split():
        if w.endswith("bank") and len(w) > 4 + KEY_MIN:
            w = w[:-4]
        if len(w) >= KEY_MIN and w not in STOP and not w.isdigit():
            keys.add(w)
    return keys


def _know_value(v):
    """True — знает, False — не знает, None — не про знание."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return True if v == 1 else False if v == 99 else None
    s = str(v).strip().lower()
    if s in KNOW_YES:
        return True
    if s in KNOW_NO:
        return False
    try:
        f = float(s)
    except ValueError:
        return None
    return True if f == 1 else False if f == 99 else None


def aided_columns(raw, skip=()):
    """Колонки-списки «Знаю / Не знаю» (или 1/99): {колонка: ключи бренда}."""
    out = {}
    for c in raw.columns:
        if c in skip or "/" in str(c) and raw[c].dropna().isin([0, 1, "0", "1"]).all():
            continue
        vals = raw[c].dropna()
        if len(vals) < 5:
            continue
        uniq = set(vals.astype(str).str.strip().str.lower().unique()[:10])
        if len(uniq) > 4:
            continue
        known = vals.map(_know_value)
        if known.isna().any() or known.nunique() < 2:
            continue
        keys = brand_keys(brand_label(c))
        if keys:
            out[c] = keys
    return out


META = re.compile(r"^_|latitude|longitude|altitude|precision|audio|video|url|device|^start$|^end$|^today$|"
                  r"submission|uuid|улиц|mahalla|махал|адрес|manzil|город|shahar|интервьюер|intervyuer|"
                  r"телефон|telefon|зовут|ism", re.IGNORECASE)


def open_columns(raw, before, keys, skip=()):
    """Открытые текстовые вопросы про бренды, заданные раньше списка: в них
    хотя бы 5% ответов называют бренд из списка (улицы, имена и т.п. не
    попадут)."""
    out = []
    for c in list(raw.columns)[:before]:
        if c in skip or META.search(str(c)) or "/" in str(c):
            continue
        vals = raw[c].dropna()
        if len(vals) < 5 or not vals.map(lambda v: isinstance(v, str)).mean() > 0.8 or vals.nunique() < 3:
            continue
        hits = vals.map(lambda v: _mentions(norm(v), keys) is not None).mean()
        if hits >= 0.05:
            out.append(c)
    return out


def _mentions(n, keys):
    """Какой ключ бренда есть в нормализованном ответе (или None)."""
    words, joined = n.split(), n.replace(" ", "")
    for k in keys:
        if any(w == k or w.startswith(k) for w in words) or (len(k) >= 5 and k in joined):
            return k
    return None


def _question_no(col):
    m = re.match(r"\s*(\d+(?:\.\d+)*)", str(col))
    return f"вопрос {m.group(1).rstrip('.')}" if m else f"«{str(col)[:40]}»"


def aware_conflicts(raw, skip=()):
    """{индекс строки: [текст]} — назвал бренд сам, а в списке «не знаю»."""
    aided = aided_columns(raw, skip)
    if not aided:
        return {}
    first = min(list(raw.columns).index(c) for c in aided)
    all_keys = set().union(*aided.values())
    opens = open_columns(raw, first, all_keys, skip)
    if not opens:
        return {}
    # что каждая анкета назвала сама: {строка: [(норм. ответ, колонка, ответ)]}
    said = {}
    for c in opens:
        for i, v in raw[c].dropna().items():
            if isinstance(v, str) and norm(v):
                said.setdefault(i, []).append((norm(v), c, v.strip()))
    out, seen = {}, {}
    # сначала колонки со словами («Не знаю»), потом с кодами 1/99
    order = sorted(aided, key=lambda c: raw[c].dropna().map(lambda v: not isinstance(v, str)).mean())
    for c in order:
        keys = aided[c]
        neg = raw[c].map(_know_value) == False  # noqa: E712
        label = brand_label(c)
        for i in neg[neg].index:
            for n, col, answer in said.get(i, []):
                k = _mentions(n, keys)
                if k is None:
                    continue
                # один бренд — одно противоречие, даже если колонок про него несколько
                if k in seen.setdefault(i, set()):
                    break
                seen[i] |= keys
                out.setdefault(i, []).append(
                    f"сам назвал «{answer}» ({_question_no(col)}), а в списке про «{label}» ответил «{_show(raw.at[i, c])}»")
                break
    return out


def _show(v):
    if isinstance(v, str):
        return v.strip()
    return "не знаю (99)" if v == 99 else str(v)


def none_conflicts(raw, skip=()):
    """{индекс строки: [текст]} — «Ничего из перечисленного» вместе с другим вариантом."""
    groups = {}
    for c in raw.columns:
        s = str(c)
        if c in skip or "/" not in s:
            continue
        vals = raw[c].dropna()
        if not len(vals) or not vals.isin([0, 1, "0", "1", 0.0, 1.0]).all():
            continue
        # «Вопрос/Вариант» (в варианте бывает <span>…</span> со своим «/»)
        q, opt = TAG.sub("", SUFFIX.sub("", s)).split("/", 1)
        groups.setdefault(q.strip(), []).append((c, opt.strip()))
    out = {}
    for q, opts in groups.items():
        nones = [(c, o) for c, o in opts if NONE_OPTION.search(o)]
        others = [(c, o) for c, o in opts if not NONE_OPTION.search(o)]
        if not nones or not others:
            continue
        for nc, nlabel in nones:
            sel = pd.to_numeric(raw[nc], errors="coerce") == 1
            for i in sel[sel].index:
                chosen = [o for c, o in others if pd.to_numeric(pd.Series([raw.at[i, c]]), errors="coerce").iloc[0] == 1]
                if chosen:
                    out.setdefault(i, []).append(
                        f"выбрано «{nlabel}» и одновременно «{chosen[0]}»" + (f" (+{len(chosen) - 1})" if len(chosen) > 1 else ""))
    return out


def conflicts(raw, skip=()):
    out = {}
    for part in (aware_conflicts(raw, skip), none_conflicts(raw, skip)):
        for i, msgs in part.items():
            out.setdefault(i, []).extend(msgs)
    return out
