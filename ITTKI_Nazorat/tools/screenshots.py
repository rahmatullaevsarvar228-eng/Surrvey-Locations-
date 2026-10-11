"""Programmatic screenshots of the main windows on demo data (QWidget.grab()).
Run:  python tools/screenshots.py [out_dir]     (default docs/screenshots)"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ittki.db.repository import Repository, User  # noqa: E402
from ittki.demo import load_demo  # noqa: E402
from ittki.services import Service  # noqa: E402
from ittki.ui.app import make_app  # noqa: E402
from ittki.ui.dialogs import AssessmentDialog  # noqa: E402
from ittki.ui.main_window import MainWindow  # noqa: E402

TODAY = date(2026, 10, 11)


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    app = make_app(["shots"])
    tmp = tempfile.mkdtemp()
    repo = Repository(Path(tmp) / "demo.sqlite3")
    load_demo(repo)
    svc = Service(repo, today=lambda: TODAY)
    user = User("Raxmatullayev S.N.", "accountant")
    w = MainWindow(svc, user)
    w.resize(1400, 860)
    w.show()
    shots = []

    def grab(widget, name):
        app.processEvents()
        widget.grab().save(str(out / f"{name}.png"))
        shots.append(name)

    for i, name in enumerate(("01_bosh_sahifa", "02_loyihalar", "03_nazorat", "04_hisobotlar", "05_sozlamalar",
                              "06_audit_jurnali")):
        w.show_page(i)
        grab(w, name)

    ids = {p.code: p.id for p in repo.projects()}
    tabs = {"FLOT": [(0, "10_karta_malumot"), (1, "11_karta_bosqichlar"), (3, "13_karta_xarajatlar"),
                     (4, "14_karta_qaror_FLOT"), (5, "15_karta_provodkalar"), (6, "16_karta_amortizatsiya"),
                     (7, "17_karta_solishtirma_FLOT")],
            "ATJBT": [(2, "12_karta_mezonlar_ATJBT"), (4, "14_karta_qaror_ATJBT"), (7, "17_karta_solishtirma_ATJBT")],
            "GIDRO": [(4, "14_karta_qaror_GIDRO"), (5, "15_karta_provodkalar_GIDRO")]}
    for key, items in tabs.items():
        code = next(c for c in ids if key in c)
        card = w.open_project(ids[code])
        card.resize(1400, 860)
        for idx, name in items:
            card.tabs.setCurrentIndex(idx)
            grab(card, name)
        card.close()

    pid = ids[next(c for c in ids if "ATJBT" in c)]
    d = AssessmentDialog(repo, user, pid, TODAY, repo.assessments(pid)[-1])
    d.show()
    grab(d, "20_dialog_yangi_baho")
    d.close()
    w.close()
    repo.close()
    print(f"{len(shots)} screenshots -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "screenshots")
