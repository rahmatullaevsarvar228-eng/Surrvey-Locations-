# -*- coding: utf-8 -*-
"""Клиент сервера доступа (Google Apps Script из server/Code.gs).

Сервер проверяет логин и пароль, решает, какие источники анкет видит
пользователь, и отдаёт сами анкеты. Приложение хранит только адрес сервера и
токен сессии — пароли и ссылки на таблицы остаются у администратора."""
import json
import urllib.error
import urllib.request

import pandas as pd

from .sources import _clean_columns, _dedupe, _maybe_numeric


class RemoteError(Exception):
    def __init__(self, message, auth=False):
        super().__init__(message)
        self.auth = auth


class RemoteClient:
    def __init__(self, url, timeout=180):
        url = (url or "").strip()
        # http — только для локальной разработки (tests/gas_server.js)
        if not (url.startswith("https://") or url.startswith("http://127.0.0.1:")):
            raise RemoteError("Адрес сервера должен начинаться с https://")
        self.url = url
        self.timeout = timeout
        self.token = None

    def call(self, action, **params):
        body = dict(params, action=action)
        if self.token:
            body["token"] = self.token
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            # Apps Script отвечает редиректом на googleusercontent.com —
            # urllib проходит его сам (POST → GET, как и требуется).
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise RemoteError(f"Сервер ответил ошибкой HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise RemoteError(f"Нет связи с сервером: {e.reason}") from e
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise RemoteError("Сервер вернул не то, что ожидалось. Проверьте адрес сервера "
                              "(ссылка веб-приложения …/exec) и доступ «Все».") from e
        if isinstance(data, dict) and data.get("error"):
            msg = str(data["error"])
            if msg.startswith("AUTH:"):
                raise RemoteError(msg[5:].strip(), auth=True)
            raise RemoteError(msg)
        return data

    def login(self, login, password):
        data = self.call("login", login=login, password=password)
        self.token = data["token"]
        return data

    def fetch_frame(self, source_id):
        data = self.call("fetch", source_id=source_id)
        return data["name"], rows_to_frame(data.get("columns") or [], data.get("rows") or [])


def rows_to_frame(columns, rows):
    if not columns:
        return pd.DataFrame()
    width = len(columns)
    rows = [list(r)[:width] + [None] * (width - len(r)) for r in rows]
    df = pd.DataFrame(rows, columns=_dedupe(columns)).replace("", None)
    return _clean_columns(df.apply(_maybe_numeric))


def combine(frames):
    """Объединяет анкеты из нескольких источников в одну таблицу с колонкой
    «Источник». Возвращает набор листов: общий + каждый источник отдельно."""
    frames = [(name, df) for name, df in frames if len(df.columns)]
    if not frames:
        return {}
    if len(frames) == 1:
        return {frames[0][0]: frames[0][1]}
    parts = []
    for name, df in frames:
        part = df.copy()
        part.insert(0, "Источник", name)
        parts.append(part)
    merged = pd.concat(parts, ignore_index=True, sort=False)
    sheets = {f"Все источники ({len(frames)})": merged}
    for name, df in frames:
        sheets.setdefault(name, df)
    return sheets
