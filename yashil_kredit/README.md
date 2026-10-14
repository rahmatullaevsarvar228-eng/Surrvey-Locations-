# GreenCredit — yashil kredit uchun lokal dastur

Muallif: **Rahmatullayev Sarvar**

Kichik biznes uchun Windows dasturi (`.exe`). Internetsiz ishlaydi, barcha ma'lumotlar
shu kompyuterdagi SQLite bazasida saqlanadi (`%APPDATA%\GreenCredit\greencredit.db`).

## Uchta tugma

1. **Ma'lumot kiritish** — korxona, o'tgan yilning 12 oylik elektr (kVt·soat) va gaz (m³)
   hisoblari, tariflar va rejalashtirilgan loyiha (narxi, quyosh panellari quvvati, tejash foizlari).
2. **Foyda hisobi (ROI)** — dastur o'zi hisoblaydi: yillik tejash, o'zini oqlash muddati,
   10 yilda jami tejash, ROI, CO₂ kamayishi, oddiy va yashil kredit taqqoslash, Green Score.
3. **Bank uchun pasport** — bir tugma bilan Green Score bo'lgan PDF hisobot ("Yashil pasport").

Qo'shimcha: **Saqlangan hisoblar** (tarix) va **Sozlamalar** (farazlar: quyosh unumdorligi,
tarif o'sishi, emissiya koeffitsientlari, kredit foizlari).

## Hisob-kitob metodikasi

- Quyosh: `quvvat (kVt) × unumdorlik (kVt·soat/kVt/yil)`; faqat korxonaning o'z iste'molini
  qoplaydigan qismi hisobga olinadi, panel quvvati har yili degradatsiya foiziga kamayadi.
- Tejash har yili tarif o'sishi foiziga oshadi. O'zini oqlash — jami tejash investitsiyaga
  yetgan payt (yil ichida chiziqli).
- CO₂ = tejalgan kVt·soat × elektr koeffitsienti + tejalgan m³ × gaz koeffitsienti.
- **Green Score (0–100)** — dasturning ichki metodikasi, rasmiy sertifikat emas:
  CO₂ kamayishi 40 ball (bazaviy chiqindining 50%+ — to'liq), o'zini oqlash 30 ball
  (3 yil va kam — to'liq, 10 yil va ko'p — 0), energiya xarajatini tejash 30 ball (50%+ — to'liq).
  A ≥ 80, B ≥ 65, C ≥ 50, D < 50.

Standart farazlar (tariflar, koeffitsientlar, foizlar) taxminiy — ularni **Sozlamalar**da
mahalliy ma'lumotlarga moslang. "Namuna bilan to'ldirish" tugmasidagi raqamlar o'ylab topilgan.

## `.exe` ni olish

- **GitHub Actions orqali:** repozitoriyda *Actions → GreenCredit .exe* → oxirgi muvaffaqiyatli
  ishga tushirish → *Artifacts* bo'limidan `GreenCredit-windows` ni yuklab oling.
- **O'z kompyuteringizda:** Python 3.10+ o'rnating, `build_exe.bat` ni ikki marta bosing —
  tayyor fayl `dist\GreenCredit.exe` da paydo bo'ladi.

## Ishlab chiquvchilar uchun

```bash
pip install -r requirements.txt pytest
python run_app.py      # dasturni ishga tushirish
python -m pytest -q    # testlar
```

Tuzilishi: `greencredit/calc.py` (hisob-kitoblar), `db.py` (SQLite), `report.py` (PDF),
`app.py` (tkinter oynasi).
