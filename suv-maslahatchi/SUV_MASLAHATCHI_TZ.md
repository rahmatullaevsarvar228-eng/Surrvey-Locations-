# SUV MASLAHATCHI
### Fermerga har kuni «qachon va qancha sug‘orish»ni aytadigan raqamli agronom
**Tadqiqot · muhandislik texnik topshirig‘i · g‘alaba strategiyasi**

**Mualliflar:** Saynatov Yodgor, Raxmatullayev Sarvar
**Versiya:** 2.0 (yakuniy, qayta tekshirilgan) · 2026-yil oktabr

**Paket tarkibi:**
- `CLAUDE.md` — Claude Code uchun loyiha qoidalari;
- `SUV_MASLAHATCHI_TZ.md` — shu hujjat;
- `suv_engine.py` — tekshirilgan FAO-56 yadrosi;
- `tests/test_engine.py` — 10 ta test, hammasi o‘tgan.

---

## 0. Qisqacha (hakamga 20 soniyada)

> «O‘zbekistonda suvning qariyb 90% i dalaga ketadi, ammo bir kub suv dunyo o‘rtachasidan 25 barobar kam foyda beradi. Fermer qachon va qancha sug‘orishni ko‘z bilan hal qiladi. Bizning Telegram-botimiz har kuni ertalab aytadi: "bugun sug‘oring, ~300 m³/ga" yoki "kuting". Asosi — FAO xalqaro standarti va bepul ob-havo ma’lumoti. Uskuna shart emas. Harvard Business School professori Shawn Cole va Nobel mukofoti sovrindori Michael Kremer asos solgan PAD tashkiloti shunday telefon orqali maslahatni 1 milliondan ortiq fermerga yetkazadi. Biz bu yondashuvni O‘zbekiston suv muammosiga moslaymiz.»

---

## 1. Muammo — tekshirilgan faktlar

Har bir raqam birlamchi manbadan qayta tekshirildi (manbalar ro‘yxati oxirida).

| # | Fakt | Manba |
|---|---|---|
| F1 | Qishloq xo‘jaligi chuchuk suvning **qariyb 90%** ini oladi. Suv unumdorligi **$0,6/m³**, dunyo o‘rtachasi **$15/m³** (25 barobar farq) | Jahon banki, Kun.uz orqali (2022) |
| F2 | Suv zaxirasi bir yilda **6,5 mlrd m³ ga kamaydi** (2025-yil dekabr) | Suv xo‘jaligi vaziri, Kun.uz |
| F3 | Sug‘oriladigan yer **4,2 mln ga** | CABAR.asia (2024) |
| F4 | Nasoslar mamlakat elektr energiyasining **20%** ini sarflaydi. Energiya subsidiyasi yiliga **$450 mln** | IWMI (2021) |
| F5 | Farg‘onada amaldagi tartibda berilgan suvning **~20%** i ildiz zonasidan pastga singib ketadi | Pereira va boshq., *Agric. Water Manag.* 96(5), 2009 |
| F6 | Kuzgi bug‘doy tajribasi: **«ko‘proq sug‘orish qo‘shimcha hosil bermadi»** | Ibragimov, Evett va boshq. (Toshkent, 2000–2002) |
| F7 | Suv tejovchi texnologiyalar 2025-yilda **2,6 mln ga**, shundan tomchilatib **664 ming ga** | Asrakulov (2026) |
| F8 | Tadqiqotchilar **«sug‘orish bo‘yicha yo‘l-yo‘riq bo‘shlig‘i» (irrigation guidance gap)** haqida yozmoqda. Jizzaxda 32 ta tomchilatib sug‘oradigan fermaga tayyor jadvallar sinovdan o‘tkazildi | Shukurullaev, Hamidov, Liutin (2026) |
| F9 | Qishloq aholisining **93,9%** i internetdan foydalanadi (2025, yanvar–avgust) | Statistika agentligi |
| F10 | Davlat **«Smart Water»** — 11 446 ta qurilma suv sarfini onlayn kuzatadi, ammo fermerga «qachon sug‘orish»ni aytmaydi | 2024-yil 5-noyabr maqolasi |
| F11 | 2024-yil yanvar farmoni: «suv tekin» degan tushunchadan voz kechish | CABAR.asia |

---

## 2. «5 nega» — ildiz sabab tahlili (Toyota usuli)

**Muammo:** dalada suv isrof bo‘lmoqda (F1, F5).

1. **Nega?** Fermer ekin ehtiyojidan ortiq yoki noto‘g‘ri vaqtda sug‘oradi. Farg‘onada ~20% suv ildizdan pastga ketadi (F5).
2. **Nega?** U ekinga bugun qancha suv kerakligini bilmaydi. Qaror odat, navbat yoki «ko‘z bilan» qabul qilinadi.
3. **Nega?** Ekin ehtiyoji har kuni o‘zgaradi: issiqlik, shamol, ekin bosqichi va tuproqqa bog‘liq. Uni hisoblash uchun ET0, Kc va tuproq parametrlari kerak, fermerda esa bular yo‘q. Mavjud ma’lumot umumiy, mahalliy emas (CGIAR, 2023).
4. **Nega?** Agronom maslahati kam va qimmat, datchiklar qimmat. Raqamli agro-xizmatlar boshqa vazifalarni bajaradi: Smart-Agro.uz shartnomalar bilan ishlaydi, Smart Water kanal hisobini yuritadi.
5. **Nega?** Shu kungacha bu hisobni **arzon, ommaviy, o‘zbek tilida va har kuni** yetkazadigan kanal bo‘lmagan.

**Ildiz sabablar (3 ta bo‘shliq):**

| Bo‘shliq | Mazmuni | Bizning javob |
|---|---|---|
| **Ma’lumot** | Fermer bugungi ehtiyojni bilmaydi | Har kuni FAO-56 hisobi, Telegram’da |
| **Ishonch** | Umumiy maslahatga ishonilmaydi | «Nega?» tushuntirishi, mahalliy Kc, pilot natijasi qo‘shnilarga namuna |
| **Rag‘bat** | Suv arzon, fermer tejashga qiziqmaydi | To‘lovchi — klaster (hosil) va davlat (elektr). Uyushma paneli |

**Hozir nega mumkin bo‘ldi:**
- qishloqda internet 93,9%;
- ET0 prognozi bepul (Open-Meteo);
- FAO-56 xalqaro standart;
- Telegram — kundalik kanal.

---

## 3. Ilmiy poydevor — buyuk muhandis va professorlar

### 3.1. Jak Fresko (1916–2017) — tizimli muhandislik
Mustaqil o‘qib o‘rgangan sanoat dizayneri va futurolog. Uning siyosiy-iqtisodiy g‘oyalari bahsli, biz faqat muhandislik tamoyillarini olamiz.

| Tamoyil | Loyihada |
|---|---|
| **Tizimli yondashuv** | Dala → kanal → uyushma → havza. Har bir fermerning maslahati yig‘ilib, **uyushma uchun 7 kunlik suv talabi prognozi** bo‘ladi (`demand_forecast`). Dispetcher suvni oldindan rejalaydi |
| **Resursni fikr bilan emas, fan bilan boshqarish** | Har maslahat FAO-56 hisobiga asoslangan va mustaqil tekshiriladi |
| **Avtomatlashtirish (kibernatsiya)** | Hisob har kuni avtomatik. Kelajakda Smart Water va nasoslarni boshqarish bilan integratsiya |
| **G‘oyani vizual model bilan ko‘rsatish** | «Tuproq stakani»: ildiz zonasidagi suvni stakan kabi ko‘rsatamiz. Har kim tushunadi |
| **Inson uchun dizayn** | 6 ta savol, faqat tugmalar, bitta aniq javob |

### 3.2. Richard G. Allen va Luis S. Pereira — FAO-56 mualliflari
- FAO-56 (Allen, Pereira, Raes, Smith, 1998) — ekin suv iste’moli bo‘yicha jahon standarti.
- **Pereira aynan Farg‘ona paxtasi bo‘yicha sug‘orish tartibini o‘rgangan** (F5).
- Bizning yadro ularning usulini qo‘llaydi:
  - Kc egri chizig‘i;
  - 62-tenglama (Kc ni shamol va namlikka tuzatish);
  - ildizning o‘sishi;
  - TAW / RAW chegarasi.

### 3.3. Michael Kremer (Nobel 2019) va Shawn Cole (Harvard Business School) — PAD
- Ular **Precision Agriculture for Development (PAD)** tashkilotiga asos solgan. PAD telefon orqali agro-maslahatni **1 milliondan ortiq** fermerga yetkazadi.
- Fabregas, Kremer, Schilbach (*Science*, 2019): telefon orqali agro-ma’lumot hosilni **4%** ga oshirgan va tavsiya qilingan usullarni qabul qilish ehtimolini **22%** ga ko‘targan. Foyda xarajatdan taxminan **bir tartib (≈10 barobar)** yuqori.
- **Saboq:** oddiy matnli xabar ham fermer xulqini o‘zgartiradi. Telegram — to‘g‘ri kanal.

### 3.4. Esther Duflo (MIT, Nobel 2019), Kremer, Robinson — «turtki» (nudge)
- *American Economic Review* (2011): fermerga **to‘g‘ri paytda** berilgan kichik turtki katta subsidiyadan samaraliroq bo‘lishi mumkin.
- **Saboq:** xabar har kuni **07:00** da, aynan qaror qabul qilinadigan paytda keladi. Xabar ostida «✅ Sug‘ordim» tugmasi bor, harakat bir bosishda.

### 3.5. Hunt Allcott — ijtimoiy taqqoslash
- Energiya hisobotlarida qo‘shnilar bilan taqqoslash iste’molni **~2%** ga kamaytirgan (80 000 xonadonli randomizatsiyalangan tajriba).
- **Saboq:** 2-bosqichda «tumandagi o‘xshash dalalar o‘rtachasi» funksiyasi. U faqat real ma’lumot to‘plangandan keyin qo‘shiladi.

### 3.6. Mahalliy olimlar
- **Kenjabaev va boshq. (2020):** Farg‘onada dala o‘lchovlari bilan Kc aniqlangan.
  - Paxta: 0,15 / 1,15 / 0,45.
  - Bug‘doy: 0,26 / 1,03 / 0,56.
  - **Yadromiz shu mahalliy Kc dan foydalanadi** (FAO jadvali muqobil sifatida qoladi).
- **Liutin va Castañeda Dower (2023):** fermerlar texnologiyani qabul qilishdagi to‘siqlarni o‘rgangan.
- **Matyakubov va boshq. (2024):** paxtaning gidromodul rayonlari bo‘yicha mavsumiy me’yorlari: 2 800–6 200 m³/ga.

---

## 4. Fermerlar ovozi (ochiq manbalar; o‘zimiz so‘rov o‘tkazmadik)

**Yo‘ldosh Hasanov** («Zamin Angor» klasteri, Surxondaryo):
- «Ilgari bir gektarga 8 joydan suv quyardik va ko‘p suv isrof bo‘lardi.»
- Tomchilatib sug‘orishdan keyin paxta hosili 22–25 s/ga dan **40–42 s/ga** gacha oshgan.

**Zahriddin Jalolov** (fermer, Surxondaryo):
- «Foyda ololmay, kreditlarni o‘z vaqtida qaytara olmaymizmi, deb qo‘rqamiz.»

*(CABAR.asia, 2024-yil 9-fevral, ingliz tilidan tarjima.)*

**CGIAR intervyulari xulosasi** (2023):
- ma’lumot umumiy;
- fermerlar mahalliy namunani kutadi;
- suv va nasos xarajatini asosan davlat qoplaydi, shuning uchun tejash motivi kuchsiz.

> Sahnada: «Ochiq manbalardagi fermer intervyulari va 15 dan ortiq tadqiqot tahlili». **Hech qachon «biz fermerlarni so‘roq qildik» demang.**

---

## 5. Mahsulot

### 5.1. Telegram-bot «Suv Maslahatchi»

**Ro‘yxatdan o‘tish** (FSM, faqat tugmalar, ≤ 60 soniya):
1. 📍 Lokatsiya yuborish (yoki Viloyat → Tuman ro‘yxati).
2. 🌱 Ekin: Paxta / Kuzgi bug‘doy.
3. 🟫 Tuproq: Yengil / O‘rta / Og‘ir. Har tugma ostida oddiy belgi, masalan: «Qo‘lda siqsangiz sochilib ketadi».
4. 💧 Usul: Egat / Yomg‘irlatib / Tomchi.
5. 📐 Maydon (ga): tugmalar 1 / 5 / 10 / 50 / «Boshqa».
6. 📅 Ekish sanasi va oxirgi sug‘orish sanasi (kalendar tugmalari).

**Kunlik xabar (07:00).** Yadro `advice()` funksiyasining `matn` maydonidan olinadi:
```
💧 BUGUN SUG‘ORING
Paxta · 10 ga
≈ 313 m³/ga  (jami ≈ 3 130 m³)
Zaxira: ▰▰▰▱▱▱▱▱▱▱ 28%
[ ✅ Sug‘ordim ]  [ ❓ Nega? ]  [ 📅 7 kunlik reja ]
```

**Buyruqlar:**
- `/bugun` — bugungi maslahat;
- `/hafta` — 7 kunlik reja;
- `/sugordim` — sug‘orilganini qayd qilish;
- `/dala` — dala sozlamalari (bir nechta dala bo‘lishi mumkin);
- `/demo` — 2026-yil iyul arxivi bo‘yicha demo, sahna uchun;
- `/til` — til tanlash;
- `/yordam` — yordam.

**«✅ Sug‘ordim» tugmasi** hisobni yangilaydi va ma’lumot to‘playdi. Bu kelajakdagi kalibrlash va ijtimoiy taqqoslash uchun asos.

**Xato holatlari** foydalanuvchiga tushunarli tilda yoziladi, masalan: «Ob-havo ma’lumoti hozir olinmadi, 1 soatdan keyin qayta urinamiz».

### 5.2. Veb-ilova (sahna va B2B/B2G uchun)

**A. «Tuproq stakani» — asosiy sahna ekrani (vau-moment):**
- Ikki stakan yonma-yon: **«Odat»** (fermer odati: har N kunda M mm, qiymatlarni foydalanuvchi kiritadi) va **«Suv Maslahatchi»** (FAO-56).
- Stakan ichidagi suv sathi — ildiz zonasidagi suv zaxirasi. Shtrix chiziq — RAW chegarasi, ildizlar Zr bilan birga o‘sadi.
- Mavsum animatsiyasi (play / pauza / tezlik): kunlar o‘tadi, issiqda sath tushadi, yomg‘ir tomchilari tushadi, sug‘orishda stakan to‘ladi.
- **Ortiqcha suv ildiz ostiga qizil tomchilar bo‘lib oqadi.** Bu yo‘qotishni ko‘zga ko‘rinadigan qiladi.
- Pastda 3 ta katta raqam: sarflangan suv (m³/ga), yo‘qotish (m³/ga), stress kunlari. Ikkala usul taqqoslanadi.
- Ob-havo — 2026-yil haqiqiy arxivi (Open-Meteo), oldindan keshlangan.

**B. «Mavsum simulyatori»:**
- Kiritish: tuman, ekin, tuproq, usul, odat.
- Grafiklar: ET0 va ETc (kunlik), tuproq zaxirasi, sug‘orish ustunlari, yig‘ma natija.
- **Me’yor nazorati:** mavsumiy rejani gidromodul me’yori bilan solishtirish (ma’lumotnoma sifatida, Matyakubov 2024).

**C. «Uyushma paneli»** (Fresko: tizimli yondashuv):
- Namuna dalalar ro‘yxati, aniq belgi bilan: «Namuna (sintetik)».
- Keyingi 7 kunda uyushma bo‘yicha kunlik suv talabi (m³), ustunli grafik.
- Bu dispetcherga «qaysi kanalga qachon qancha suv berish»ni oldindan ko‘rsatadi.

**D. «Ilmiy asos»:**
- formulalar;
- parametrlar va ularning manbalari;
- validatsiya natijasi, halol (6-bo‘lim);
- cheklovlar;
- mualliflar.

### 5.3. Muhandislik arxitekturasi
- Arxitektura `CLAUDE.md` da batafsil yozilgan.
- **Toza yadro:** hisob-kitob faqat `engine/` da va testlangan.
- **Ob-havo:** grid-kesh (0,1°, 3 soat), qayta urinish, fayl zaxirasi.
- **Ma’lumotlar bazasi:** SQLite, keyinchalik PostgreSQL ga o‘tish oson.
- **Ikki tilli** (uz/ru), **proyektor rejimi** (`?stage=1`).
- **Sahna uchun:** internetsiz ishlash, `./run.sh` bitta buyruq bilan ishga tushiradi.

---

## 6. Yadro: tekshiruv va validatsiya (halol natijalar)

**Testlar: 10/10 o‘tdi.** Tekshirilganlar:
- Kc egri chizig‘i va 62-tenglama yo‘nalishi;
- ildiz o‘sishi;
- qo‘lda hisob: 7 kun × 6 mm × 1,15 = 48,3 mm ✓;
- yomg‘ir sug‘orishni kechiktiradi;
- tomchilatib sug‘orishda kunlarga bo‘lish;
- mavsumdan tashqari holat;
- maslahat bilan stress yo‘q;
- uyushma talabi;
- indikator.

**Dala o‘lchovlari bilan solishtirish:**
- Kenjabaev va boshq. (2020) Farg‘onada o‘lchagan: paxta mavsumida ET0 863 mm, **haqiqiy ETc 560 ± 50 mm** (nisbat 0,65).
- Bizning model (mahalliy Kc, ET0 jami 863 mm ga normallashtirilgan sintetik mavsum shakli bilan) **potensial ETc ni 690–730 mm** beradi (nisbat 0,80–0,85; mavsum uzunligiga bog‘liq).
- **Xulosa: model taxminan 25–30% yuqori.** Sabablari:
  1. Model stresssiz (potensial) iste’molni hisoblaydi, dala o‘lchovi esa fermer sharoitidagi haqiqiy iste’mol.
  2. Bosqich davomiyligi mahalliy emas.
  3. Sizot suvining hissasi hisobga olinmagan. Xorazm va Farg‘onada bu muhim (Pereira 2009).
- **Reja:** `kc_scale` hududiy kalibrlash koeffitsienti (yadroda tayyor) pilotda Smart Water hisoblagichlari va gidromodul me’yorlari asosida aniqlanadi. Ungacha maslahat **ehtiyotkor**: ekinni stressga tushirmaydi.
- **Hakamga aynan shunday ayting.** Bu zaiflik emas, ilmiy halollik belgisi.

---

## 7. Raqobat

| Kim | Nima qiladi | Farq |
|---|---|---|
| Smart-Agro.uz (RealSoft) | Agro-shartnomalar, 55+ xizmat; kompaniya ma’lumotiga ko‘ra 41 541 fermadan 155 tasida | Sug‘orish maslahati yo‘q |
| FAO CROPWAT | Mutaxassislar uchun kompyuter dasturi | Fermer uchun emas, kundalik prognoz yo‘q |
| Datchik tizimlari | Tuproq namligini o‘lchaydi | Uskuna va xizmat qimmat |
| Smart Water (davlat) | Kanal va nasoslarda hisob | Fermerga maslahat bermaydi. Biz uni to‘ldiramiz |
| PAD (xalqaro) | Telefon orqali agro-maslahat | O‘zbekistonda sug‘orish yo‘nalishida faol emas* |

\* PAD faoliyatining O‘zbekistonda yo‘qligi alohida tekshirilmagan. Sahnada «bizga ma’lum bo‘lgan raqobatchilar orasida» deb ayting.

---

## 8. Biznes-model

| Segment | Qiymat | To‘lov |
|---|---|---|
| **Paxta-to‘qimachilik klasterlari, yirik tomchilatib sug‘oradigan fermalar** | Uskuna bor, jadval yo‘q (F8). Hosil — ularning daromadi | Mavsumiy obuna (gektar asosida) + agronom paneli |
| **Davlat:** Suv xo‘jaligi vazirligi, suv iste’molchilari uyushmalari | Tejalgan suv = tejalgan elektr va subsidiya (F4). Uyushma talab prognozi | Hududiy litsenziya (B2G) |
| **Kichik fermerlar** | Bepul maslahat | Bepul: qamrov va ma’lumot uchun |

- Narxlar — gipoteza, pilotda tekshiriladi. Sahnada narx o‘ylab topmang.

---

## 9. Loyiha boshqaruvi (PMI usuli)

**Maqsad (SMART):** tanlovda 1-o‘rin. Natija: ishlaydigan bot + veb-demo + 5 daqiqalik pitch.

**Ishlar tuzilmasi (WBS):**
1. Yadro + testlar (tayyor).
2. Ob-havo xizmati va demo keshi.
3. Bot.
4. Veb: Tuproq stakani, Simulyator, Uyushma paneli, Ilmiy asos.
5. Pitch va slaydlar.
6. Repetitsiya va zaxira video.

**Jadval (kunlar):**

| Kun | Ish |
|---|---|
| K1 | Loyiha tuzilmasi, ob-havo xizmati, demo kesh, bot ro‘yxatdan o‘tish qismi |
| K2 | Bot maslahatlari, 07:00 xabar, «Nega?», «Sug‘ordim» |
| K3 | Veb: Tuproq stakani animatsiyasi |
| K4 | Simulyator, Uyushma paneli, Ilmiy asos, i18n, proyektor rejimi |
| K5 | Pitch, QR kod, video, 3 marta to‘liq repetitsiya |

**Kritik yo‘l:** demo kesh → Tuproq stakani → pitch.

**Xavflar reestri:**

| Xavf | Ehtimol | Ta’sir | Javob |
|---|---|---|---|
| Zalda internet yo‘q | O‘rta | Yuqori | Kesh, offline veb, video |
| Hakam: «model aniqmi?» | Yuqori | O‘rta | 6-bo‘lim: halol validatsiya + kalibrlash rejasi |
| Hakam: «fermer to‘laydimi?» | Yuqori | O‘rta | B2B/B2G modeli, F4, F11 |
| Oktyabrda mavsum yo‘q | Aniq | O‘rta | `/demo`: 2026-yil iyul arxivi |
| Bot tokeni yoki server ishlamay qoladi | Past | Yuqori | Lokal ishga tushirish, video |

---

## 10. Sahna ssenariysi (5 daqiqa)

| Vaqt | Ekran | Gap |
|---|---|---|
| 0:00–0:40 | F1 va F2 raqamlari, katta shriftda | «Bir kub suv: bizda $0,6, dunyoda $15. Bir yilda 6,5 mlrd kub kam suv.» |
| 0:40–1:00 | Hasanov iqtibosi | «Fermer suv isrof bo‘layotganini biladi. Ammo qachon va qancha kerakligini hech kim aytmaydi.» |
| 1:00–2:30 | **Tuproq stakani:** iyul mavsumi animatsiyasi, «Odat» va «Maslahat» | «Chap stakandan suv ildiz ostiga oqib ketyapti — bu isrof. O‘ngda suv kerak paytida va kerakli miqdorda berilyapti.» |
| 2:30–3:20 | **QR kod → bot**, zal o‘z telefonida sinaydi; spiker `/demo` ni ko‘rsatadi | «30 soniyada: bugun sug‘orish kerakmi va necha kub» |
| 3:20–3:50 | Uyushma paneli | «Har bir fermer maslahati yig‘ilib, kanal uchun 7 kunlik suv rejasi bo‘ladi. Bu tizimli yondashuv.» |
| 3:50–4:30 | Ilmiy asos: FAO-56, PAD (Harvard/Nobel), halol validatsiya | «Biz model raqamlarini Farg‘ona o‘lchovlari bilan solishtirdik va farqni ochiq ko‘rsatamiz.» |
| 4:30–5:00 | Biznes va yo‘l xaritasi | «Kichik fermerga bepul. Klaster va davlat to‘laydi. Keyingi qadam — bitta tumanda pilot.» |

---

## 11. Halollik qoidalari

**Deyish mumkin:**
- ✅ FAO-56 xalqaro standarti; mahalliy Kc (Kenjabaev 2020).
- ✅ «Model ehtiyotkor; pilotda kalibrlaymiz».
- ✅ PAD va Science (2019) natijalari: bu ularning natijasi, bizniki emas.

**Deyish mumkin emas:**
- ❌ «Bot X% suv tejaydi». O‘lchanmagan.
- ❌ «Fermerlar bilan suhbatlashdik».
- ❌ «Hosil kafolatlanadi».
- ❌ O‘ylab topilgan narx.

---

## 12. Hakamlar savollari

1. **Aniqligi qanday?**
   FAO-56 + mahalliy Kc. Dala o‘lchovlari bilan solishtirdik: model ~25–30% yuqori, ya’ni ehtiyotkor. Pilotda kalibrlaymiz (6-bo‘lim).
2. **Fermer Telegram ishlatadimi?**
   Qishloqda internet 93,9%. Bot faqat tugmalar bilan ishlaydi.
3. **Fermer nega ishonadi?**
   «Nega?» tushuntirishi, mahalliy ma’lumot, pilotdagi qo‘shni natijasi (CGIAR).
4. **Suv arzon bo‘lsa, nega tejaydi?**
   Shuning uchun to‘lovchi — klasterlar va davlat (elektrning 20%, $450 mln subsidiya). «Suv tekin» siyosati o‘zgarmoqda (F11).
5. **Telefon orqali maslahat ishlaydimi?**
   Science (2019) meta-tahlili: hosil +4%, usulni qabul qilish ehtimoli +22%. PAD 1 mln+ fermerga yetkazmoqda.
6. **Sizot suvi-chi?**
   Hozir hisobga olinmagan. Bu ma’lum cheklov va yo‘l xaritasida bor (Pereira 2009).
7. **Raqobatchi?**
   7-bo‘lim.
8. **Nega siz?**
   Ma’lumotlar tahlili va dala tadqiqotlari tajribasi, Telegram-bot ishlab chiqish tajribasi.
9. **Mukofot nimaga ketadi?**
   Bitta tumanda pilot (hisoblagichlar bilan kalibrlash), agronom-konsultant, server.

---

## 13. Claude Code uchun prompt (to‘liq nusxalang)

```
Avval CLAUDE.md ni, keyin SUV_MASLAHATCHI_TZ.md ni to‘liq o‘qi. suv_engine.py va
tests/ — tekshirilgan yadro: uni engine/ ga ko‘chir, formulalarni qayta yozma.
Vazifa: TZ 5-bo‘limidagi bot va veb-ilovani CLAUDE.md dagi arxitektura, dizayn
tokenlari va sifat talablari bo‘yicha qur. Ish tartibi — TZ 9-bo‘limdagi K1–K4.
Vaqt kam: to‘xtamasdan ishla, har kun-bosqichdan keyin `make test` ni ishga tushir
va xatolarni o‘zing tuzat. Faqat jiddiy muammoda to‘xta.
Qat’iy: hech qanday raqam yoki natijani o‘ylab topma; namuna dalalar "Namuna (sintetik)"
deb belgilansin; interfeys o‘zbek tilida (lotin), o‘ va g‘ to‘g‘ri belgilar bilan;
sahna demosi internetsiz ishlasin (scripts/build_demo_cache.py internet bor paytda
2026-yil aprel–sentabr Jizzax arxiv ob-havosini keshga saqlaydi); BOT_TOKEN — .env da.
Oxirida: ishga tushirish buyruqlari, tayyor/ulgurilmagan ro‘yxati, ekran rasmlari.
```

---

## Manbalar (barchasi qayta tekshirildi)

1. Jahon banki, suv unumdorligi (Kun.uz, 2022) — https://kun.uz/en/news/2022/05/28/wb-agriculture-in-uzbekistan-is-one-of-the-most-inefficient-in-terms-of-water-consumption-in-the-world
2. Suv zaxiralari (Kun.uz, 2025-yil dekabr) — https://kun.uz/en/news/2025/12/19/uzbekistans-water-reserves-fall-by-65-billion-cubic-meters-year-on-year
3. CABAR.asia (2024), fermerlar va raqamlar — https://cabar.asia/en/uzbekistan-seeks-to-introduce-new-technologies-for-irrigation-of-agricultural-lands
4. IWMI (2021), nasos energiyasi — https://archive.iwmi.org/wle/news/research-shifts-policy-energy-subsidy-water-savings-uzbekistans-irrigated-heartland/
5. Pereira va boshq. (2009), *Agric. Water Manag.* 96(5) — https://ideas.repec.org/a/eee/agiwat/v96y2009i5p723-735.html
6. Ibragimov, Evett va boshq. (Toshkent tajribalari) — https://www.irrigation.org/IA/FileUploads/IA/Resources/TechnicalPapers/2003/CottonAndWinterWheatIrrigationSchedulingImprovementsInUzbekistan.pdf
7. Asrakulov (2026) — https://zenodo.org/records/21352371
8. Shukurullaev, Hamidov, Liutin (2026) — https://zenodo.org/records/23219108
9. Statistika agentligi (2025) — https://stat.uz/ru/press-tsentr/novosti-goskomstata/64381-ishlo-zhojlarda-yashovchilarning-93-9-foizi-internetdan-fojdalanadi-3
10. Smart Water (2024) — https://usbekistan.at/en/digitalization-makes-it-possible-to-rationally-solve-the-problems-of-water-shortages-in-uzbekistan/
11. CGIAR, Liutin va Castañeda Dower (2023) — https://www.cgiar.org/news-events/news/irrigation-innovation-navigating-challenges-in-uzbekistan-water-energy-food-environment-nexus
12. Kenjabaev va boshq. (2020), Farg‘ona Kc va ETc — https://staff.tiiame.uz/storage/users/617/articles/v3mfhWMlDfuvVDxlbLX5J6W21Gs4eEDda8YgY40f.pdf
13. Matyakubov va boshq. (2024), gidromodul me’yorlari — https://www.scitepress.org/Papers/2024/137732/137732.pdf
14. FAO-56 — https://www.fao.org/4/x0490e/x0490e0b.htm
15. Fabregas, Kremer, Schilbach (2019), *Science* — https://agrinatura-eu.eu/realizing-the-potential-of-digital-development-the-case-of-agricultural-advice/
16. Shawn Cole, HBS va PAD — https://heep.hks.harvard.edu/people/shawn-cole
17. PAD (Kremer — hammuassis) — https://precisiondev.org/tag/kremer/
18. Duflo, Kremer, Robinson (2011) — https://nber.org/papers/w15131
19. Allcott, ijtimoiy normalar — https://ceepr.mit.edu/workingpaper/social-norms-and-energy-conservation
20. Smart-Agro.uz (FAO Agritech Observatory) — https://agritechobservatory.review.fao.org/en/smart-agrouz
21. Open-Meteo (prognoz va arxiv) — https://open-meteo.com/en/docs/historical-weather-api
22. Jacque Fresco — https://en.wikipedia.org/wiki/Jacque_Fresco
