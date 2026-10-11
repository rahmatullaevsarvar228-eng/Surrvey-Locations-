"""Program entry point (GUI)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """%APPDATA%\\ITTKI_Nazorat on Windows, ~/.ittki_nazorat elsewhere; ITTKI_DATA overrides."""
    if os.environ.get("ITTKI_DATA"):
        p = Path(os.environ["ITTKI_DATA"])
    elif os.name == "nt" and os.environ.get("APPDATA"):
        p = Path(os.environ["APPDATA"]) / "ITTKI_Nazorat"
    else:
        p = Path.home() / ".ittki_nazorat"
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_app(argv=None):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from . import style
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("ITTKI Nazorat")
    app.setStyle("Fusion")
    app.setFont(QFont(style.FONT_FAMILY, style.FONT_SIZE))
    app.setStyleSheet(style.QSS)
    return app


def selftest(log: str | None = None) -> int:
    """`ITTKI_Nazorat.exe --selftest [log.txt]`: demo data + engine + DB + offscreen GUI start.
    Exit code 0 = OK. A windowed exe has no console, so the result can also be written to a file."""
    import tempfile
    from datetime import date

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ..core.engine import evaluate
    from ..db.repository import Repository, User
    from ..demo import load_demo
    from ..services import Service
    from .main_window import MainWindow

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "selftest.sqlite3")
        assert load_demo(repo) == 4
        svc = Service(repo)
        an = svc.analyze_all()
        caps = {a.record.code: (a.res["IAS38"]["capitalized"], a.res["NAS11"]["capitalized"]) for a in an}
        app = make_app(["selftest"])
        w = MainWindow(svc, User("selftest", "accountant"))
        for i in range(len(w.pages)):
            w.show_page(i)
        card = w.open_project(an[0].record.id)
        for i in range(card.tabs.count()):
            card.tabs.setCurrentIndex(i)
        app.processEvents()
        card.close(); w.close()
        repo.close()
    lines = ["ITTKI Nazorat selftest OK", f"  python {sys.version.split()[0]}, frozen={getattr(sys, 'frozen', False)}"]
    lines += [f"  {k}: IAS 38 {a:,} | BHMS 11 {b:,}" for k, (a, b) in caps.items()]
    print("\n".join(lines))
    if log:
        Path(log).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        i = argv.index("--selftest")
        return selftest(argv[i + 1] if i + 1 < len(argv) else None)
    from ..db.repository import Repository
    from ..services import Service
    from .dialogs import LoginDialog
    from .main_window import MainWindow

    app = make_app(argv)
    db = Path(os.environ.get("ITTKI_DB") or data_dir() / "ittki_nazorat.sqlite3")
    repo = Repository(db)
    login = LoginDialog()
    if not login.exec():
        return 0
    w = MainWindow(Service(repo), login.user())
    w.show()
    rc = app.exec()
    repo.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
