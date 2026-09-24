# -*- coding: utf-8 -*-
"""Запуск приложения: отдельное нативное окно (pywebview → WebView2 на
Windows), без консоли и без браузера. Режим --browser — только для
разработки, открывает тот же интерфейс в обычном браузере."""
import os
import sys
import threading
import webbrowser
from pathlib import Path

from . import APP_NAME
from .server import create_app


def data_dir():
    custom = os.environ.get("ANKETA_QC_DATA")
    if custom:
        return Path(custom)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AnketaQC"
    return Path.home() / ".anketa_qc"


class JsApi:
    """Методы, доступные из интерфейса как window.pywebview.api.*"""

    def __init__(self, app):
        self._app = app
        self._window = None

    def save_export(self, kind):
        import webview
        sess = self._app.config["SESSION"]
        try:
            name, data = sess.export_bytes(kind)
        except ValueError as e:
            return {"error": str(e)}
        path = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename=name,
                                               file_types=("Excel (*.xlsx)",))
        if not path:
            return {"cancelled": True}
        path = path[0] if isinstance(path, (list, tuple)) else path
        with open(path, "wb") as f:
            f.write(data)
        return {"path": path}

    def pick_key_file(self):
        import webview
        path = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("JSON (*.json)",))
        return path[0] if path else None


def selftest():
    """Проверка собранного exe без окна (для CI): поднимаем API и
    запрашиваем главную страницу и состояние. Код выхода 0 — всё на месте."""
    import tempfile
    app = create_app(Path(tempfile.mkdtemp()))
    client = app.test_client()
    ok = client.get("/").status_code == 200 and client.get("/web/app.js").status_code == 200
    ok = ok and client.get("/api/state").status_code == 200
    import webview  # noqa: F401 — проверяем, что оконная библиотека попала в сборку
    sys.exit(0 if ok else 1)


def main():
    if "--selftest" in sys.argv:
        return selftest()
    app = create_app(data_dir())
    if "--browser" in sys.argv:
        port = int(os.environ.get("PORT", "8765"))
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
        app.run(host="127.0.0.1", port=port)
        return
    import webview
    api = JsApi(app)
    window = webview.create_window(APP_NAME, app, js_api=api, width=1400, height=900,
                                   min_size=(1100, 700), background_color="#F5F5F7")
    api._window = window
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
