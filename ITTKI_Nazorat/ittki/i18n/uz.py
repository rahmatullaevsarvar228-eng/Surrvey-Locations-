"""O'zbek tili (lotin). All user-visible strings live here; ru.py can be added with the same keys."""

APP_NAME = "ITTKI Nazorat"
APP_SUBTITLE = "ITTKI xarajatlarini hisobga olish, kapitallashtirish va nazorat (BHMS 11 (2024) | IAS 38)"
DEMO_MARK = "Shartli misol, \"Olmaliq KMK\" AJ faoliyati yo'nalishlari asosida"

FW = {"IAS38": "IAS 38", "NAS11": "BHMS 11"}

# ------------------------------------------------------------------ enumerations
SCOPE = {
    "rnd": "ITTKI",
    "mineral_exploration": "Geologik qidiruv",
    "contract_for_customer": "Buyurtma asosida (boshqa tashkilot uchun)",
}
STAGE = {
    "research": "Tadqiqot",
    "development": "Ishlanma",
    "ready": "Foydalanishga tayyor",
    "abandoned": "To'xtatilgan",
}
ANSWER = {"yes": "Ha", "no": "Yo'q", "expert": "Ekspert bahosi talab etiladi"}
STATUS = {"met": "Bajarilgan", "no": "Yo'q", "pending": "Kutilmoqda"}
TREATMENT = {"capitalize": "Kapitallashtirish", "expense": "Xarajat"}
DECISION = {
    "XARAJAT SIFATIDA TAN OLINADI": "XARAJAT SIFATIDA TAN OLINADI",
    "KAPITALLASHTIRILADI": "KAPITALLASHTIRILADI",
    "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN": "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN",
    "STANDART QO'LLANILMAYDI": "STANDART QO'LLANILMAYDI",
}
DECISION_SHORT = {
    "XARAJAT SIFATIDA TAN OLINADI": "Xarajat",
    "KAPITALLASHTIRILADI": "Kapitallashtiriladi",
    "KAPITALLASHTIRILGAN, KEYIN HISOBDAN CHIQARILGAN": "Hisobdan chiqarilgan",
    "STANDART QO'LLANILMAYDI": "Qo'llanilmaydi",
}
CRITERION = {
    "K1_technical_feasibility": "K1. Texnik jihatdan amalga oshirish mumkinligi",
    "K2_intention": "K2. Yakunlash va foydalanish/sotish niyati",
    "K3_ability_use_or_sell": "K3. Foydalanish yoki sotish qobiliyati",
    "K4_future_benefits": "K4. Kelajakdagi iqtisodiy naf / bozor mavjudligi",
    "K5_adequate_resources": "K5. Yetarli texnik, moliyaviy va boshqa resurslar",
    "K6_reliable_measurement": "K6. Xarajatlarni ishonchli o'lchash",
    "K7_clearly_defined": "K7. Mahsulot/jarayon aniq belgilangan (identifikatsiya)",
}
CATEGORY = {
    "salary": "Ish haqi (ITTKI xodimlari)",
    "materials": "Materiallar",
    "services": "Tashqi tashkilotlar xizmatlari",
    "depreciation": "ITTKIda foydalanilgan AV amortizatsiyasi",
    "direct_overhead": "To'g'ridan-to'g'ri ustama xarajatlar",
    "patent_amortization": "Patent/litsenziyalar amortizatsiyasi",
    "legal_registration": "Huquqlarni ro'yxatdan o'tkazish",
    "selling": "Sotish xarajatlari",
    "general_admin": "Umumiy ma'muriy xarajatlar",
    "training": "Xodimlarni o'qitish",
    "other": "Boshqa (loyihaga bevosita taalluqli emas)",
}
EVIDENCE_TYPES = ["Buyruq", "TEI", "Smeta", "Bozor tahlili", "Sinov dalolatnomasi", "Shartnoma",
                  "Bayonnoma", "Ekspert xulosasi", "Boshqa"]
ROLE = {"leader": "Loyiha rahbari", "accountant": "Buxgalter", "auditor": "Ichki auditor / Audit qo'mitasi"}
LEVEL = {"high": "Yuqori", "medium": "O'rta", "info": "Ma'lumot"}
PROJECT_STATUS = {"active": "Faol", "ready": "Foydalanishga tayyor", "abandoned": "To'xtatilgan"}

PERM_ACTION = {
    "project": "loyiha ma'lumotlarini saqlash",
    "stage": "bosqichni o'zgartirish",
    "assessment": "mezonlar bahosini saqlash",
    "cost": "xarajatlarni kiritish, tahrirlash va o'chirish",
    "import": "xarajatlarni Exceldan import qilish",
    "impairment": "qadrsizlanish hodisasi va testlarini kiritish",
    "settings": "sozlamalarni saqlash",
    "report": "hisobotlarni tuzish",
}

JOURNAL_OPS = {
    "expense": "Xarajat sifatida tan olindi",
    "capitalize": "Kapitallashtirildi",
    "nas_writeoff": "BHMS 11, 18-band: hisobdan chiqarish",
    "pre_impairment": "Qadrsizlanish (tayyor bo'lgunga qadar)",
    "abandon_writeoff": "Loyiha to'xtatildi: hisobdan chiqarish",
    "transfer": "Aktiv foydalanishga tayyor",
    "amortization": "Amortizatsiya",
    "impairment": "Qadrsizlanish",
    "disposal_accum": "Chiqib ketish: jamlangan amortizatsiya",
    "disposal_residual": "Chiqib ketish: qoldiq qiymat",
}

# ------------------------------------------------------------------ controls M10
CONTROL_TITLE = {
    "E1": "'Ha' javobi dalil hujjatisiz",
    "E2": "Ishlanma bosqichida xarajatlar uzoq vaqt xarajatga o'tmoqda",
    "E3": "Ishlanmaga o'tgandan keyin mezonlar baholanmagan",
    "E4": "Xarajatlar byudjetdan oshdi",
    "E5": "Qadrsizlanish testi o'tkazilmagan (IAS 36.10(a))",
    "E6": "'Ekspert bahosi' javobi uzoq vaqt hal qilinmagan",
    "E7": "Ruxsat etilmagan toifadagi xarajat",
    "E8": "Foydali xizmat muddati ko'rsatilmagan",
    "E9": "BHMS ↔ MHXS farqi chegaradan katta",
    "E10": "Loyiha bo'yicha uzoq vaqt faoliyat yo'q",
}
CONTROL_MSG = {
    "E1": "{date}: {criterion} = 'Ha', lekin dalil hujjati yo'q — bajarilmagan deb hisoblanadi",
    "E2": "{fw}: {since} dan beri mezonlar bajarilmagan ({days} kun), xarajatlar xarajatga o'tmoqda — bahoni qayta ko'rib chiqing",
    "E3": "Ishlanma {start} da boshlangan, {days} kun ichida mezonlar baholanmagan",
    "E4": "Xarajatlar {total} so'm, byudjet {budget} so'm ({pct}% oshdi) — K5 ni qayta ko'rib chiqing",
    "E5": "{year} yil: foydalanishga tayyor bo'lmagan nomoddiy aktiv qadrsizlanish testidan o'tkazilmagan",
    "E6": "{criterion}: {since} dan beri 'Ekspert bahosi' ({days} kun)",
    "E7": "{date}: {category} {amount} so'm — {fw} bo'yicha avtomatik xarajatga o'tkazildi",
    "E8": "Aktiv {date} da foydalanishga tayyor, lekin foydali xizmat muddati ko'rsatilmagan",
    "E9": "{date} holatiga balans qiymatlari farqi {diff} so'm (IAS 38: {ias}, BHMS 11: {nas})",
    "E10": "Oxirgi faoliyat {last}; {months} oydan ortiq xarajat ham, baho ham yo'q — loyiha amalda to'xtatilganmi?",
}

# ------------------------------------------------------------------ UI
UI = {
    # navigation
    "nav.home": "Bosh sahifa",
    "nav.projects": "Loyihalar",
    "nav.controls": "Nazorat",
    "nav.reports": "Hisobotlar",
    "nav.settings": "Sozlamalar",
    "nav.audit": "Audit jurnali",
    # user
    "user.title": "Foydalanuvchi",
    "user.name": "F.I.Sh.",
    "user.role": "Rol",
    "user.prompt": "Ishni boshlash uchun F.I.Sh. va rolingizni kiriting",
    "user.change": "Foydalanuvchini almashtirish",
    "user.readonly": "Ichki auditor faqat ko'rish huquqiga ega",
    "perm.denied": "Ruxsat yo'q: «{action}» amalini faqat {allowed} bajara oladi.\nSizning rolingiz: {role}.\n"
                   "Urinish audit jurnaliga yozildi.",
    # home
    "home.title": "Umumiy ko'rsatkichlar",
    "home.projects": "Loyihalar",
    "home.capitalized": "Kapitallashtirilgan",
    "home.expensed": "Xarajatga o'tkazilgan",
    "home.exceptions": "Istisnolar",
    "home.as_of": "Sana holatiga",
    "home.demo": "Demo ma'lumotlarni yuklash",
    "home.demo_done": "Demo ma'lumotlar yuklandi",
    "home.demo_exists": "Demo loyihalar allaqachon mavjud",
    "home.backup": "Zaxira nusxa",
    "home.backup_done": "Zaxira nusxa saqlandi: {path}",
    "home.by_project": "Loyihalar bo'yicha",
    # projects
    "projects.new": "Yangi loyiha",
    "projects.open": "Ochish",
    "projects.search": "Qidirish (kod, nom)...",
    "projects.all": "Barchasi",
    "projects.filter_status": "Holat",
    "projects.filter_stage": "Bosqich",
    "projects.filter_decision": "Qaror (IAS 38)",
    # columns
    "col.code": "Kod",
    "col.name": "Nomi",
    "col.type": "Turi",
    "col.stage": "Bosqich",
    "col.status": "Holat",
    "col.leader": "Rahbar",
    "col.budget": "Byudjet",
    "col.costs": "Xarajatlar",
    "col.date": "Sana",
    "col.amount": "Summa",
    "col.category": "Toifa",
    "col.document": "Birlamchi hujjat",
    "col.comment": "Izoh",
    "col.treatment": "Qaror",
    "col.reason": "Sabab",
    "col.standard": "Standart bandi",
    "col.debit": "Debet",
    "col.credit": "Kredit",
    "col.operation": "Operatsiya",
    "col.period": "Davr",
    "col.opening": "Davr boshiga",
    "col.amortization": "Amortizatsiya",
    "col.impairment": "Qadrsizlanish",
    "col.closing": "Davr oxiriga",
    "col.code_exc": "Kod",
    "col.level": "Daraja",
    "col.project": "Loyiha",
    "col.message": "Tavsif",
    "col.when": "Vaqt",
    "col.who": "Kim",
    "col.role": "Rol",
    "col.action": "Amal",
    "col.object": "Obyekt",
    "col.before": "Avval",
    "col.after": "Keyin",
    "col.stage_from": "Avvalgi bosqich",
    "col.stage_to": "Yangi bosqich",
    "col.criterion": "Mezon",
    "col.answer": "Javob",
    "col.evidence": "Dalil hujjati",
    "col.indicator": "Ko'rsatkich",
    "col.ias": "IAS 38",
    "col.nas": "BHMS 11",
    "col.diff": "Farq",
    # project card
    "card.title": "Loyiha kartasi",
    "tab.info": "Ma'lumot",
    "tab.stages": "Bosqichlar",
    "tab.criteria": "Mezonlar",
    "tab.costs": "Xarajatlar",
    "tab.decision": "Qaror",
    "tab.journal": "Provodkalar",
    "tab.amort": "Amortizatsiya",
    "tab.reconcile": "Solishtirma",
    "f.code": "Loyiha kodi",
    "f.name": "Loyiha nomi",
    "f.type": "Loyiha turi",
    "f.department": "Bo'linma",
    "f.leader": "Loyiha rahbari",
    "f.start": "Boshlanish sanasi",
    "f.budget": "Byudjet (so'm)",
    "f.separable": "Tadqiqot va ishlanma bosqichlarini ajratish mumkin (IAS 38.53)",
    "f.dev_start": "Ishlanma bosqichi boshlangan sana",
    "f.ready": "Foydalanishga tayyor (qabul dalolatnomasi) sanasi",
    "f.abandoned": "To'xtatilgan sana",
    "f.life": "Foydali xizmat muddati (oy)",
    "f.benefit": "Kutilayotgan sof iqtisodiy naf (so'm, ixtiyoriy; BHMS 11, 13-band)",
    "f.note": "Izoh",
    "f.demo": "Shartli misol",
    "f.not_set": "ko'rsatilmagan",
    "f.impairment": "Qadrsizlanish hodisasi",
    "f.imp_date": "Hodisa sanasi",
    "f.imp_amount": "Qoplanadigan summa (so'm)",
    "f.imp_tests": "O'tkazilgan qadrsizlanish testlari",
    "f.add_test": "Test qo'shish",
    "btn.save": "Saqlash",
    "btn.cancel": "Bekor qilish",
    "btn.add": "Qo'shish",
    "btn.edit": "Tahrirlash",
    "btn.delete": "O'chirish",
    "btn.import": "Exceldan import",
    "btn.export": "Excelga eksport",
    "btn.new_assessment": "Yangi baho",
    "btn.save_draft": "Qoralama sifatida saqlash",
    "btn.stage": "Bosqichni o'zgartirish",
    "btn.close": "Yopish",
    "btn.refresh": "Yangilash",
    "btn.choose_file": "Fayl tanlash...",
    "stage.history": "Bosqichlar tarixi (o'chirib bo'lmaydi)",
    "stage.current": "Joriy bosqich",
    "stage.to": "Yangi bosqich",
    "stage.date": "O'tish sanasi",
    "stage.need_ready": "Foydalanishga tayyor bosqichi uchun qabul dalolatnomasi sanasi va foydali xizmat muddati kerak (aks holda E8)",
    "crit.history": "Baholar tarixi (yangi baho eskisini o'chirmaydi)",
    "crit.date": "Baho sanasi (shu sanadan kapitallashtirishga ruxsat)",
    "crit.draft": "qoralama",
    "crit.status": "Holat",
    "crit.need_evidence": "'Ha' javobi uchun dalil hujjati majburiy: {criterion}.\nHujjat kiriting yoki qoralama sifatida saqlang (E1 istisnosi yuzaga keladi).",
    "crit.ev_type": "Hujjat turi",
    "crit.ev_number": "Raqami",
    "crit.ev_date": "Sanasi",
    "crit.ev_file": "Fayl (ixtiyoriy)",
    "crit.k3_note": "K3 BHMS 11 da alohida mezon emas",
    "cost.total": "Jami xarajatlar",
    "cost.new": "Yangi xarajat",
    "cost.imported": "{n} ta xarajat import qilindi",
    "cost.import_errors": "Import xatolari",
    "dec.title": "Qaror",
    "dec.decision": "Loyiha bo'yicha qaror",
    "dec.capitalized": "Kapitallashtirilgan",
    "dec.expensed": "Xarajatga o'tkazilgan",
    "dec.writeoff": "Hisobdan chiqarilgan",
    "dec.amort_months": "Amortizatsiya muddati (oy)",
    "dec.carrying": "Balans qiymati (bugun)",
    "dec.first_met": "Mezonlar bajarilgan sana",
    "dec.status_today": "Mezonlar holati (bugun)",
    "dec.warnings": "Ogohlantirishlar",
    "dec.ref": "Qo'llaniladigan standart",
    "rec.date": "Solishtirma sanasi",
    "rec.capitalized": "Kapitallashtirilgan",
    "rec.carrying": "Balans qiymati",
    "rec.amort_months": "Amortizatsiya muddati (oy)",
    "rec.expensed": "Xarajatga o'tkazilgan",
    "rec.reasons": "Farq sabablari",
    "rec.total": "Jami",
    "rec.all": "Barcha loyihalar bo'yicha",
    "amort.fw": "Standart",
    "amort.empty": "Amortizatsiya jadvali yo'q",
    # reports
    "rep.title": "Hisobotlar",
    "rep.period_from": "Davr boshi",
    "rep.period_to": "Davr oxiri",
    "rep.amort": "Amortizatsiya jadvali (Excel)",
    "rep.reconcile": "BHMS ↔ MHXS solishtirma (Excel)",
    "rep.costs": "Xarajatlar jurnali va qarorlar (Excel)",
    "rep.note": "Moliyaviy hisobotga izoh (Word)",
    "rep.audit": "Audit qo'mitasi uchun hisobot (PDF)",
    "rep.audit_xlsx": "Istisnolar hisoboti (Excel)",
    "rep.template": "Xarajatlar import shabloni (Excel)",
    "rep.saved": "Hisobot saqlandi: {path}",
    "rep.signer": "Imzolovchi",
    # settings
    "set.title": "Sozlamalar",
    "set.org": "Tashkilot nomi",
    "set.lang": "Interfeys tili",
    "set.accounts": "Hisobvaraqlar (BHMS 21 (2024))",
    "set.sources": "Manba hisobvaraqlari (toifa bo'yicha)",
    "set.amort_start": "Amortizatsiya boshlanishi",
    "set.nas_max": "BHMS 11 bo'yicha maksimal muddat (oy)",
    "set.categories": "Aktiv qiymatiga kiritiladigan toifalar",
    "set.thresholds": "Nazorat chegaralari",
    "set.saved": "Sozlamalar saqlandi",
    "set.invalid": "Noto'g'ri qiymat: {error}",
    "acc.expense": "Xarajat sifatida tan olingan xarajatlar (Dt)",
    "acc.capitalize": "Kapitallashtiriladigan xarajatlar (Dt)",
    "acc.asset": "Tayyor nomoddiy aktiv (Dt)",
    "acc.accumulated": "Jamlangan amortizatsiya va qadrsizlanish (Kt)",
    "acc.amortization_debit": "Amortizatsiya (Dt): 9420 / 2010 / 2510",
    "acc.writeoff": "Hisobdan chiqarish, qadrsizlanish (Dt)",
    "amort_start.auto": "Avtomatik (1-sanada bo'lsa — shu oydan, aks holda keyingi oydan)",
    "amort_start.same_month": "Shu oydan",
    "amort_start.next_month": "Keyingi oydan",
    "thr.e2_days": "E2: kunlar",
    "thr.e3_days": "E3: kunlar",
    "thr.e4_pct": "E4: byudjetdan oshish, %",
    "thr.e6_days": "E6: kunlar",
    "thr.e9_amount": "E9: farq chegarasi, so'm",
    "thr.e10_months": "E10: oylar",
    # controls window
    "ctl.title": "Nazorat: istisnolar",
    "ctl.count": "{n} ta istisno",
    "ctl.level_all": "Barcha darajalar",
    # misc
    "msg.error": "Xato",
    "msg.info": "Ma'lumot",
    "msg.confirm": "Tasdiqlash",
    "msg.confirm_delete": "Tanlangan yozuvni o'chirishni tasdiqlaysizmi?",
    "msg.required": "Majburiy maydon to'ldirilmagan: {field}",
    "msg.code_exists": "Bunday kodli loyiha mavjud",
    "msg.select_row": "Avval qatorni tanlang",
    "sum": "so'm",
    "yes": "Ha",
    "no": "Yo'q",
}


def t(key: str, **kw) -> str:
    s = UI.get(key, key)
    return s.format(**kw) if kw else s


def money(v) -> str:
    """1234567 -> '1 234 567'."""
    if v is None:
        return ""
    return f"{int(v):,}".replace(",", " ")


def fdate(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""

# ------------------------------------------------------------------ M8 reconciliation reasons
REC_REASON = {
    "row": "{date} {category} {amount} so'm: IAS 38 — {ias}, BHMS 11 — {nas}",
    "k3": "K3 (foydalanish yoki sotish qobiliyati) bajarilmagan — IAS 38 bo'yicha xarajatga, BHMS 11 bo'yicha "
          "kapitallashtirilgan (BHMS 11 da alohida mezon yo'q)",
    "months": "Amortizatsiya muddati: IAS 38 — {ias} oy, BHMS 11 — {nas} oy (BHMS 11, 16-band: 5 yildan oshmaydi)",
    "nas_writeoff": "BHMS 11, 18-band bo'yicha {amount} so'm hisobdan chiqarilgan; IAS 38 bo'yicha faqat "
                    "qadrsizlanish belgisi (IAS 36.9, 36.12)",
    "limit": "BHMS 11, 13-band: kutilayotgan sof nafdan oshgan {amount} so'm xarajatga o'tkazilgan; IAS 38 da "
             "tan olishda chegara yo'q",
    "none": "Farq yo'q",
    "scope": "Standart qo'llanilmaydi",
}
