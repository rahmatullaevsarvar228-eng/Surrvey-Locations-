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

from . import APP_NAME, __version__, config, engine, export, quotas, review, sources
from .remote import RemoteClient, RemoteError, combine
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
        # Вход через сервер доступа: без него приложение не работает.
        self.client = None
        self.user = None
        self.sources = []
        self.server_email = ""
        self.seen_ids = None   # ID анкет на прошлой проверке — чтобы показать, сколько пришло новых
        # Решения руководителя: {(id источника, ID анкеты): {...}} и названия источников
        self.decisions = {}
        self.source_names = {}
        self.source_tabs = {}   # {id источника: {"sheets": [...], "sheet": прочитанный лист}}
        self.tech_frames = []   # технические задания с отдельных листов/таблиц Google

    def logout(self):
        self.client, self.user, self.sources, self.server_email = None, None, [], ""
        self.sheets, self.source_label, self.result, self.seen_ids = {}, None, None, None
        self.decisions, self.source_names, self.source_tabs, self.tech_frames = {}, {}, {}, []

    # --- решения по анкетам ------------------------------------------------
    def row_sources(self):
        """pos анкеты → id источника (по колонке «Источник» объединённой таблицы)."""
        if not self.result or not self.source_names:
            return {}
        raw = self.result["raw"]
        by_name = {name: sid for sid, name in self.source_names.items()}
        if "Источник" in raw.columns and len(self.source_names) > 1:
            return {pos: by_name.get(v) for pos, v in raw["Источник"].items()}
        # проверяется лист одной из таблиц — решения идут именно в неё
        sid = by_name.get(self.config.get("sheet")) or next(iter(self.source_names))
        return {pos: sid for pos in raw.index}

    def decisions_by_pos(self):
        if not self.result:
            return {}
        srcs = self.row_sources()
        ids = self.result["df"].set_index("pos")["row_id"]
        out = {}
        for pos, sid in srcs.items():
            d = self.decisions.get((sid, str(ids.get(pos))))
            if d and d.get("decision"):
                out[pos] = d
        return out

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
            self.config["sheet"] = best_sheet(sheets)

    def frame_for_run(self):
        """Лист с анкетами + технические задания с отдельного листа или
        таблицы (если указаны): они нужны, чтобы интервью сразу после ТЗ не
        считалось «без перерыва»."""
        from .blocks import TECH_SHEET_COL
        df = self.sheets.get(self.config.get("sheet"))
        if df is None:
            return None
        extra = list(self.tech_frames)
        ts = self.config.get("tech_sheet")
        if ts and ts in self.sheets and ts != self.config.get("sheet"):
            extra.append(self.sheets[ts])
        if not extra:
            return df
        parts = [df] + [x.assign(**{TECH_SHEET_COL: "да"}) for x in extra if len(x)]
        return pd.concat(parts, ignore_index=True, sort=False)

    def columns(self):
        df = self.sheets.get(self.config.get("sheet"))
        return list(df.columns) if df is not None else []

    def export_bytes(self, kind, filters=None):
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
            from . import daily
            return (f"otchet_{slug}_{stamp}.xlsx",
                    export.full_report(r, engine.status_legend(self.config),
                                       daily.frame(r, self.config, self.decisions_by_pos())))
        if kind == "interviewers":
            return f"interviewery_{slug}_{stamp}.xlsx", export.simple_report(
                "Интервьюеры", r["interviewers"], status_col="Статус")
        if kind == "repetition":
            return f"povtor_{slug}_{stamp}.xlsx", export.simple_report(
                "Повтор значения", r["repetition"]["rows"], status_col="Статус")
        if kind == "answers":
            return f"otvety_{slug}_{stamp}.xlsx", export.simple_report("Все ответы", r["answers"]["all"])
        if kind == "quotas":
            q = quotas.compute(r, self.config, self.decisions_by_pos())
            if not q.get("enabled"):
                raise ValueError("Квоты не настроены")
            return f"kvoty_{slug}_{stamp}.xlsx", export.simple_report("Квоты", q["rows"], status_col="Статус")
        if kind == "client":
            dec = self.decisions_by_pos()
            clean, todo = review.clean_base(r, dec)
            counts = {}
            for d in dec.values():
                counts[d["decision"]] = counts.get(d["decision"], 0) + 1
            try:
                q = quotas.compute(r, self.config, dec)
            except ValueError:
                q = None
            return f"otchet_zakazchiku_{slug}_{stamp}.xlsx", export.client_report(
                r, clean, todo, q, self.project, self.source_label, counts)
        if kind == "word":
            from . import word
            filters = {k: v for k, v in (filters or {}).items() if k in ("region", "city", "inter") and v}
            dec = self.decisions_by_pos()
            try:
                q = quotas.compute(r, self.config, dec)
            except ValueError:
                q = None
            suffix = "_" + re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", "_".join(filters.values()))[:30] if filters else ""
            return f"otchet_KK_{slug}{suffix}_{stamp}.docx", word.build(
                r, self.config, dec, self.project, self.source_label, q,
                user=(self.user or {}).get("name") or (self.user or {}).get("login"), filters=filters)
        if kind == "listen":
            rows = review.listen_rows(r, self.config, self.decisions_by_pos())
            if not rows:
                raise ValueError("Выборка на прослушку пуста")
            return f"proslushka_{slug}_{stamp}.xlsx", export.simple_report("На прослушку", rows)
        if kind == "cards":
            from . import word
            inter = (filters or {}).get("inter")
            name = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", inter)[:30] if inter else "vse"
            return f"kartochki_{name}_{stamp}.docx", word.cards(
                r, self.config, self.decisions_by_pos(), self.project, inter)
        if kind == "clean":
            clean, todo = review.clean_base(r, self.decisions_by_pos())
            return f"chistaya_baza_{slug}_{stamp}.xlsx", export.clean_report(clean, todo, review.technical_rows(r))
        raise ValueError(f"Неизвестный отчёт: {kind}")


def _looks_like_anketas(df):
    """Все обязательные колонки (устройство, старт, финиш, город, интервьюер) нашлись."""
    found = config.suggest_mapping(list(df.columns))
    return len(df) > 0 and all(found.get(k) for k in config.REQUIRED_ROLES)


def best_sheet(sheets):
    """Лист с анкетами среди многих (свод, Pivot, мониторинг…): тот, где
    нашлось больше всего нужных колонок, при равенстве — где больше строк."""
    def score(item):
        name, df = item
        found = sum(1 for k, c in config.suggest_mapping(list(df.columns)).items() if c and k in config.REQUIRED_ROLES)
        return (found, name == "data", len(df))
    return max(sheets.items(), key=score)[0]


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


def _quotas_safe(sess):
    try:
        return _clean_deep(quotas.compute(sess.result, sess.config, sess.decisions_by_pos()))
    except ValueError as e:          # например, неверно заданы интервалы возраста
        return {"enabled": False, "error": str(e)}


def _clean_deep(obj):
    if isinstance(obj, dict):
        return {k: _clean_deep(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_deep(v) for v in obj]
    return _clean(obj)


def _records(rows):
    return [{k: _clean(v) for k, v in r.items()} for r in rows]


def result_payload(sess):
    r, cfg = sess.result, sess.config
    df = r["df"]
    n = len(df)
    n_tech = int(df["technical"].sum())
    n_iv = n - n_tech
    n_def = int(df["is_defect"].sum())
    dec = sess.decisions_by_pos()
    has_geo = "geo_point" in df.columns

    def issues_of(x):
        return [[c, sev, b, engine.short_label(c), txt] for (c, sev, txt), b in zip(x.issues, x.blocks)]

    listen = review.listen_sample(r, cfg, dec)
    anketas = [{
        "pos": int(x.pos), "decision": (dec.get(x.pos) or {}).get("decision") or "",
        "decision_comment": (dec.get(x.pos) or {}).get("comment") or "",
        "decision_by": (dec.get(x.pos) or {}).get("by") or "",
        "id": _clean(x.row_id), "city": _clean(x.city), "inter": _clean(x.inter),
        "device": _clean(x.deviceid), "start": _clean(x.start), "end": _clean(x.end),
        "duration": None if pd.isna(x.duration_min) else round(float(x.duration_min), 1),
        "defect": bool(x.is_defect), "warning": bool(x.is_warning),
        "reasons": x.reason_text, "warnings": x.warning_text,
        "risk": int(x.risk),
        "technical": bool(x.technical), "rejected": bool(x.rejected), "completed": bool(x.completed), "screenout": bool(getattr(x, "screenout", False)), "region": x.region,
        "date": None if pd.isna(x.start) else x.start.strftime("%Y-%m-%d"),
        "hour": None if pd.isna(x.start) else int(x.start.hour),
        "lat": _clean(x.lat), "lon": _clean(x.lon),
        "point": (_clean(x.geo_point) if has_geo else None), "dist": (_clean(round(x.geo_dist, 2)) if has_geo else None),
        "primary": _clean(x.primary), "issues": issues_of(x), "listen": listen.get(x.pos, ""),
    } for x in df.itertuples()]

    cities = []
    for city, g in df.groupby("city"):
        nd = int(g["is_defect"].sum())
        n_city = int((~g["technical"]).sum())
        pct = round(nd / max(n_city, 1) * 100, 1)
        cities.append({"Город": city, "Регион": g["region"].iloc[0], "Анкет": n_city,
                       "Интервьюеров": int(g["inter"].nunique()),
                       "Брак": nd, "% брака": pct,
                       "Статус": engine.status_for_pct(pct, cfg["status"]["red_pct"], cfg["status"]["yellow_pct"])})

    inter_status = [x["Статус"] for x in r["interviewers"]]
    return {
        "summary": {
            "total": n, "interviews": n_iv, "technical": n_tech, "source_rows": n + r["n_dropped"],
            "technical_info": r.get("technical_info"),
            "rejected": int(df["rejected"].sum()), "rejected_info": r.get("rejected_info"),
            "completed": int(df["completed"].sum()),
            "defects": n_def, "defect_pct": round(n_def / max(n_iv, 1) * 100, 1),
            "warnings": int(df["is_warning"].sum()),
            "cities": int(df["city"].nunique()), "interviewers": int(df["inter"].nunique()),
            "dropped": r["n_dropped"], "period": engine.data_period(df),
            "processed_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "source": sess.source_label, "sheet": cfg.get("sheet"),
            "status_counts": {s: inter_status.count(s) for s in ("RED", "YELLOW", "GREEN")},
            "wave_median": r["wave_median"],
            "review": {
                "enabled": bool(sess.source_names) and bool(cfg["mapping"].get("id")),
                "can_decide": (sess.user or {}).get("role") in ("lead", "admin"),
                "todo": sum(1 for a in anketas if (a["defect"] or a["warning"]) and not a["decision"] and not a["technical"]
                            and not a["rejected"]),
                **{d: sum(1 for a in anketas if a["decision"] == d) for d in review.DECISIONS},
            },
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
        "data_checks": r.get("data_checks") or [],
        "typical_duration": _clean(r.get("typical_duration")),
        "legend": engine.status_legend(cfg),
        "sections": r.get("sections", []),
        "answer_patterns": _clean_deep(r.get("answer_patterns") or []),
        "block_times": r.get("block_times") or [],
        "quality_cols": r.get("quality_cols", 0),
        "labels": {**engine.SHORT_LABELS, **{c: engine.short_label(c) for c in df["primary"].dropna().unique()}},
        "status_cfg": cfg["status"],
        "geo": r.get("geo") or {"enabled": False},
        "quotas": _quotas_safe(sess),
    }


# Без входа доступны только страница и сами запросы входа.
OPEN_ENDPOINTS = {"/api/auth", "/api/auth/login"}
# Какие действия администратора пропускаем на сервер доступа.
ADMIN_ACTIONS = {"list_users", "create_user", "update_user", "reset_password", "delete_user", "log"}


def create_app(data_dir, client_factory=RemoteClient):
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

    @app.errorhandler(RemoteError)
    def _remote_error(e):
        if e.auth:   # сессия истекла, пользователя заблокировали или удалили
            sess.logout()
            return jsonify({"error": str(e), "auth": True}), 401
        return fail(str(e))

    @app.before_request
    def local_only():
        """Только запросы к самому компьютеру (127.0.0.1 / localhost): защита
        от DNS-rebinding — чужой сайт в браузере не сможет обратиться к API."""
        host = (request.host or "").rsplit(":", 1)[0].strip("[]").lower()
        if host not in ("127.0.0.1", "localhost", "::1"):
            return jsonify({"error": "Доступ только с этого компьютера"}), 403
        return None

    @app.before_request
    def require_login():
        if request.path.startswith("/api/") and request.path not in OPEN_ENDPOINTS and sess.user is None:
            return jsonify({"error": "Нужно войти", "auth": True}), 401
        return None

    def auth_payload():
        return {"logged_in": sess.user is not None, "user": sess.user,
                "server_url": sess.store.get_setting("server_url", ""),
                "last_login": sess.store.get_setting("last_login", ""),
                "app": {"name": APP_NAME, "version": __version__}}

    @app.get("/api/auth")
    def auth_status():
        return jsonify(auth_payload())

    @app.post("/api/auth/login")
    def auth_login():
        body = request.json or {}
        url = (body.get("server_url") or "").strip()
        client = client_factory(url)
        data = client.login((body.get("login") or "").strip(), body.get("password") or "")
        sess.client, sess.user, sess.sources = client, data["user"], data.get("sources", [])
        sess.server_email = data.get("server_email", "")
        sess.store.set_setting("server_url", url)
        sess.store.set_setting("last_login", data["user"]["login"])
        return jsonify(auth_payload())

    @app.post("/api/auth/logout")
    def auth_logout():
        sess.logout()
        return jsonify(auth_payload())

    @app.post("/api/auth/password")
    def auth_password():
        body = request.json or {}
        sess.client.call("change_password", old_password=body.get("old_password", ""),
                         new_password=body.get("new_password", ""))
        return jsonify({"ok": True})

    def reload_sources():
        sess.sources = sess.client.call("sources")["sources"]
        return jsonify(sess.sources)

    @app.get("/api/remote/sources")
    def remote_sources():
        return reload_sources()

    @app.post("/api/remote/sources/add")
    def remote_source_add():
        body = request.json or {}
        sess.client.call("add_source", name=body.get("name", ""), url=body.get("url", ""),
                         sheet=body.get("sheet", ""), project=sess.project)
        return reload_sources()

    @app.post("/api/remote/sources/delete")
    def remote_source_delete():
        sid = (request.json or {}).get("id")
        sess.client.call("delete_source", id=sid)
        ids = [x for x in sess.config.get("remote_sources") or [] if x != sid]
        sess.config["remote_sources"] = ids
        sess.save_config()
        return reload_sources()

    def load_remote(ids):
        tabs = sess.config.get("source_sheets") or {}
        tech_tabs = sess.config.get("tech_tabs") or {}
        tech_sources = [i for i in sess.config.get("tech_sources") or [] if i in ids]
        all_ids = list(ids)
        ids = [i for i in ids if i not in tech_sources] or ids
        sess.tech_frames = []
        for i in tech_sources:                     # целая таблица с ТЗ
            if i not in ids:
                sess.tech_frames.append(sess.client.fetch_frame(i, tabs.get(i))[2])
        for i, tab in tech_tabs.items():           # лист с ТЗ в таблице с анкетами
            if i in ids and tab:
                try:
                    sess.tech_frames.append(sess.client.fetch_frame(i, tab)[2])
                except RemoteError as e:
                    if e.auth:
                        raise
        fetched = []
        for i in ids:
            try:
                fetched.append(sess.client.fetch_frame(i, tabs.get(i)))
            except RemoteError as e:
                if not tabs.get(i) or e.auth or "нет листа" not in str(e):
                    raise
                # выбранный лист удалили или переименовали — читаем лист по умолчанию
                tabs.pop(i, None)
                fetched.append(sess.client.fetch_frame(i))
        # Лист не выбран, а в прочитанном по умолчанию нет анкет (свод, Pivot…) —
        # сами пробуем другие листы таблицы и запоминаем первый подходящий.
        for k, f in enumerate(fetched):
            info = f[4] if len(f) > 4 else {}
            if tabs.get(f[0]) or _looks_like_anketas(f[2]) or not info.get("sheets"):
                continue
            best = None                          # из подходящих листов — где больше всего строк
            for tab in info["sheets"][:10]:
                if tab == info.get("sheet") or tab == tech_tabs.get(f[0]):
                    continue
                g = sess.client.fetch_frame(f[0], tab)
                if _looks_like_anketas(g[2]) and (best is None or len(g[2]) > len(best[1][2])):
                    best = (tab, g)
            if best:
                fetched[k] = best[1]
                tabs[f[0]] = best[0]
        sess.config["source_sheets"] = tabs
        frames = [(f[1], f[2]) for f in fetched]
        sess.source_names = {f[0]: f[1] for f in fetched}
        sess.source_tabs = {f[0]: (f[4] if len(f) > 4 else {}) for f in fetched}
        sess.decisions = {(f[0], str(d["id"])): d for f in fetched for d in f[3]}
        sheets = combine(frames)
        if not sheets:
            raise sources.SourceError("В выбранных источниках нет данных")
        keep_sheet = sess.config.get("sheet")
        sess.set_sheets(sheets, "Google Sheets: " + ", ".join(name for name, _ in frames))
        # Лист сохраняется между обновлениями; при новом наборе — объединённый.
        sess.config["sheet"] = keep_sheet if keep_sheet in sheets else next(iter(sheets))
        sess.config["remote_sources"] = all_ids
        sess.save_config()

    @app.post("/api/source/remote")
    def source_remote():
        ids = (request.json or {}).get("ids") or []
        if not ids:
            return fail("Отметьте хотя бы одну таблицу")
        load_remote(ids)
        sess.seen_ids = None
        return jsonify(state_payload())

    @app.post("/api/refresh")
    def refresh():
        """Автообновление: заново забираем анкеты из таблиц проекта и
        перепроверяем. Возвращает результат и сколько пришло новых анкет."""
        ids = sess.config.get("remote_sources") or []
        if not ids:
            return fail("К проекту не подключены таблицы")
        load_remote(ids)
        df = sess.frame_for_run()
        fill_mapping(df)
        missing = config.missing_required(sess.config["mapping"])
        if missing or any(c and c not in df.columns for c in sess.config["mapping"].values()):
            return fail("Колонки не сопоставлены — откройте «Колонки»")
        sess.result = engine.run(df, sess.config)
        rdf = sess.result["df"]
        ids_now = set(rdf["row_id"])
        new = [] if sess.seen_ids is None else sorted(ids_now - sess.seen_ids, key=str)
        new_def = rdf[rdf["row_id"].isin(new) & rdf["is_defect"]]
        sess.seen_ids = ids_now
        payload = result_payload(sess)
        payload["refresh"] = {"new": len(new), "new_defects": int(len(new_def)),
                              "at": datetime.now().strftime("%H:%M")}
        return jsonify(payload)

    @app.get("/api/anketa/<int:pos>")
    def anketa(pos):
        if sess.result is None or pos not in sess.result["raw"].index:
            return fail("Анкета не найдена", 404)
        return jsonify(_clean_deep(review.anketa_detail(sess.result, sess.config, pos,
                                                        sess.decisions_by_pos().get(pos))))

    @app.post("/api/decisions")
    def decisions():
        """Решение руководителя по одной или нескольким анкетам → лист
        «Решения ОТК» в Google-таблице, откуда пришла анкета."""
        if (sess.user or {}).get("role") not in ("lead", "admin"):
            return fail("Решения по анкетам ставит только руководитель проекта", 403)
        if sess.result is None:
            return fail("Сначала запустите проверку")
        if not sess.source_names:
            return fail("Решения сохраняются в Google-таблице — загрузите анкеты из подключённой таблицы")
        if not sess.config["mapping"].get("id"):
            return fail("Выберите колонку «ID анкеты» на странице «Колонки» — по ней сохраняются решения")
        body = request.json or {}
        decision, comment = body.get("decision") or "", body.get("comment") or ""
        if decision and decision not in review.DECISIONS:
            return fail("Неизвестное решение")
        df = sess.result["df"].set_index("pos")
        srcs = sess.row_sources()
        groups = {}
        for pos in body.get("positions") or []:
            if pos not in df.index:
                continue
            groups.setdefault(srcs.get(pos), []).append({
                "id": str(df.at[pos, "row_id"]), "decision": decision, "comment": comment,
                "reason": df.at[pos, "reason_text"] or df.at[pos, "warning_text"]})
        if not groups:
            return fail("Не выбрано ни одной анкеты")
        for sid, items in groups.items():
            saved = sess.client.call("set_decisions", source_id=sid, items=items)["decisions"]
            sess.decisions = {k: v for k, v in sess.decisions.items() if k[0] != sid}
            sess.decisions.update({(sid, str(d["id"])): d for d in saved})
        return jsonify(result_payload(sess))

    @app.post("/api/admin/<action>")
    def admin(action):
        if (sess.user or {}).get("role") != "admin":
            return fail("Нужны права администратора", 403)
        if action not in ADMIN_ACTIONS:
            return fail("Неизвестное действие", 404)
        return jsonify(sess.client.call(action, **(request.json or {})))

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
            "technical_hint": _technical_hint(sess),
            "rejected_hint": _rejected_hint(sess),
            "sections_auto": _sections_auto(sess),
            "has_result": sess.result is not None,
            "waves": sess.store.list_waves(sess.project),
            "user": sess.user,
            "remote_sources": sess.sources,
            "source_tabs": sess.source_tabs,
            "server_email": sess.server_email,
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
            sess.config["sheet"] = best_sheet(sess.sheets)
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

    @app.post("/api/sheet")
    def pick_sheet():
        name = (request.json or {}).get("sheet")
        if name not in sess.sheets:
            return fail("Нет такого листа")
        sess.config["sheet"] = name
        sess.result = None
        sess.save_config()
        return jsonify(state_payload())

    @app.get("/api/geo/default-plan")
    def geo_default_plan():
        from . import geo
        return jsonify(geo.default_plan())

    @app.post("/api/geo/plan/parse")
    def geo_plan_parse():
        from . import geo
        f = request.files.get("file")
        if f is None:
            return fail("Файл не получен")
        sheets = sources.read_excel_bytes(f.read())
        errors = []
        for df in sheets.values():
            try:
                return jsonify(geo.plan_from_frame(df))
            except ValueError as e:
                errors.append(str(e))
        return fail(errors[0] if errors else "Пустой файл")

    @app.post("/api/quotas/template")
    def quotas_template():
        if sess.result is None:
            return fail("Сначала запустите проверку — строки плана берутся из данных")
        try:
            return jsonify(quotas.template(sess.result, sess.config, sess.config["quotas"].get("plan")))
        except ValueError as e:
            return fail(str(e))

    @app.post("/api/quotas/from-geo")
    def quotas_from_geo():
        plan = quotas.plan_from_geo(sess.config)
        if not plan:
            return fail("В плане GPS-точек нет цифр по городам")
        return jsonify(plan)

    @app.post("/api/quotas/parse")
    def quotas_parse():
        f = request.files.get("file")
        if f is None:
            return fail("Файл не получен")
        labels = quotas.dim_labels(sess.config)
        errors = []
        for df in sources.read_excel_bytes(f.read()).values():
            try:
                return jsonify(quotas.plan_from_frame(df, labels))
            except ValueError as e:
                errors.append(str(e))
        return fail(errors[0] if errors else "Пустой файл")

    @app.get("/api/column/values")
    def column_values():
        df = sess.sheets.get(sess.config.get("sheet"))
        col = request.args.get("col", "")
        if df is None or col not in df.columns:
            return jsonify([])
        vc = df[col].dropna().map(lambda v: str(v).strip()).value_counts().head(40)
        return jsonify([{"value": k, "n": int(v)} for k, v in vc.items() if k])

    @app.get("/api/preview")
    def preview():
        df = sess.sheets.get(sess.config.get("sheet"))
        if df is None:
            return jsonify({"rows": [], "total": 0})
        return jsonify({"rows": _records(df.head(8).to_dict("records")), "total": len(df)})

    def fill_mapping(df):
        """Незаполненные роли колонок берём из подсказок — чтобы новый проект
        (и автообновление) заработал без обязательного захода в «Колонки»."""
        m = sess.config["mapping"]
        for key, col in config.suggest_mapping(list(df.columns), m).items():
            if not m.get(key) and col:
                m[key] = col
        sess.save_config()

    @app.post("/api/run")
    def run():
        body = request.json or {}
        if body.get("config"):
            sess.save_config(body["config"])
        df = sess.frame_for_run()
        if df is None:
            return fail("Сначала подключите данные: файл Excel или Google Sheets")
        fill_mapping(df)
        missing = config.missing_required(sess.config["mapping"])
        if missing:
            return fail("Укажите колонки: " + ", ".join(missing))
        absent = [c for c in sess.config["mapping"].values() if c and c not in df.columns]
        if absent:
            return fail("В выбранном листе нет колонок: " + ", ".join(absent))
        sess.result = engine.run(df, sess.config)
        sess.seen_ids = set(sess.result["df"]["row_id"])
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
            name, data = sess.export_bytes(kind, request.args.to_dict())
        except ValueError as e:
            return fail(str(e))
        import io
        mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document" if name.endswith(".docx")
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return send_file(io.BytesIO(data), as_attachment=True, download_name=name, mimetype=mime)

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


def _technical_hint(sess):
    from .blocks import suggest_technical
    df = sess.sheets.get(sess.config.get("sheet"))
    return suggest_technical(df) if df is not None else []


def _rejected_hint(sess):
    from .blocks import rejected_candidates
    df = sess.sheets.get(sess.config.get("sheet"))
    if df is None:
        return []
    return rejected_candidates(df, skip={c for c in sess.config["mapping"].values() if c})[:3]


def _sections_auto(sess):
    from .blocks import build_sections
    df = sess.sheets.get(sess.config.get("sheet"))
    if df is None:
        return []
    return [{"name": x["name"], "start": x["columns"][0], "n": len(x["columns"])}
            for x in build_sections(df.columns, {"sections": []})]


def _history_payload(sess):
    h = sess.store.history(sess.project)
    return {"waves": h["waves"], "rows": _records(h["rows"])}
