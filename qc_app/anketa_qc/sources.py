# -*- coding: utf-8 -*-
"""Чтение данных: Excel-файл с диска и приведение строк из сервера доступа
к таблице (те же правила, что у pandas при чтении Excel)."""
import io

import pandas as pd


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
