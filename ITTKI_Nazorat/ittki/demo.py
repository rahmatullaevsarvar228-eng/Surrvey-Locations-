"""Demo data (TZ section 9): four CONDITIONAL projects. Real AGMK R&D project data do not exist —
every project is marked "Shartli misol"."""
from __future__ import annotations

from datetime import date as d

from .core.engine import CRITERIA
from .db.repository import (Answer, AssessmentRecord, CostRecord, EvidenceDoc, ImpairmentTest, ProjectRecord,
                            Repository, User)
from .i18n import uz

M = 1_000_000
LEADER = User("Demo: loyiha rahbari", "leader")
ACCOUNTANT = User("Demo: buxgalter", "accountant")

_DOCS = {
    "K1_technical_feasibility": "Sinov dalolatnomasi",
    "K2_intention": "Buyruq",
    "K3_ability_use_or_sell": "Bayonnoma",
    "K4_future_benefits": "Bozor tahlili",
    "K5_adequate_resources": "Smeta",
    "K6_reliable_measurement": "Smeta",
    "K7_clearly_defined": "TEI",
}


def _assessment(pid, code, on, draft=False, **override):
    ans = {}
    for i, k in enumerate(CRITERIA, 1):
        v = override.get(k[:2], "yes")
        missing = v == "yes_no_doc"
        v = "yes" if missing else v
        ev = EvidenceDoc(_DOCS[k], f"{code}/{on.year}-{i:02d}", on) if v == "yes" and not missing else None
        ans[k] = Answer(v, ev)
    return AssessmentRecord(pid, on, ans, is_draft=draft)


def _costs(pid, rows):
    return [CostRecord(pid, on, amt * M, cat, f"PD-{i:03d}", comment) for i, (on, amt, cat, comment) in
            enumerate(rows, 1)]


def load_demo(repo: Repository) -> int:
    """Creates the demo projects (skips ones that already exist). Returns how many were created."""
    created = 0
    mark = uz.DEMO_MARK

    # (1) flotation technology — capitalized, available for use, 96 months (IAS) vs 60 (BHMS 11)
    if not repo.project_by_code("DEMO-FLOT-01"):
        pid = repo.save_project(ProjectRecord(
            "DEMO-FLOT-01", "Mis-molibden rudalarini flotatsiya qilish texnologiyasini takomillashtirish",
            department="Mis boyitish fabrikasi, texnologiya bo'limi", leader="Demo: bosh texnolog",
            start_date=d(2024, 9, 2), budget=2_400 * M, useful_life_months=96, note=mark, is_demo=True), LEADER)
        repo.change_stage(pid, "development", d(2025, 2, 3), LEADER, "Texnik kengash qarori")
        repo.add_assessment(_assessment(pid, "FLOT", d(2025, 2, 20)), LEADER)
        repo.add_costs(_costs(pid, [
            (d(2024, 10, 15), 180, "salary", "Laboratoriya tadqiqotlari"),
            (d(2024, 12, 10), 95, "materials", "Ruda namunalari, reagentlar"),
            (d(2025, 2, 10), 60, "services", "Tashqi laboratoriya tahlili"),
            (d(2025, 3, 14), 420, "salary", "Tajriba qurilmasi loyihasi"),
            (d(2025, 5, 20), 610, "materials", "Tajriba-sanoat qurilmasi uskunalari"),
            (d(2025, 7, 11), 150, "depreciation", "Flotatsiya mashinalari amortizatsiyasi"),
            (d(2025, 9, 5), 35, "training", "Operatorlarni o'qitish"),
            (d(2025, 10, 17), 240, "direct_overhead", "Sex xarajatlari (bevosita)"),
            (d(2025, 12, 12), 18, "legal_registration", "Patent arizasi"),
            (d(2026, 1, 23), 130, "services", "Sanoat sinovlari"),
            (d(2026, 4, 10), 22, "general_admin", "Ma'muriy xarajatlar ulushi"),
        ]), ACCOUNTANT)
        repo.add_impairment_test(ImpairmentTest(pid, d(2025, 12, 22), "Qadrsizlanish testi 2025"), ACCOUNTANT)
        repo.change_stage(pid, "ready", d(2026, 3, 1), LEADER, "Qabul dalolatnomasi No 14")
        created += 1

    # (2) process control system — K3 'no' first: BHMS 11 capitalizes, IAS 38 does not (S4)
    if not repo.project_by_code("DEMO-ATJBT-02"):
        pid = repo.save_project(ProjectRecord(
            "DEMO-ATJBT-02", "Boyitish fabrikasining texnologik jarayonlarini avtomatlashtirilgan boshqarish "
                             "tizimi (ATJBT)",
            department="Avtomatlashtirish boshqarmasi", leader="Demo: ATJBT bo'limi boshlig'i",
            start_date=d(2025, 3, 3), budget=1_500 * M, useful_life_months=72, note=mark, is_demo=True), LEADER)
        repo.change_stage(pid, "development", d(2025, 9, 1), LEADER, "Texnik topshiriq tasdiqlandi")
        repo.add_assessment(_assessment(pid, "ATJBT", d(2025, 9, 15), K3="no", K5="expert"), LEADER)
        repo.add_assessment(_assessment(pid, "ATJBT", d(2025, 10, 1), K3="no"), LEADER)
        repo.add_assessment(_assessment(pid, "ATJBT", d(2026, 6, 1)), LEADER)
        repo.add_costs(_costs(pid, [
            (d(2025, 4, 18), 85, "services", "Mavjud tizim auditi"),
            (d(2025, 6, 20), 120, "salary", "Talablar tahlili"),
            (d(2025, 9, 25), 90, "salary", "Arxitektura loyihasi"),
            (d(2025, 11, 14), 260, "services", "Dasturiy ta'minot ishlab chiqish (pudratchi)"),
            (d(2026, 2, 13), 210, "materials", "Kontrollerlar, datchiklar"),
            (d(2026, 5, 15), 140, "salary", "Integratsiya"),
            (d(2026, 7, 17), 175, "services", "Sinov ishga tushirish"),
            (d(2026, 9, 11), 95, "salary", "Hujjatlashtirish"),
        ]), ACCOUNTANT)
        repo.add_impairment_test(ImpairmentTest(pid, d(2025, 12, 26), "Qadrsizlanish testi 2025"), ACCOUNTANT)
        created += 1

    # (3) new reagents — research only, everything expensed; no activity for >12 months (E10)
    if not repo.project_by_code("DEMO-REAG-03"):
        pid = repo.save_project(ProjectRecord(
            "DEMO-REAG-03", "Yangi flotatsiya reagentlarini tadqiq qilish (faqat tadqiqot)",
            department="Markaziy ilmiy-tadqiqot laboratoriyasi", leader="Demo: laboratoriya mudiri",
            start_date=d(2024, 6, 3), budget=300 * M, note=mark, is_demo=True), LEADER)
        repo.add_costs(_costs(pid, [
            (d(2024, 7, 12), 45, "salary", "Adabiyot tahlili, rejalashtirish"),
            (d(2024, 10, 18), 70, "materials", "Reagent namunalari"),
            (d(2025, 2, 14), 55, "services", "Xromatografik tahlil"),
            (d(2025, 6, 20), 40, "salary", "Natijalarni umumlashtirish"),
        ]), ACCOUNTANT)
        created += 1

    # (4) abandoned project — capitalized, then written off before availability (S7); E1 draft, E4 budget
    if not repo.project_by_code("DEMO-GIDRO-04"):
        pid = repo.save_project(ProjectRecord(
            "DEMO-GIDRO-04", "Mis eritish shlaklarini gidrometallurgik qayta ishlash (to'xtatilgan)",
            department="Mis eritish zavodi", leader="Demo: metallurgiya bo'limi boshlig'i",
            start_date=d(2024, 4, 1), budget=600 * M, useful_life_months=60, note=mark, is_demo=True), LEADER)
        repo.change_stage(pid, "development", d(2024, 11, 1), LEADER)
        repo.add_assessment(_assessment(pid, "GIDRO", d(2024, 11, 20), draft=True, K4="yes_no_doc"), LEADER)
        repo.add_assessment(_assessment(pid, "GIDRO", d(2025, 1, 15)), LEADER)
        repo.add_costs(_costs(pid, [
            (d(2024, 5, 17), 80, "salary", "Texnologik tadqiqot"),
            (d(2024, 12, 6), 110, "materials", "Tajriba partiyasi"),
            (d(2025, 2, 21), 230, "services", "Pilot qurilma loyihasi"),
            (d(2025, 6, 13), 190, "materials", "Pilot qurilma"),
            (d(2025, 10, 10), 75, "salary", "Pilot sinovlar"),
        ]), ACCOUNTANT)
        repo.add_impairment_test(ImpairmentTest(pid, d(2025, 12, 19), "Qadrsizlanish testi 2025"), ACCOUNTANT)
        repo.change_stage(pid, "abandoned", d(2026, 2, 2), LEADER,
                          "Pilot sinov natijalari iqtisodiy samarasiz — loyiha to'xtatildi")
        created += 1
    return created
