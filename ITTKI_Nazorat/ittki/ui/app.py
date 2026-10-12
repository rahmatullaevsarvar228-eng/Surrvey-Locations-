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
    """`ITTKI_Nazorat.exe --selftest [log.txt]`: offscreen check of the built program.

    * demo data loaded by Buxgalter into an empty database, 'today' fixed at 11.10.2026;
    * control numbers of the demo projects;
    * every window and tab opened;
    * login under each of the three roles: one allowed and one forbidden action each
      (the forbidden one must show 'Ruxsat yo'q' and leave a 'denied' record in the audit log).
    Exit code 0 = everything as expected. A windowed exe has no console, so results also go to `log`."""
    import tempfile
    from datetime import date

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from .. import clock
    from ..db.repository import CostRecord, Repository, User
    from ..services import Service
    from . import widgets
    from .dialogs import LoginDialog
    from .main_window import MainWindow
    from .project_card import ProjectCard

    clock.set_fixed(date(2026, 10, 11))
    lines = [f"ITTKI Nazorat selftest  (python {sys.version.split()[0]}, frozen={getattr(sys, 'frozen', False)}, "
             f"today={clock.today():%d.%m.%Y})"]
    failures = []

    def check(ok, text):
        lines.append(("  OK    " if ok else "  FAIL  ") + text)
        if not ok:
            failures.append(text)

    messages = []
    widgets.error = lambda parent, text: messages.append(text)   # no modal boxes offscreen
    app = make_app(["selftest"])
    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "selftest.sqlite3")
        svc = Service(repo)
        acc = User("Selftest Buxgalter", "accountant")
        check(svc.load_demo(acc) == 4, "Buxgalter: demo ma'lumotlar bo'sh bazaga yuklandi (4 loyiha)")
        an = {a.record.code: a for a in svc.analyze_all()}
        f, t = an["DEMO-FLOT-01"], an["DEMO-ATJBT-02"]
        check((f.res["IAS38"]["capitalized"], f.carrying["IAS38"], f.carrying["NAS11"])
              == (1_568_000_000, 1_453_666_669, 1_385_066_669), "DEMO-FLOT-01 raqamlari")
        check((t.res["IAS38"]["capitalized"], t.res["NAS11"]["capitalized"]) == (270_000_000, 880_000_000),
              "DEMO-ATJBT-02 raqamlari")
        pid = f.record.id
        w = MainWindow(svc, acc)
        for i in range(len(w.pages)):
            w.show_page(i)
        card = w.open_project(pid)
        for i in range(card.tabs.count()):
            card.tabs.setCurrentIndex(i)
        card.close(); w.close()

        def login(name, role):
            d = LoginDialog(None)
            d.name.setText(name)
            d.role.setCurrentIndex(d.role.findData(role))
            return d.user()

        def refused(fn):
            before = len([x for x in repo.audit_log() if x.action == "denied"])
            messages.clear()
            fn()
            after = len([x for x in repo.audit_log() if x.action == "denied"])
            return bool(messages) and "Ruxsat yo'q" in messages[0] and after == before + 1

        # Loyiha rahbari: allowed — criteria assessment; forbidden — cost
        u = login("Selftest Rahbar", "leader")
        card = ProjectCard(svc, u, pid)
        prev = repo.assessments(pid)[-1]
        prev.on_date, prev.id = date(2026, 10, 11), None
        try:
            svc.add_assessment(u, prev)
            ok = True
        except Exception:
            ok = False
        check(ok and card.b_assess.isEnabled(), "Loyiha rahbari: mezonlar bahosi saqlandi (ruxsat)")
        check(not card.b_c_add.isEnabled() and refused(card._add_cost),
              "Loyiha rahbari: xarajat qo'shish — tugma o'chiq, 'Ruxsat yo'q' + audit (taqiq)")
        card.close()

        # Buxgalter: allowed — cost; forbidden — stage change
        u = login("Selftest Buxgalter", "accountant")
        card = ProjectCard(svc, u, pid)
        n = len(repo.costs(pid))
        svc.add_cost(u, CostRecord(pid, date(2026, 10, 11), 1_000_000, "salary", "ST-1"))
        check(len(repo.costs(pid)) == n + 1 and card.b_c_add.isEnabled(), "Buxgalter: xarajat qo'shildi (ruxsat)")
        check(not card.b_stage.isEnabled() and refused(card._change_stage),
              "Buxgalter: bosqichni o'zgartirish — tugma o'chiq, 'Ruxsat yo'q' + audit (taqiq)")
        card.close()

        # Ichki auditor: allowed — report and backup; forbidden — save the passport
        u = login("Selftest Auditor", "auditor")
        card = ProjectCard(svc, u, pid)
        out = Path(tmp) / "solishtirma.xlsx"
        svc.export(u, "reconcile", out)
        svc.backup(u, Path(tmp) / "zaxira.sqlite3")
        check(out.exists() and (Path(tmp) / "zaxira.sqlite3").exists(),
              "Ichki auditor: hisobot (Excel) va zaxira nusxa (ruxsat)")
        check(not card.b_save.isEnabled() and refused(card._save_info),
              "Ichki auditor: pasportni saqlash — tugma o'chiq, 'Ruxsat yo'q' + audit (taqiq)")
        card.close()
        last = repo.audit_log()[-1]
        lines.append(f"  audit: oxirgi yozuv {clock.fmt_tashkent(last.at)} (Toshkent), bazada {last.at}")
        repo.close()
    app.processEvents()
    lines.append("RESULT: " + ("OK" if not failures else f"FAILED ({len(failures)})"))
    print("\n".join(lines))
    if log:
        Path(log).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if not failures else 1


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from .. import clock
    clock.init_from_env(argv)          # --today dd.mm.yyyy / ITTKI_TODAY: fixed "today"
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
