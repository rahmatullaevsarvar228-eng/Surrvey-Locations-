# -*- coding: utf-8 -*-
"""Логика ответов: респондент сначала сказал одно, потом другое.

Это не брак, а «сомнительно»: люди путаются, интервьюер мог ошибиться при
вводе. Но если таких анкет много у одного интервьюера — повод послушать аудио.

Проверки, которые работают без настройки на любом проекте Kobo:

1. «Сам назвал, а потом сказал «не знаю»». В начале анкеты респондент сам
   называет банки/бренды (открытые вопросы), а позже в списке «Знаю / Не
   знаю» говорит, что этот бренд не знает. Список узнаём по ответам
   (только «Знаю»/«Не знаю» или 1/99), название бренда — по заголовку
   колонки; открытые вопросы — текстовые колонки ДО списка.
2. «Ничего из перечисленного» и одновременно другой вариант в вопросе с
   несколькими ответами (колонки Kobo «Вопрос/Вариант» со значениями 0/1).
3. Цепочка «Назовите… / А ещё? / А ещё?»: сказал «больше не знаю», а в
   следующем вопросе цепочки назвал бренд. Один бренд дважды в цепочке —
   для сведения (неаккуратный ввод).
4. Возраст меньше порога отбора из текста анкеты («…достигшие 16 лет») или
   невозможный возраст.
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


_YES = {"да", "ha", "xa", "yes", "bor", "ha, bilaman", "да, знаю"}
_NO = {"нет", "yoq", "yo'q", "yoʻq", "yo‘q", "no", "yok"}


def _yes_no(col):
    vals = col.dropna().astype(str).str.strip().str.lower()
    return len(vals) >= 5 and vals.isin(_YES | _NO).all() and vals.isin(_YES).any()


def _rating(col):
    """Шкала оценки (1–5, 1–10), коды «затрудняюсь» 97–99 допустимы."""
    v = pd.to_numeric(col, errors="coerce").dropna()
    if len(v) < 5 or (v % 1 != 0).any():
        return False
    core = v[v < 90]
    return len(core) >= 0.6 * len(v) and core.min() >= 0 and core.max() <= 10 and core.nunique() >= 3


def _names_brand(col, keys):
    words = norm(re.sub(r"_", " ", str(col))).split()
    return any(w == k or w.startswith(k) for w in words for k in keys)


def brand_answer_conflicts(raw, skip=()):
    """{строка: [текст]}: про бренд ответил «Да» («Знаете ли вы карту Uzum?»,
    «Оформляли?») или поставил ему оценку, а в списке сказал, что этот бренд
    не знает."""
    aided = aided_columns(raw, skip)
    if not aided:
        return {}
    all_keys = set().union(*aided.values())
    # вопросы «Да/Нет» и шкалы, в названии которых есть бренд из списка
    yes_no, ratings = [], []
    for c in raw.columns:
        if c in aided or c in skip:
            continue
        name = TAG.sub("", str(c))
        if not _names_brand(name, all_keys):
            continue
        if _yes_no(raw[c]):
            yes_no.append((c, name.strip()[:60], raw[c].astype(str).str.strip().str.lower().isin(_YES)))
        elif _rating(raw[c]):
            v = pd.to_numeric(raw[c], errors="coerce")
            ratings.append((c, v, v.notna() & (v < 90)))
    if not yes_no and not ratings:
        return {}
    out = {}
    for c, keys in aided.items():
        label = brand_label(c)
        bad = raw[c].map(_know_value) == False  # noqa: E712
        mine_yn = [(q, name, yes) for q, name, yes in yes_no if _names_brand(name, keys)]
        mine_rt = [(q, v, has) for q, v, has in ratings if _names_brand(q, keys)]
        for q, name, yes in mine_yn:
            for i in (bad & yes)[lambda x: x].index:
                if any(label in m for m in out.get(i, [])):
                    continue
                out.setdefault(i, []).append(f"на вопрос «{name}» ответил «{str(raw.at[i, q]).strip()}», "
                                             f"а в списке про «{label}» — «{_show(raw.at[i, c])}»")
        for q, v, has in mine_rt:
            for i in (bad & has)[lambda x: x].index:
                if any(label in m for m in out.get(i, [])):
                    continue
                out.setdefault(i, []).append(f"поставил оценку «{v[i]:g}» банку «{label}» ({str(q)[:30]}), "
                                             f"хотя в списке сказал «{_show(raw.at[i, c])}»")
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


# ── Цепочки «А ещё?» ──────────────────────────────────────────────────────
# «Больше не знаю» пишут как угодно: «Boshqa bilmaydi», «Бошка билмайди»,
# «Билмадим», «Бил», «Yoʻq», «999», «Нет», «Больше не знаю»…
_DK_WORDS = {"boshqa", "boshka", "bosqa", "boshqasi", "bil", "yoq", "yuq", "yok", "yo", "net", "ne", "no", "none",
             "znayu", "znaet", "znaju", "nichego", "bolshe", "xech", "hech", "narsa", "kim", "biri", "other", "drugoe",
             "drugih", "emas", "esimda", "yodimda", "eslolmadi", "eslay", "olmadi", "javob", "otkaz", "otkazalsya",
             "99", "999", "9999", "0", "x", "nomalum", "aniq", "zatrudnyayus", "ham", "videl", "videla", "slyshal",
             "pomnyu", "kormadi", "kormagan", "kormaganman", "kormadim", "eshitmagan", "eshitmadim", "yoqku"}
_DK_PREFIX = ("bilm", "bilma", "nezna", "eslo", "eslay", "zatrud", "otkaz", "kormad", "kormag", "eshitma")


def plain(text):
    s = TAG.sub(" ", str(text)).lower()
    s = "".join(_TR.get(ch, ch) for ch in s)
    s = re.sub(r"[ʻʼ’‘`']", "", s)
    return re.sub(r"[^0-9a-z]+", " ", s).strip()


def is_dont_know(v):
    """«Не знаю / больше нет / другое» в любом написании."""
    words = plain(v).split()
    return not words or all(w in _DK_WORDS or w.startswith(_DK_PREFIX) or len(w) == 1 for w in words)


def brand_key(v):
    """Ключ ответа-названия: «Tbc bank» → «tbc», «Миллийбанк» → «milliy»,
    «Sanoat qurilish bank» → «sanoatqurilish»; «Uzum nasiya» ≠ «Uzum bank»."""
    words = []
    for w in norm(v).split():
        if w.endswith("bank") and len(w) > 4 + KEY_MIN:
            w = w[:-4]
        if w not in STOP:
            words.append(w)
    key = "".join(words)
    return key if len(key) >= 2 else None


_NUM = re.compile(r"^\s*(\d+)((?:\.\d+)*)\.?\s")
_XML = re.compile(r"^(.*?[a-z_]*\d+)_?([a-z])$", re.IGNORECASE)


def chains(raw, skip=()):
    """Цепочки открытых вопросов «Назовите… / А ещё? / А ещё?»:
    «2.2.», «2.3.»… или q2a, q2b… Вопрос прямо перед «N.2» (обычно «первым
    на ум») — начало той же цепочки."""
    cols = list(raw.columns)
    texty = {}
    for c in cols:
        if c in skip or str(c).startswith("_"):
            continue
        vals = raw[c].dropna()
        if len(vals) < 5 or vals.map(lambda v: isinstance(v, str)).mean() <= 0.8 or vals.nunique() < 6:
            continue
        # шкала или закрытый список («1 — Совсем не подходит» … «5 — …») — не открытый вопрос
        if vals.value_counts().head(5).sum() >= 0.9 * len(vals):
            continue
        texty[c] = True
    groups = {}
    for pos, c in enumerate(cols):
        if c not in texty:
            continue
        m = _NUM.match(str(c))
        if m:
            key = ("n", m.group(1))
            if m.group(2).startswith(".2") and m.group(2).count(".") == 1 and key not in groups and pos > 0 \
                    and cols[pos - 1] in texty and _NUM.match(str(cols[pos - 1])) is not None:
                groups[key] = [cols[pos - 1]]
            groups.setdefault(key, []).append(c)
            continue
        m = _XML.match(str(c).split("/")[-1])
        if m:
            groups.setdefault(("x", m.group(1).lower()), []).append(c)
    return [g for g in groups.values() if len(g) >= 2]


def chain_conflicts(raw, skip=()):
    """{строка: [текст]}: «больше не знаю», а дальше назвал; один бренд дважды."""
    out = {}
    for chain in chains(raw, skip):
        # настоящее название — то, что в цепочке называют часто (не опечатка)
        keys = pd.concat([raw[c] for c in chain]).dropna().map(lambda v: None if is_dont_know(v) else brand_key(v))
        common = set(keys.value_counts()[lambda x: x >= 5].index)
        for i in raw.index:
            dk, seen, flagged = None, {}, set()
            for c in chain:
                v = raw.at[i, c]
                if not isinstance(v, str) or not v.strip():
                    continue
                if is_dont_know(v):
                    dk = dk or (c, v.strip())
                    continue
                k = brand_key(v)
                if dk and k in common and "dk" not in flagged:
                    out.setdefault(i, []).append(("logic",
                        f"сказал «{dk[1]}» ({_question_no(dk[0])}), а потом назвал «{v.strip()}» ({_question_no(c)})"))
                    flagged.add("dk")
                if k and k in seen and k in common and "dup" not in flagged:
                    out.setdefault(i, []).append(("logic_dup",
                        f"«{v.strip()}» назван дважды: {_question_no(seen[k][0])} («{seen[k][1]}») и {_question_no(c)}"))
                    flagged.add("dup")
                seen.setdefault(k, (c, v.strip()))
    return out


# ── Возраст и условие отбора ──────────────────────────────────────────────
_AGE_COL = re.compile(r"возраст|полных лет|сколько вам лет|yosh|\bage\b|how old", re.IGNORECASE)
_AGE_MIN = re.compile(r"(?:достигши\w*|старше|от|не младше)\s*(\d{2})\s*(?:лет|года)|(\d{2})\s*yosh(?:ga|dan)|"
                      r"(?:aged?|over)\s*(\d{2})", re.IGNORECASE)


def age_conflicts(raw, skip=()):
    """{строка: [текст]}: возраст меньше порога отбора из текста анкеты
    («…достигшие 16 лет») или невозможный (< 10, > 100)."""
    col = next((c for c in raw.columns if c not in skip and _AGE_COL.search(str(c))
                and pd.to_numeric(raw[c], errors="coerce").notna().mean() > 0.5), None)
    if col is None:
        return {}
    limit = None
    for c in raw.columns:
        m = _AGE_MIN.search(str(c))
        if m:
            limit = int(next(g for g in m.groups() if g))
            break
    age = pd.to_numeric(raw[col], errors="coerce")
    out = {}
    for i, a in age.dropna().items():
        if a < 10 or a > 100:
            out[i] = [f"возраст {a:g} — такого не бывает, похоже на ошибку ввода"]
        elif limit and a < limit:
            out[i] = [f"возраст {a:g}, а по условию отбора участвуют только с {limit} лет — анкета должна была прерваться"]
    return out


def conflicts(raw, skip=()):
    """{строка: [(вид, текст)]}: «logic» — противоречие, «logic_dup» — один
    бренд назван в цепочке дважды (для сведения)."""
    out = {}
    for part in (aware_conflicts(raw, skip), brand_answer_conflicts(raw, skip), none_conflicts(raw, skip),
                 age_conflicts(raw, skip)):
        for i, msgs in part.items():
            out.setdefault(i, []).extend(("logic", m) for m in msgs)
    for i, items in chain_conflicts(raw, skip).items():
        out.setdefault(i, []).extend(items)
    return out
