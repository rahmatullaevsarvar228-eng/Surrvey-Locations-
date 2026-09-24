# -*- coding: utf-8 -*-
"""Источники данных: Excel-файл с диска или Google Sheets по ссылке.

Google Sheets читается напрямую у Google, без промежуточных серверов:
  1) таблица открыта «всем, у кого есть ссылка» — скачивается как .xlsx через
     официальный экспорт Google (docs.google.com/.../export?format=xlsx);
  2) закрытая таблица — через Google Sheets API (библиотека gspread) с ключом
     сервисного аккаунта; ключ хранится только на этом компьютере.
Оба способа дают один и тот же результат — набор листов (dict имя → DataFrame),
поэтому выбор листа и сопоставление колонок работают одинаково.
"""
import io
import re
import urllib.error
import urllib.request

import pandas as pd

_SHEET_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


class SourceError(Exception):
    pass


def _clean_columns(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def read_excel_bytes(data):
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    except Exception as e:  # noqa: BLE001 — показываем пользователю любую причину
        raise SourceError(f"Не удалось открыть Excel-файл: {e}") from e
    return {name: _clean_columns(df) for name, df in sheets.items()}


def read_excel_path(path):
    with open(path, "rb") as f:
        return read_excel_bytes(f.read())


def sheet_id_from_url(url):
    m = _SHEET_ID.search(url or "")
    if not m:
        raise SourceError("Это не похоже на ссылку Google Sheets "
                          "(нужна ссылка вида https://docs.google.com/spreadsheets/d/…)")
    return m.group(1)


def read_google_public(url, timeout=60):
    sheet_id = sheet_id_from_url(url)
    export = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    req = urllib.request.Request(export, headers={"User-Agent": "Mozilla/5.0 anketa-qc"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise SourceError("Google не отдал таблицу. Откройте доступ «Все, у кого есть ссылка → "
                              "Читатель» или подключите сервисный аккаунт.") from e
        raise SourceError(f"Ошибка Google Sheets: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise SourceError(f"Нет связи с Google: {e.reason}") from e
    if "html" in ctype.lower() or data[:2] != b"PK":
        raise SourceError("Вместо таблицы Google вернул страницу входа — таблица закрыта. "
                          "Откройте доступ по ссылке или подключите сервисный аккаунт.")
    return read_excel_bytes(data)


def read_google_service_account(url, key_path):
    try:
        import gspread
    except ImportError as e:
        raise SourceError("Для закрытых таблиц нужна библиотека gspread (pip install gspread)") from e
    try:
        gc = gspread.service_account(filename=key_path)
        book = gc.open_by_key(sheet_id_from_url(url))
        out = {}
        for ws in book.worksheets():
            values = ws.get_all_values()
            if not values:
                out[ws.title] = pd.DataFrame()
                continue
            header, *rows = values
            df = pd.DataFrame(rows, columns=_dedupe(header)).replace("", None)
            out[ws.title] = _clean_columns(df.apply(_maybe_numeric))
        return out
    except SourceError:
        raise
    except Exception as e:  # noqa: BLE001
        raise SourceError(f"Не удалось прочитать таблицу через сервисный аккаунт: {e}") from e


def _dedupe(header):
    """Как pandas: повторяющиеся заголовки → «X», «X.1», «X.2»."""
    seen, out = {}, []
    for h in header:
        h = str(h).strip()
        if h in seen:
            seen[h] += 1
            out.append(f"{h}.{seen[h]}")
        else:
            seen[h] = 0
            out.append(h)
    return out


def _maybe_numeric(col):
    conv = pd.to_numeric(col, errors="coerce")
    return conv if conv.notna().sum() == col.notna().sum() else col


def read_google(url, key_path=None):
    if key_path:
        return read_google_service_account(url, key_path)
    return read_google_public(url)
