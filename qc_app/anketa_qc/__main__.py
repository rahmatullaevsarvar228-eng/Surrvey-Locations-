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


def unblock_bundle():
    """Снимает с файлов программы пометку «скачано из интернета»
    (поток Zone.Identifier). Windows ставит её на всё, что распаковано из
    скачанного zip, и .NET тогда отказывается загружать Python.Runtime.dll,
    через которую рисуется окно: «Failed to resolve Python.Runtime.Loader.Initialize»."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if os.environ.get("ANKETA_QC_NO_UNBLOCK"):   # для проверки в CI, что без этого падает
        return
    for path in Path(sys.executable).resolve().parent.rglob("*"):
        if path.suffix.lower() in (".dll", ".exe", ".pyd"):
            try:
                os.remove(f"{path}:Zone.Identifier")
            except OSError:
                pass


def run_in_browser(app):
    port = int(os.environ.get("PORT", "8765"))
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    app.run(host="127.0.0.1", port=port)


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


def selftest():
    """Проверка собранного exe без окна (для CI): поднимаем API и
    запрашиваем главную страницу и состояние. Код выхода 0 — всё на месте."""
    import tempfile
    app = create_app(Path(tempfile.mkdtemp()))
    client = app.test_client()
    ok = client.get("/").status_code == 200 and client.get("/web/app.js").status_code == 200
    ok = ok and client.get("/api/auth").status_code == 200
    # Загружаем ту же оконную часть, что и при обычном запуске (на Windows это
    # .NET через pythonnet) — именно она падала у файлов из скачанного zip.
    unblock_bundle()
    try:
        import webview  # noqa: F401
        if sys.platform == "win32":
            import webview.platforms.winforms  # noqa: F401
    except Exception:  # noqa: BLE001
        # Не даём исключению уйти наружу: exe без консоли показал бы окно
        # с ошибкой и ждал нажатия — в CI это зависание вместо кода выхода.
        import traceback
        traceback.print_exc()
        sys.exit(2)
    sys.exit(0 if ok else 1)


def main():
    if "--selftest" in sys.argv:
        return selftest()
    app = create_app(data_dir())
    if "--browser" in sys.argv:
        return run_in_browser(app)
    unblock_bundle()
    try:
        import webview
        api = JsApi(app)
        window = webview.create_window(APP_NAME, app, js_api=api, width=1400, height=900,
                                       min_size=(1100, 700), background_color="#F5F5F7")
        api._window = window
        webview.start(private_mode=False)
    except Exception:  # noqa: BLE001
        # Окно не поднялось (нет WebView2/.NET) — не оставляем пользователя
        # с ошибкой: тот же интерфейс откроется в браузере по умолчанию.
        import traceback
        (data_dir() / "startup_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        run_in_browser(app)


if __name__ == "__main__":
    main()
