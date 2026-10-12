"""Sample reports on demo data (for the dissertation appendix).
Run:  python tools/samples.py [out_dir]     (default docs/samples)"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ittki import clock  # noqa: E402
from ittki.db.repository import Repository, User  # noqa: E402
from ittki.reports.excel import export_costs, export_findings, export_reconcile, export_schedule  # noqa: E402
from ittki.reports.pdf import export_audit_report  # noqa: E402
from ittki.reports.word import export_note  # noqa: E402
from ittki.services import Service  # noqa: E402

TODAY = date(2026, 10, 11)


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    clock.set_fixed(TODAY)                      # same fixed date as the screenshots
    repo = Repository(Path(tempfile.mkdtemp()) / "demo.sqlite3")
    svc = Service(repo)
    svc.load_demo(User("Raxmatullayev S.N.", "accountant"))
    st = svc.settings
    signer = User("Raxmatullayev S.N.", "auditor")
    an = svc.analyze_all()
    export_schedule(an, out / "amortizatsiya_jadvali.xlsx", st)
    export_reconcile(an, out / "BHMS_MHXS_solishtirma.xlsx", st)
    export_costs(an, out / "xarajatlar_jurnali.xlsx", st)
    export_findings(an, out / "istisnolar.xlsx", st, signer, TODAY)
    export_audit_report(an, out / "audit_qomitasi.pdf", st, signer, TODAY)
    an25 = svc.analyze_all(date(2025, 12, 31))
    export_note(an25, out / "izoh_BHMS11_IAS38_2025.docx", st, date(2025, 1, 1), date(2025, 12, 31))
    repo.close()
    print(f"samples -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "samples")
