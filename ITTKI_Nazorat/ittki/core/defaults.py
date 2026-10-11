"""Default values for M12 settings, taken from tables M6 and M10 of the TZ.

These are only *defaults*: on first run they are copied into the `settings` table and from then
on the program reads account codes and thresholds from the database (editable in Sozlamalar).
The engine, journal and controls never contain account codes themselves.
"""

# M6. Chart of accounts BHMS 21 (2024), Appendix 1. Key -> (code, name).
DEFAULT_ACCOUNTS = {
    "expense": "9420",              # costs expensed (9420 Ma'muriy xarajatlar or 9430 by accounting policy)
    "capitalize": "0830",           # costs capitalized (author's proposal, see TZ M6)
    "asset": "0490",                # asset available for use (or 0410)
    "accumulated": "0590",          # accumulated amortization and impairment (0510 for 0410)
    "amortization_debit": "9420",   # 9420 / 2010 / 2510 by place of use (BHMS 11, 17-band)
    "writeoff": "9430",             # BHMS 11 18-band write-off, abandonment, impairment, disposal
}

# Source (credit) account of a cost by category. M6 gives defaults for the first six;
# for the rest the TZ is silent — 6010 is a placeholder the user is expected to review.
DEFAULT_SOURCE_ACCOUNTS = {
    "salary": "6710",
    "materials": "1010",
    "services": "6010",
    "depreciation": "0230",
    "patent_amortization": "0510",
    "direct_overhead": "2510",
    "legal_registration": "6010",
    "selling": "6010",
    "general_admin": "6010",
    "training": "6010",
    "other": "6010",
}

ACCOUNT_NAMES = {
    "0230": "Mashina va asbob-uskunalarning eskirishi",
    "0410": "Patentlar, litsenziyalar va nou-xau",
    "0490": "Boshqa nomoddiy aktivlar",
    "0510": "Patentlar, litsenziyalar va nou-xaularning amortizatsiyasi",
    "0590": "Boshqa nomoddiy aktivlarning amortizatsiyasi",
    "0830": "Nomoddiy aktivlarni xarid qilish",
    "1010": "Xom ashyo va materiallar",
    "2010": "Asosiy ishlab chiqarish",
    "2510": "Umumiy ishlab chiqarish xarajatlari",
    "6010": "Mol yetkazib beruvchilar va pudratchilarga to'lovlar",
    "6710": "Ish haqi bo'yicha xodimlar bilan hisob-kitoblar",
    "9420": "Ma'muriy xarajatlar",
    "9430": "Boshqa operatsion xarajatlar",
}

# Accounts that must never be used for R&D. 9410 = "Sotish xarajatlari" (TZ M6).
FORBIDDEN_ACCOUNTS = frozenset({"9410"})

# M10 thresholds.
DEFAULT_CONTROLS = {
    "e2_days": 90,
    "e3_days": 30,
    "e4_pct": 10,
    "e6_days": 60,
    "e9_amount": 0,      # so'm; 0 = report any NAS/IFRS difference
    "e10_months": 12,
}

DEFAULT_GENERAL = {
    "organization": '"Olmaliq KMK" AJ',
    "language": "uz",
    "amort_start": "auto",
    "nas_max_months": 60,
}
