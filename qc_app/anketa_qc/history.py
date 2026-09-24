# -*- coding: utf-8 -*-
"""Локальное хранилище (SQLite-файл на этом компьютере, без облака):
настройки проектов и накопительная история интервьюеров по волнам."""
import json
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    config TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    wave TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    period TEXT,
    source TEXT,
    n_total INTEGER,
    n_defect INTEGER,
    UNIQUE(project, wave)
);
CREATE TABLE IF NOT EXISTS interviewer_results (
    wave_id INTEGER NOT NULL REFERENCES waves(id) ON DELETE CASCADE,
    inter TEXT NOT NULL,
    city TEXT,
    n INTEGER,
    n_defect INTEGER,
    pct REAL,
    status TEXT,
    n_warning INTEGER,
    PRIMARY KEY (wave_id, inter)
);
"""

_SEVERITY = {"GREEN": 0, "YELLOW": 1, "RED": 2}


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # --- настройки ---------------------------------------------------------
    def get_setting(self, key, default=None):
        with self._conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_setting(self, key, value):
        with self._conn() as c:
            c.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                      (key, json.dumps(value, ensure_ascii=False)))

    # --- проекты -----------------------------------------------------------
    def list_projects(self):
        with self._conn() as c:
            return [r["name"] for r in c.execute("SELECT name FROM projects ORDER BY updated_at DESC")]

    def load_project(self, name):
        with self._conn() as c:
            row = c.execute("SELECT config FROM projects WHERE name = ?", (name,)).fetchone()
        return json.loads(row["config"]) if row else None

    def save_project(self, name, config):
        with self._conn() as c:
            c.execute("INSERT INTO projects(name, config, updated_at) VALUES(?, ?, ?) "
                      "ON CONFLICT(name) DO UPDATE SET config = excluded.config, updated_at = excluded.updated_at",
                      (name, json.dumps(config, ensure_ascii=False), _now()))

    def delete_project(self, name):
        with self._conn() as c:
            c.execute("DELETE FROM projects WHERE name = ?", (name,))

    # --- история волн ------------------------------------------------------
    def save_wave(self, project, wave, interviewers, period=None, source=None):
        """Сохраняет итоги волны по интервьюерам. Повторное сохранение той же
        волны перезаписывает её (например, после догрузки анкет)."""
        n_total = sum(r["Анкет"] for r in interviewers)
        n_defect = sum(r["Брак"] for r in interviewers)
        with self._conn() as c:
            c.execute("DELETE FROM waves WHERE project = ? AND wave = ?", (project, wave))
            cur = c.execute("INSERT INTO waves(project, wave, saved_at, period, source, n_total, n_defect) "
                            "VALUES(?, ?, ?, ?, ?, ?, ?)",
                            (project, wave, _now(), period, source, n_total, n_defect))
            wave_id = cur.lastrowid
            c.executemany(
                "INSERT INTO interviewer_results(wave_id, inter, city, n, n_defect, pct, status, n_warning) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                [(wave_id, str(r["Интервьюер"]), r["Город"], r["Анкет"], r["Брак"], r["% брака"],
                  r["Статус"], r["Предупреждений"]) for r in interviewers])
        return wave_id

    def delete_wave(self, project, wave):
        with self._conn() as c:
            c.execute("DELETE FROM waves WHERE project = ? AND wave = ?", (project, wave))

    def list_waves(self, project):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT wave, saved_at, period, source, n_total, n_defect FROM waves "
                "WHERE project = ? ORDER BY id", (project,))]

    def history(self, project):
        """Накопительный рейтинг: по каждому интервьюеру — статус в каждой
        волне, сколько волн подряд (до последней) он в жёлтой/красной зоне и
        суммарная доля брака."""
        waves = self.list_waves(project)
        wave_names = [w["wave"] for w in waves]
        with self._conn() as c:
            rows = c.execute(
                "SELECT w.wave, r.inter, r.city, r.n, r.n_defect, r.pct, r.status "
                "FROM interviewer_results r JOIN waves w ON w.id = r.wave_id "
                "WHERE w.project = ? ORDER BY w.id", (project,)).fetchall()
        by_inter = {}
        for r in rows:
            d = by_inter.setdefault(r["inter"], {"city": r["city"], "waves": {}, "n": 0, "n_defect": 0})
            d["waves"][r["wave"]] = {"status": r["status"], "pct": r["pct"], "n": r["n"]}
            d["n"] += r["n"]
            d["n_defect"] += r["n_defect"]
            d["city"] = r["city"] or d["city"]

        out = []
        for inter, d in by_inter.items():
            present = [w for w in wave_names if w in d["waves"]]
            streak = 0
            for w in reversed(present):
                if d["waves"][w]["status"] in ("YELLOW", "RED"):
                    streak += 1
                else:
                    break
            pct = round(d["n_defect"] / d["n"] * 100, 1) if d["n"] else 0.0
            worst = max((d["waves"][w]["status"] for w in present), key=lambda s: _SEVERITY.get(s, 0))
            out.append({
                "Интервьюер": inter, "Город": d["city"] or "—",
                "Волн": len(present), "Анкет всего": d["n"], "Брак всего": d["n_defect"],
                "% брака (накоп.)": pct,
                "Подряд в зоне риска": streak,
                "Худший статус": worst,
                "waves": {w: d["waves"][w] for w in present},
            })
        out.sort(key=lambda r: (-r["Подряд в зоне риска"], -r["% брака (накоп.)"], str(r["Интервьюер"])))
        return {"waves": waves, "rows": out}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
