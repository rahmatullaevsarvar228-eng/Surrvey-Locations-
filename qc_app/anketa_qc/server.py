# -*- coding: utf-8 -*-
"""Локальный API для интерфейса. Работает только внутри окна приложения
(pywebview отдаёт его напрямую, без сети); данные никуда не отправляются,
кроме явного запроса к Google Sheets."""
import math
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_file, send_from_directory

from . import APP_NAME, __version__, config, engine, export, sources
from .history import Store

WEB_DIR = Path(__file__).resolve().parent / "web"


class Session:
    """Состояние одного пользователя: приложение однооконное и локальное."""

    def __init__(self, store):
        self.store = store
        self.project = store.get_setting("last_project") or "Мой проект"
        self.config = config.merge_config(store.load_project(self.project))
        self.sheets = {}
        self.source_label = None
        self.result = None

    # --- проект ------------------------------------------------------------
    def open_project(self, name):
        self.project = name
        self.config = config.merge_config(self.store.load_project(name))
        self.store.set_setting("last_project", name)
        self.result = None

    def save_config(self, cfg=None):
        if cfg is not None:
            self.config = config.merge_config(cfg)
        self.store.save_project(self.project, self.config)
        self.store.set_setting("last_project", self.project)

    # --- данные ------------------------------------------------------------
    def set_sheets(self, sheets, label):
        if not sheets:
            raise sources.SourceError("В файле нет ни одного листа с данными")
        self.sheets, self.source_label, self.result = sheets, label, None
        if self.config.get("sheet") not in sheets:
            self.config["sheet"] = "data" if "data" in sheets else next(iter(sheets))

    def columns(self):
        df = self.sheets.get(self.config.get("sheet"))
        return list(df.columns) if df is not None else []

    def export_bytes(self, kind):
        """(имя файла, байты) для выгрузки — общий код для кнопки в браузере и
        для диалога «Сохранить как» в окне приложения."""
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        slug = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", self.project).strip("_")[:40] or "proekt"
        if kind == "history":
            return f"istoriya_{slug}_{stamp}.xlsx", export.history_report(self.store.history(self.project))
        if self.result is None:
            raise ValueError("Сначала запустите проверку")
        r = self.result
        if kind == "full":
            return (f"otchet_{slug}_{stamp}.xlsx",
                    export.full_report(r, engine.status_legend(self.config)))
        if kind == "interviewers":
            return f"interviewery_{slug}_{stamp}.xlsx", export.simple_report(
                "Интервьюеры", r["interviewers"], status_col="Статус")
        if kind == "repetition":
            return f"povtor_{slug}_{stamp}.xlsx", export.simple_report(
                "Повтор значения", r["repetition"]["rows"], status_col="Статус")
        if kind == "answers":
            return f"otvety_{slug}_{stamp}.xlsx", export.simple_report("Все ответы", r["answers"]["all"])
        raise ValueError(f"Неизвестный отчёт: {kind}")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.strftime("%d.%m.%Y %H:%M")
    if hasattr(v, "item"):          # numpy-скаляры
        return _clean(v.item())
    if v is pd.NaT:
        return None
    return v


def _records(rows):
    return [{k: _clean(v) for k, v in r.items()} for r in rows]


def result_payload(sess):
    r, cfg = sess.result, sess.config
    df = r["df"]
    n = len(df)
    n_def = int(df["is_defect"].sum())
    anketas = [{
        "id": _clean(x.row_id), "city": _clean(x.city), "inter": _clean(x.inter),
        "device": _clean(x.deviceid), "start": _clean(x.start), "end": _clean(x.end),
        "duration": None if pd.isna(x.duration_min) else round(float(x.duration_min), 1),
        "defect": bool(x.is_defect), "warning": bool(x.is_warning),
        "reasons": x.reason_text, "warnings": x.warning_text,
    } for x in df.itertuples()]

    cities = []
    for city, g in df.groupby("city"):
        nd = int(g["is_defect"].sum())
        pct = round(nd / len(g) * 100, 1)
        cities.append({"Город": city, "Анкет": len(g), "Интервьюеров": int(g["inter"].nunique()),
                       "Брак": nd, "% брака": pct,
                       "Статус": engine.status_for_pct(pct, cfg["status"]["red_pct"], cfg["status"]["yellow_pct"])})

    inter_status = [x["Статус"] for x in r["interviewers"]]
    return {
        "summary": {
            "total": n, "defects": n_def, "defect_pct": round(n_def / max(n, 1) * 100, 1),
            "warnings": int(df["is_warning"].sum()),
            "cities": int(df["city"].nunique()), "interviewers": int(df["inter"].nunique()),
            "dropped": r["n_dropped"], "period": engine.data_period(df),
            "processed_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "source": sess.source_label, "sheet": cfg.get("sheet"),
            "status_counts": {s: inter_status.count(s) for s in ("RED", "YELLOW", "GREEN")},
            "wave_median": r["wave_median"],
        },
        "defect_reasons": engine.issue_breakdown(df, engine.DEFECT),
        "warning_reasons": engine.issue_breakdown(df, engine.WARNING),
        "anketas": anketas,
        "interviewers": _records(r["interviewers"]),
        "cities": cities,
        "city_issues": r["city_issues"],
        "repetition": {"enabled": r["repetition"]["enabled"], "rows": _records(r["repetition"]["rows"])},
        "answers": _records(r["answers"]["all"]),
        "rule_errors": r["rule_errors"],
        "legend": engine.status_legend(cfg),
    }


def create_app(data_dir):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    sess = Session(Store(data_dir / "anketa_qc.db"))
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
    app.config["SESSION"] = sess

    def fail(msg, code=400):
        return jsonify({"error": msg}), code

    @app.errorhandler(sources.SourceError)
    def _source_error(e):
        return fail(str(e))

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/web/<path:name>")
    def web(name):
        return send_from_directory(WEB_DIR, name)

    def state_payload():
        cols = sess.columns()
        return {
            "app": {"name": APP_NAME, "version": __version__, "data_dir": str(data_dir)},
            "project": sess.project,
            "projects": sorted(set(sess.store.list_projects()) | {sess.project}),
            "config": sess.config,
            "roles": config.ROLES,
            "rule_ops": engine.RULE_OPS,
            "source": sess.source_label,
            "sheets": list(sess.sheets),
            "columns": cols,
            "suggested": config.suggest_mapping(cols, sess.config["mapping"]) if cols else {},
            "has_result": sess.result is not None,
            "waves": sess.store.list_waves(sess.project),
        }

    @app.get("/api/state")
    def state():
        return jsonify(state_payload())

    @app.post("/api/project/open")
    def project_open():
        name = (request.json or {}).get("name", "").strip()
        if not name:
            return fail("Введите название проекта")
        sess.open_project(name)
        if sess.sheets and sess.config.get("sheet") not in sess.sheets:
            sess.config["sheet"] = "data" if "data" in sess.sheets else next(iter(sess.sheets))
        sess.save_config()
        return jsonify(state_payload())

    @app.post("/api/project/delete")
    def project_delete():
        sess.store.delete_project(sess.project)
        others = sess.store.list_projects()
        sess.open_project(others[0] if others else "Мой проект")
        return jsonify(state_payload())

    @app.post("/api/config")
    def save_config():
        sess.save_config((request.json or {}).get("config"))
        return jsonify(state_payload())

    @app.post("/api/source/file")
    def source_file():
        f = request.files.get("file")
        if f is None:
            return fail("Файл не получен")
        sess.set_sheets(sources.read_excel_bytes(f.read()), f.filename)
        sess.save_config()
        return jsonify(state_payload())

    @app.post("/api/source/google")
    def source_google():
        body = request.json or {}
        url = (body.get("url") or "").strip()
        key = (body.get("key_path") or "").strip() or None
        sess.set_sheets(sources.read_google(url, key), "Google Sheets")
        sess.config["google"] = {"url": url, "key_path": key or ""}
        sess.save_config()
        return jsonify(state_payload())

    @app.post("/api/sheet")
    def pick_sheet():
        name = (request.json or {}).get("sheet")
        if name not in sess.sheets:
            return fail("Нет такого листа")
        sess.config["sheet"] = name
        sess.result = None
        sess.save_config()
        return jsonify(state_payload())

    @app.get("/api/preview")
    def preview():
        df = sess.sheets.get(sess.config.get("sheet"))
        if df is None:
            return jsonify({"rows": [], "total": 0})
        return jsonify({"rows": _records(df.head(8).to_dict("records")), "total": len(df)})

    @app.post("/api/run")
    def run():
        body = request.json or {}
        if body.get("config"):
            sess.save_config(body["config"])
        df = sess.sheets.get(sess.config.get("sheet"))
        if df is None:
            return fail("Сначала подключите данные: файл Excel или Google Sheets")
        missing = config.missing_required(sess.config["mapping"])
        if missing:
            return fail("Укажите колонки: " + ", ".join(missing))
        absent = [c for c in sess.config["mapping"].values() if c and c not in df.columns]
        if absent:
            return fail("В выбранном листе нет колонок: " + ", ".join(absent))
        sess.result = engine.run(df, sess.config)
        return jsonify(result_payload(sess))

    @app.get("/api/result")
    def result():
        if sess.result is None:
            return fail("Проверка ещё не запускалась", 404)
        return jsonify(result_payload(sess))

    @app.get("/api/answers/who")
    def answers_who():
        if sess.result is None:
            return fail("Проверка ещё не запускалась", 404)
        return jsonify(sess.result["answers"]["index"].get(request.args.get("answer", ""), []))

    @app.get("/api/export/<kind>")
    def export_file(kind):
        try:
            name, data = sess.export_bytes(kind)
        except ValueError as e:
            return fail(str(e))
        import io
        return send_file(io.BytesIO(data), as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/api/history")
    def history_get():
        return jsonify(_history_payload(sess))

    @app.post("/api/history/save")
    def history_save():
        wave = ((request.json or {}).get("wave") or "").strip()
        if not wave:
            return fail("Введите название волны")
        if sess.result is None:
            return fail("Сначала запустите проверку")
        sess.store.save_wave(sess.project, wave, sess.result["interviewers"],
                             period=engine.data_period(sess.result["df"]), source=sess.source_label)
        return jsonify(_history_payload(sess))

    @app.post("/api/history/delete")
    def history_delete():
        sess.store.delete_wave(sess.project, (request.json or {}).get("wave", ""))
        return jsonify(_history_payload(sess))

    return app


def _history_payload(sess):
    h = sess.store.history(sess.project)
    return {"waves": h["waves"], "rows": _records(h["rows"])}
