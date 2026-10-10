# VIRTUAL DOUBLE-TRACK
### Bir yo‘lli temir yo‘lning raqamli egizagi — texnik topshiriq (Claude Code uchun) va g‘alaba strategiyasi

**Mualliflar:** Saynatov Yodgor, Raxmatullayev Sarvar
**Versiya:** 1.0 (yakuniy) · 2026-yil oktabr
**Fayllar:** `VDT_LOYIHA_TZ.md` (shu hujjat) + `vdt_engine.py` (tekshirilgan hisob yadrosi)

> **Qanday foydalanish kerak:** loyiha papkasini yarating, ikkala faylni unga joylang, shu papkada Claude Code’ni oching va 15-bo‘limdagi promptni nusxalab qo‘ying. Ishni qat’iy bosqichma-bosqich bajaring (11-bo‘lim) va har bir bosqichdan keyin tayyorlik mezonlarini tekshiring.

---

## 1. G‘oya — bir jumlada

**«Bir yo‘lli temir yo‘lning raqamli egizagi: mavjud relslardan ko‘proq foyda olishni ko‘rsatadi va yangi razyezdni qayerga qurish har bir dollarga eng ko‘p samara berishini hisoblaydi.»**

### Asosiy burilish: biz nimani sotamiz va nimani sotmaymiz

Biz **«poyezdlarni jonli boshqaradigan AI»** sotmaymiz. Bunday mahsulot hakamlarda darhol xavfsizlik, sertifikatlash va mavjud tizimlarga kirish haqida savollar tug‘diradi.

Biz **rejalashtirish vositasini (offline decision-support)** sotamiz:
1. **Jadvalni rejalashtirish.** Berilgan poyezdlar uchun uchrashuv va quvib o‘tish nuqtalarining eng yaxshi joyi va vaqtini topadi.
2. **Stress-test.** Lokomotiv buzilsa yoki peregon yopilsa nima bo‘lishini va jadvalni qanday qilib eng tez tiklashni ko‘rsatadi.
3. **Investitsiya simulyatori.** Qaysi bekatga qo‘shimcha yo‘l yoki razyezd qo‘shish eng katta samara berishini hisoblaydi.

**Qarorni inson qabul qiladi, biz hisob-kitobni beramiz.** Shu bilan xavfsizlik haqidagi savolga oldindan javob tayyor. Jonli boshqaruv yo‘l xaritasining 3-bosqichi, MVP emas.

---

## 2. Muammo: tekshirilgan faktlar

| Fakt | Manba |
|---|---|
| Umumiy foydalanishdagi tarmoq taxminan **90% bir yo‘lli**: 4 280,7 km bir yo‘lli va 493,4 km ikki yo‘lli | «O‘zbekiston temir yo‘llari», CAREC uchun taqdimot (2016-yil ma’lumoti; dolzarb ko‘rsatkichni tekshiring) |
| Jahon banki (2026-yil sentabr): koridorda **«operatsion, infratuzilmaga oid bo‘lmagan yaxshilanishlarga erishish eng ehtimoliy asosiy muammo»**. Shu bilan birga jismoniy tor joylar «asosan temir yo‘l segmentlarida» to‘plangan. O‘zbekiston 9 ta koridor davlatidan biri | World Bank, *Integration: World-Class Trade Logistics Along the Trans-Caspian Transport Corridor* |
| Tashqi yuklarning taxminan **70% Chuqursoy bekati orqali** o‘tadi, ba’zan ko‘p kunlik kechikishlar bo‘ladi | Kun.uz, 2025-yil 28-may |
| Buxoro–Miskin–Urganch–Xiva liniyasi: aralash harakat (yuk + yo‘lovchi), 2019-yilda 9,2 mln t yuk, 2030-yilga prognoz 17,6 mln t | AIIB loyiha hujjati |
| 2026–2030-yillarda yo‘lovchi va yuk tashish hajmini kamida 2 barobar oshirish maqsadi qo‘yilgan | Gazeta.uz, 2025-yil 13-noyabr |

**Xulosa:** tarmoq asosan bir yo‘lli, yuk oqimi esa o‘sib bormoqda. Ikkinchi yo‘l qimmat va uzoq quriladi. Shuning uchun mavjud relslardan maksimal foydalanish — bu dolzarb muammo.

---

## 3. Ilmiy va muhandislik asos: buyuk muhandis va professorlarning usullari

### 3.1. Jak Fresko (Jacque Fresco, 1916–2017) — tizimli muhandislik tafakkuri
Mustaqil o‘qib o‘rgangan sanoat dizayneri va futurolog, «The Venus Project» asoschisi. Uning **muhandislik tamoyillarini** qo‘llaymiz (siyosiy-iqtisodiy g‘oyalari bahsli, hakamlarga ularni keltirmang):

| Fresko tamoyili | Loyihamizda qo‘llanishi |
|---|---|
| **Tizimli yondashuv:** muammoni butun tizim sifatida ko‘rish | Bitta poyezdni emas, butun koridorni optimallashtiramiz |
| **Resurslardan oqilona foydalanish:** yangi narsa qurishdan oldin mavjudini to‘liq ishlatish | «Yangi rels emas, mavjud relsdan yangi quvvat» |
| **Qarorlar fikrga emas, ilmiy hisobga asoslansin** | Har bir natija baza bilan taqqoslanadi va mustaqil tekshiriladi |
| **G‘oyani vizual model orqali ko‘rsatish** (Fresko maketlar va renderlar bilan tushuntirgan) | Slaydlar o‘rniga jonli raqamli model |
| **Kibernetik (avtomatlashtirilgan) boshqaruv** | Hisobni mashina qiladi, qarorni inson tasdiqlaydi |

### 3.2. Leo Kroon va hamkasblari — Niderlandiya temir yo‘llari (Franz Edelman mukofoti, 2008)
«The New Dutch Timetable: The O.R. Revolution» loyihasi operatsion tadqiqotlar (OR) usullari bilan milliy temir yo‘l jadvalini qayta qurgani uchun dunyodagi eng nufuzli amaliy OR mukofotiga sazovor bo‘lgan.

**Saboq:** matematik model operator bilan birga qurilgandagina amalda ishlaydi. Bizning 1-pilotimiz ham operator bilan birga bo‘ladi.

### 3.3. D’Ariano, Pacciarelli, Pranzo (2007) — poyezdlarni rejalashtirish «job-shop» masalasi sifatida
*European Journal of Operational Research*, 183(2), 643–657. Poyezd harakatini bloklanuvchi resurslar (peregonlar) bo‘yicha rejalashtirish masalasi sifatida modellashtiradi.

**Saboq:** bizning modelimiz shu ilmiy oilaga kiradi: peregonlar `NoOverlap` resurs, bekatlar sig‘imli resurs. Bu «o‘ylab topilgan» emas, tan olingan yondashuv.

### 3.4. Yang va boshq. (2023, 2025) — bir yo‘lli tarmoqda chuqur o‘rganish (RL)
- Yang F. va boshq. (2023), *Transportation Research Part C*, 154, 104237.
- Yang F. va boshq. (2025), *Transportation Research Part C*, 178, 105215.

**Saboq:** katta tarmoqlarga kengaytirish uchun RL — bizning keyingi ilmiy bosqichimiz.

### 3.5. UIC 406 — temir yo‘l o‘tkazuvchanligini o‘lchashning xalqaro usuli
**Saboq:** keyingi bosqichda natijani xalqaro standart tilida ham ifodalaymiz (quvvat iste’moli, %).

### 3.6. Stiv Blank va Tom Eyzenmann (Harvard Business School) — mijozni o‘rganish
Eyzenmann ma’lumotiga ko‘ra, startaplarni o‘ldiradigan asosiy sabab — «soxta start»: mijozni o‘rganmasdan qurishni boshlash.

**Saboq:** kod bilan parallel ravishda 5–10 ta intervyu (dispetcher, logist, transport OTM o‘qituvchisi) o‘tkazamiz.

---

## 4. Prototip natijalari (biz o‘zimiz tekshirdik)

**Test sharoiti:**
- 12 bekatli sintetik uchastka, 18 ta poyezd (o‘sish ssenariysida 24 ta).
- Xavfsizlik oralig‘i (headway) 3 daqiqa.
- Har bir ssenariy uchun 10 xil tasodifiy variant (seed).
- AI hisobi har biri 8 soniya.
- Taqqoslash bazasi: FIFO dispetcher («kim birinchi kelsa, o‘sha birinchi ketadi»).

| Ssenariy | Umumiy kechikish (AI «umumiy» rejimi) | Ustuvor poyezdlar kechikishi, vaznli (AI «ustuvorlik» rejimi) | FIFO tupikka tushdi |
|---|---|---|---|
| Oddiy kun | **o‘rtacha −10,4%** (4,4% dan 18,7% gacha) | **o‘rtacha −28,4%** (14,0% dan 46,3% gacha) | 0 / 10 |
| Avariya (peregon 90 daqiqa yopiq) | o‘rtacha −6,9% (0% dan 22,1% gacha) | o‘rtacha −20,1% (2,7% dan 30,8% gacha) | **1 / 10** (15 ta poyezd to‘xtab qoldi, AI yechim topdi) |
| O‘sish +30% poyezd | o‘rtacha −6,2% (0,6% dan 16,9% gacha) | o‘rtacha −15,3% (1,3% dan 35,1% gacha) | 0 / 10 |

**Qo‘shimcha topilmalar:**
- **Mustaqil validator:** barcha 89 ta jadvalda (60 ta AI + 29 ta FIFO) **0 ta xavfsizlik buzilishi**.
- **Hisob vaqti muhim:** bitta ssenariyda 8 soniyada −10,6%, 60 soniyada **−23,2%**. Shuning uchun sahnada oldindan uzoq hisoblangan (keshdagi) natijani ko‘rsatamiz.
- **Kafolat:** AI dispetcher rejasidan boshlaydi va faqat yaxshilaydi, ya’ni **natija hech qachon FIFO dan yomon bo‘lmaydi**. Bu hakamlar uchun kuchli argument.
- **Investitsiya rejimi** ishlaydi, lekin bitta qo‘shimcha yo‘lning samarasi kichik va hisob shovqiniga yaqin. Shuning uchun nazorat guruhi va bir necha seed bilan uzoq (o‘nlab daqiqa) hisoblanadi va oldindan keshga saqlanadi (7.4-bo‘lim).

⚠️ **Bular sintetik ma’lumotdagi natijalar.** Sahnada faqat «modelda», «sintetik uchastkada» deb ayting. Hech qachon «O‘zbekiston temir yo‘llarida 30–40% oshadi» demang. Raqamlarni o‘zingiz qayta hisoblab tasdiqlang.

---

## 5. Nega g‘alaba qozonishi mumkin: hakamlar mezonlari bo‘yicha

| Hakam mezoni | Bizning javobimiz |
|---|---|
| Haqiqiy muammo | ~90% bir yo‘lli tarmoq, o‘sayotgan yuk oqimi, Jahon banki xulosasi |
| Ishlaydigan mahsulot | Slaydlar o‘rniga jonli demo: hisob sahnada bajariladi |
| Ilmiy asos | Constraint Programming (Google OR-Tools CP-SAT), D’Ariano 2007, Kroon 2008, Yang 2023/2025 |
| O‘lchanadigan natija | 30 ta ssenariy, baza bilan taqqoslash, mustaqil validator, ilmiy halollik |
| Biznes | Aniq mijoz va «tadqiqot → obuna» modeli (10-bo‘lim) |
| «Vau» effekti | «Avariya» tugmasi: oddiy dispetcher tupikka tushadi, AI soniyalarda jadvalni qayta tuzadi |

---

## 6. Sahnadagi demo ssenariysi (5–7 daqiqadan 3 daqiqa)

| Vaqt | Ekranda | Spiker gapi |
|---|---|---|
| 0:00–0:20 | «Koridor» ekrani: liniya sxemasi, 12 bekat | «Respublikamiz temir yo‘l tarmog‘ining qariyb 90% bir yo‘lli. Qarama-qarshi poyezdlar razyezdlarda bir-birini kutadi. Ikkinchi yo‘l qurish — yuzlab million dollar. Mavjud relsdan ko‘proq poyezd o‘tkazish mumkinmi?» |
| 0:20–1:10 | «Bugun vs AI» ekrani: chapda FIFO, o‘ngda AI. «Ishga tushirish» bosiladi, poyezdlar harakatlanadi, harakat grafigi chiziladi, kutish daqiqalari hisoblagichi o‘sadi | «Chapda — oddiy qoida bo‘yicha reja. O‘ngda — bizning optimallashtiruvchimiz. Poyezdlar bir xil, relslar bir xil, xavfsizlik qoidalari bir xil.» Yakuniy raqamda pauza qiling |
| 1:10–1:50 | «Favqulodda holat» tugmasi: peregon 90 daqiqaga yopiladi | Chapda kechikishlar o‘sadi yoki «TUPIK (DEADLOCK)» chiqadi. O‘ngda «AI jadvalni bir necha soniyada qayta tuzdi». Validator nishoni: «✓ 0 konflikt» |
| 1:50–2:40 | «Yangi razyezd qayerda?» ekrani: bekatlar reytingi (oldindan hisoblangan) | «Pul sarflashdan oldin modelimizda tekshiring: qo‘shimcha yo‘l qayerda haqiqatan samara beradi, qayerda pul behuda ketadi» |
| 2:40–3:00 | «Iqtisodiy samara» ekrani | «Mana shu — virtual ikkinchi yo‘l» |

**Zaxira reja:** demo videosini yozib oling. Sahnada nimadir buzilsa, videoni qo‘yasiz. Ilova **internetsiz** ishlashi shart.

---

## 7. Ilova ekranlari

- Interfeys tili: **o‘zbek tili (lotin)** asosiy, RU/EN almashtirgich bilan. Barcha matnlar i18n fayllarida saqlanadi.
- Har bir ekranning pastida: «Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar».

### 7.1. «Koridor» — sozlash
- Liniya sxemasi: bekatlar va har bir bekatdagi yo‘llar soni (1 = faqat asosiy yo‘l, 2 = asosiy + razyezd).
- Poyezdlar jadvali:
  - turi: yuk / yo‘lovchi / tezyurar;
  - yo‘nalish;
  - tezlik;
  - jo‘nash vaqti;
  - to‘xtash bekatlari;
  - ustuvorlik.
- Tayyor ssenariylar: **«Oddiy kun»**, **«Avariya»**, **«O‘sish +30%»**.
- Ekranda ko‘rinadigan belgi: **«Sintetik ma’lumotlar»**.

### 7.2. «Bugun vs AI» — asosiy ekran
- Ikkita **poyezdlar harakati grafigi** yonma-yon: X o‘qi — vaqt, Y o‘qi — bekatlar va km. Bu temir yo‘lchilar uchun standart vosita.
  - Poyezd chiziqlari turiga qarab rangli.
  - Uchrashuv va quvib o‘tish nuqtalari belgilangan.
  - Bekatda kutish gorizontal kesma sifatida ko‘rinadi.
- Tepada animatsion liniya sxemasi: poyezdlar vaqt shkalasi bo‘yicha sinxron harakatlanadi. Boshqaruv: play, pauza, tezlik ×1 / ×10 / ×60.
- Ko‘rsatkichlar paneli: katta raqamlar va farq foizda.
  - umumiy kechikish, daq;
  - o‘rtacha kechikish;
  - turlar bo‘yicha kechikish;
  - kutish to‘xtashlari soni;
  - oxirgi poyezdning yetib kelish vaqti.
- Validator nishoni: **«✓ 0 konflikt — xavfsizlik tekshirildi»**.
- AI maqsadi almashtirgichi: **«Umumiy kechikish» / «Ustuvorlik»**.
- Hisob holati: «OPTIMAL», «ENG YAXSHI TOPILGAN (FEASIBLE)» yoki «BOSHLANG‘ICH REJA SAQLANDI».

### 7.3. «Favqulodda holat»
- Hodisani tanlash:
  - peregon yopilishi (qaysi peregon, qachondan, necha daqiqa);
  - poyezd buzilishi (bekatda N daqiqa turib qoladi).
- «Qayta rejalashtirish» tugmasi.
- FIFO tupikka tushsa, qizil banner: **«TUPIK: poyezdlar bir-birini to‘sib qo‘ydi»**, poyezdlar va bekatlar ro‘yxati bilan (engine `deadlock_info` qaytaradi).
- «Tiklanish vaqti» ko‘rsatkichi.

### 7.4. «Yangi razyezd qayerda?» — investitsiya simulyatori
- Har bir oraliq bekatga +1 yo‘l qo‘shiladi va AI qayta hisoblaydi (`investment_ranking`).
- **Ilmiy protokol** (shusiz natija ishonchsiz):
  1. Nazorat guruhi: xuddi shu vaqt va seed’lar bilan, yangi yo‘lsiz qayta hisob.
  2. Har bir variant 3 seed bilan hisoblanadi, eng yaxshisi olinadi.
  3. Shovqin chegarasidan kichik tejash **«sezilarli emas»** deb kulrang rangda ko‘rsatiladi.
- Natija: bekatlar bo‘yicha ustunli reyting. Hisob o‘nlab daqiqa davom etadi, shuning uchun **faqat oldindan hisoblangan kesh** ko‘rsatiladi.
- «Bitta razyezd narxi, $» kiritish maydoni. Raqam qattiq kodlanmaydi, foydalanuvchi manbadan kiritadi.
- Asosiy xabar: **«Joy muhim: noto‘g‘ri bekatga qurilgan yo‘l deyarli foyda bermaydi».**

### 7.5. «Iqtisodiy samara»
- Kiritish maydonlari (standart holatda bo‘sh, «manbadan kiriting» degan izoh bilan):
  - yuk poyezdining 1 soatlik turib qolish narxi;
  - kunlik poyezdlar soni;
  - yildagi kunlar.
- Formula ekranda ko‘rinadi: tejalgan soatlar × narx = yiliga $.
- Shu uchastkada ikkinchi yo‘l narxi bilan taqqoslash (narx kiritiladi).

### 7.6. (Ixtiyoriy) «Dispetcher o‘yini»
- Foydalanuvchi har bir konfliktda qaysi poyezd kutishini o‘zi tanlaydi, keyin natijasi AI bilan taqqoslanadi.
- Sahnada hakamni «AIga qarshi o‘ynashga» taklif qilish mumkin.

---

## 8. Texnik stek

- **Hisob yadrosi:** Python 3.11+, `ortools` (CP-SAT), `pydantic`.
- **API:** FastAPI.
  - `/scenarios`
  - `/solve`
  - `/simulate_fifo`
  - `/verify`
  - `/investment` (faqat keshdan)
- **Frontend:** React + Vite + TypeScript. Grafiklar uchun Plotly.js yoki D3, liniya animatsiyasi uchun SVG.
- **Kesh:** `data/cache/` papkasidagi JSON fayllar (`to_json` funksiyasi orqali). Barcha tayyor ssenariylar 120 soniyalik hisob bilan oldindan saqlanadi.
- **Bitta buyruq bilan ishga tushirish:** `./run.sh` backend va frontendni lokal ishga tushiradi, **internetsiz**.
- **Testlar:** `pytest`.
  - Har bir yechimda validator 0 xato beradi.
  - AI natijasi hech qachon FIFO dan yomon emas.
  - Tupik to‘g‘ri aniqlanadi.
- **Zaxira yo‘l:** React ulgurilmasa, o‘sha engine + Streamlit + Plotly.

---

## 9. Model va algoritmlar (`vdt_engine.py` asosida)

### Ma’lumotlar modeli
- `Station(name, km, tracks)` — tracks: asosiy yo‘l bilan birga yo‘llar soni. Chekka bekatlar cheklanmagan.
- `Train(id, kind, direction, speed, release, weight, stops)` — ID prefikslari: `YK` yuk, `YL` yo‘lovchi, `TZ` tezyurar.
- Vaqt butun daqiqalarda. Peregondagi yurish vaqti = ⌈uzunlik / tezlik × 60⌉.

### Xavfsizlik qoidalari (qat’iy cheklovlar)
1. Ikki bekat orasidagi peregonda bir vaqtda **faqat 1 ta poyezd** (konservativ model).
2. Peregon bo‘shagach, keyingi poyezd kamida **3 daqiqa** (headway) o‘tgandan keyin kiradi.
3. Bekatda bir vaqtda `tracks` dan ko‘p poyezd turmaydi.
4. Poyezd jo‘nash vaqtidan oldin ketmaydi va to‘xtash bekatida minimal vaqtdan kam turmaydi.
5. Tezlik peregonda belgilangan. AI **faqat bekatlardan jo‘nash vaqtini** o‘zgartiradi, ya’ni kim kimni kutishini va qayerda uchrashishini.
6. Avariyada peregon [start, end) oralig‘ida yopiq.

### Bazaviy dispetcher (FIFO)
- Daqiqama-daqiqa simulyatsiya. Tayyor poyezd keyingi peregonni egallaydi, agar:
  - peregon bo‘sh (+headway);
  - peregon yopilmagan;
  - keyingi bekatda bo‘sh yo‘l bor.
- Navbat tayyorlik vaqti bo‘yicha, teng bo‘lsa yuqori ustuvorlik birinchi.
- Bu ilmiy adabiyotdagi standart FCFS benchmarki. Sahnada «oddiy dispetcherlik qoidasi» deb ayting, «hozirgi dispetcherlar» demang.

### AI optimallashtiruvchi (CP-SAT)
- O‘zgaruvchilar: har bir poyezdning har bir bekatga kelish va ketish vaqti.
- Peregonlar: `NoOverlap` (yurish + headway). Bekatlar: `Cumulative` (sig‘im = yo‘llar soni).
- Maqsad:
  - «umumiy» — kechikishlar yig‘indisi;
  - «ustuvorlik» — vazn × kechikish (tezyurar 5, yo‘lovchi 3, yuk 1).
- **Issiq start:** FIFO rejasi boshlang‘ich yechim sifatida beriladi (`AddHint`). AI yomonroq natija bersa, FIFO rejasi saqlanadi. Natijada AI ≤ FIFO, kafolatlangan.
- Hisob statusini doim ko‘rsating: OPTIMAL yoki FEASIBLE (ajratilgan vaqt ichida topilgan eng yaxshi).
- Ko‘p oqimli (multi-thread) hisob har safar biroz boshqacha natija berishi mumkin. Shuning uchun sahnada **faqat kesh**.

### Mustaqil validator (majburiy)
- `verify()` har qanday jadvalni (FIFO ham, AI ham) tekshiradi:
  - yurish vaqti;
  - peregon to‘qnashuvlari (+headway);
  - yopiq peregon;
  - bekat sig‘imi.
- Natija ekranda nishon sifatida ko‘rinadi. Bu hakamlar uchun asosiy ishonch dalili.

### Ko‘rsatkichlar
- Kechikish = haqiqiy yetib kelish − to‘siqsiz yetib kelish.
- Umumiy, o‘rtacha va turlar bo‘yicha kechikish.
- Kutish to‘xtashlari.
- Oxirgi yetib kelish.
- Avariyadan keyin tiklanish vaqti.

---

## 10. Biznes-model

| Bosqich | Mahsulot | Kim to‘laydi | Qanday |
|---|---|---|---|
| 1. Hozir – 12 oy | **Capacity Study** — aniq uchastka bo‘yicha hisob-tadqiqot | «O‘zbekiston temir yo‘llari» va uning tarkibiy korxonalari, ADB/AIIB/Jahon banki loyihalari konsultantlari (texnik-iqtisodiy asoslash) | Tadqiqot uchun to‘lov |
| 2. 1–3 yil | **Planning SaaS** — grafik rejalashtiruvchilar uchun | Markaziy Osiyo temir yo‘llari, yirik operatorlar va terminallar | Yillik obuna |
| 3. 3+ yil | **Dispetcher maslahatchisi** (real vaqtda) | O‘shalar | Pilot va sertifikatlashdan keyin |

- **Raqobatchilar:** harakatni boshqarish tizimlarining yirik yetkazib beruvchilari (Siemens, Hitachi Rail, Wabtec va boshqalar).
- **Bizning farqimiz:**
  - bir yo‘lli liniyalar va investitsiya qarorlariga fokus;
  - mahalliy moslashuv va til;
  - narx;
  - mavjud tizimlarni almashtirmasdan tez joriy etish.

---

## 11. Claude Code uchun bosqichlar (qat’iy tartibda)

**1-bosqich. Yadro va API.**
- `vdt_engine.py` ni `engine/` paketiga ajratish: model, FIFO, CP-SAT, validator, ko‘rsatkichlar, ssenariylar, investitsiya.
- FastAPI endpointlari.
- Pytest:
  - 5 ta seed’da validator 0 xato;
  - AI ≤ FIFO;
  - seed 4 «Avariya» ssenariysida FIFO tupikni aniqlaydi.
- ✅ Tayyorlik mezoni: `pytest` yashil, `/solve` 15 soniyadan tez javob beradi.

**2-bosqich. Kesh generatori.**
- `scripts/precompute.py`: barcha tayyor ssenariylarni 120 soniyalik hisob bilan JSON keshga saqlaydi.
- Investitsiya reytingini protokol bo‘yicha hisoblaydi (uzoq ishlaydi, kechasi qoldiring).

**3-bosqich. Asosiy ekran (statik).**
- Ikkita harakat grafigi + ko‘rsatkichlar paneli + validator nishoni (keshdan).
- ✅ Tayyorlik mezoni: bitta ekranda «FIFO vs AI» va −X% raqami.

**4-bosqich. Animatsiya.**
- Grafiklardagi vaqt kursori bilan sinxron harakatlanuvchi poyezdlar; play, pauza, tezlik.
- ✅ Tayyorlik mezoni: noutbukda silliq (60 fps).

**5-bosqich. Favqulodda holat.**
- Hodisa formasi, qayta hisob, TUPIK banneri, tiklanish vaqti.

**6-bosqich. Investitsiya simulyatori.**
- Keshdagi reyting, «sezilarli emas» belgisi, narx kiritish.

**7-bosqich. Iqtisodiy samara va i18n** (uz / ru / en).

**8-bosqich. Sahnaga tayyorgarlik.**
- `run.sh`, internetsiz rejim, katta shriftli «Demo» rejimi, mualliflar ko‘rsatilgan bosh ekran.
- Videoni yozish (OBS).

**9-bosqich (ixtiyoriy).** Dispetcher o‘yini.

---

## 12. Halollik qoidalari: sahnada nima deyiladi

**Deyish mumkin:**
- ✅ «Modelda», «sintetik uchastkadagi testimizda».
- ✅ «Optimallashtirish (constraint programming) — sun’iy intellektning klassik yo‘nalishlaridan biri (planning & scheduling)».
- ✅ «RL — katta tarmoqlar uchun keyingi tadqiqot bosqichi».
- ✅ «Qarorni inson qabul qiladi, biz hisobni beramiz».
- ✅ «AI dispetcher rejasidan boshlaydi va faqat yaxshilaydi».

**Deyish mumkin emas:**
- ❌ «O‘zbekiston o‘tkazuvchanligini 30–40% oshiramiz».
- ❌ «Neyrotarmog‘imiz poyezdlarni boshqaradi».
- ❌ Manbasiz har qanday narx yoki raqam.

---

## 13. Pitch tuzilmasi (5–7 daqiqa)

1. **Muammo** (30 s): bir yo‘lli tarmoq, poyezdlar kutadi, ikkinchi yo‘l qimmat.
2. **Jonli demo** (3 daq): 6-bo‘lim bo‘yicha.
3. **Qanday ishlaydi** (30 s): xavfsizlik cheklovlari, CP-SAT, issiq start, validator; Fresko va Kroon tamoyillari.
4. **Validatsiya** (30 s): intervyulardan iqtiboslar (dispetcher, logist, o‘qituvchi).
5. **Biznes** (40 s): kim to‘laydi, bosqichlar.
6. **Jamoa va so‘rov** (30 s): Saynatov Yodgor, Raxmatullayev Sarvar; mukofot nimaga sarflanadi (ma’lumotlar + bitta uchastkada pilot).

---

## 14. Hakamlar savollari: tayyor javoblar

1. **Real ma’lumotni qayerdan olasiz?**
   Hozir ochiq ma’lumot va sintetik model. Keyingi qadam — «O‘zbekiston temir yo‘llari» bo‘limi yoki transport OTM kafedrasi bilan bitta uchastkada pilot.
2. **Xavfsizlik-chi?**
   Bu offline rejalashtirish vositasi. Model konservativ: peregonda bitta poyezd + 3 daqiqa oraliq. Har bir jadvalni mustaqil validator tekshiradi.
3. **AI xato qilsa-chi?**
   AI dispetcher rejasidan boshlaydi va faqat yaxshilaydi, natija hech qachon bazadan yomon bo‘lmaydi. Qarorni inson tasdiqlaydi.
4. **Siemens va boshqalardan farqingiz?**
   Bir yo‘lli liniyalar va investitsiya qaroriga fokus, narx, mahalliylashtirish, tizimlarni almashtirmasdan joriy etish.
5. **Nega FIFO bilan taqqoslaysiz?**
   Bu ilmiy adabiyotdagi standart benchmark. Keyingi qadam — real jadval bilan taqqoslash.
6. **Natija nega 10%, 30% emas?**
   Biz halol o‘lchadik: 30 ta ssenariy, xavfsizlik oralig‘i bilan. Ustuvor poyezdlar uchun o‘rtacha −28%. Uzoqroq hisobda natija yaxshilanadi (bir ssenariyda 8 s da −11%, 60 s da −23%). Yuklangan uchastkada hatto bir necha foiz ham ikkinchi yo‘l qurishdan arzon.
7. **Masshtablanadimi?**
   CP-SAT o‘nlab poyezdli uchastkani soniyalarda hal qiladi. Butun tarmoq uchun uchastkalarga bo‘lish (dekompozitsiya) va RL (Yang va boshq.).
8. **AI qayerda?**
   Cheklovli matematik optimallashtirish — AI’ning klassik yo‘nalishi.
9. **Nega aynan siz?**
   Dala tadqiqotlari va ma’lumotlar tahlili tajribasi + jamoadagi texnik a’zo. Jamoaga dasturchi yoki temir yo‘lchi talabani qo‘shing.
10. **Mukofotni nimaga sarflaysiz?**
    Ma’lumot yig‘ish, bitta uchastkada pilot, temir yo‘l bo‘yicha konsultant.

---

## 15. Claude Code uchun birinchi prompt (to‘liq nusxalang)

```
Bu papkadagi VDT_LOYIHA_TZ.md va vdt_engine.py fayllarini o‘qi.
Bu universitet startap tanlovi uchun "Virtual Double-Track" demo-ilovasining
texnik topshirig‘i. Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar.
11-bo‘lim bo‘yicha qat’iy ishla, 1-bosqichdan boshla. Har bir bosqichdan keyin:
testlarni ishga tushir, natijani menga ko‘rsat va tekshirish uchun to‘xta.
Majburiy: har bir jadvalda mustaqil validator, AI natijasi FIFO dan yomon emas,
internetsiz ishlash, oldindan hisoblangan kesh, interfeys o‘zbek tilida (lotin)
RU/EN almashtirgich bilan. Real narx raqamlarini o‘ylab topma — faqat kiritish maydonlari.
```

---

## 16. O‘zingiz yig‘ishingiz kerak bo‘lganlar (koddan tashqari)

- [ ] Tanlov qoidalari, baholash mezonlari, pitch vaqti.
- [ ] 5–10 ta intervyu: dispetcher, logist yoki ekspeditor, transport OTM o‘qituvchisi.
- [ ] 1 km ikkinchi yo‘l yoki bitta razyezd narxi: ADB, Jahon banki yoki AIIB hujjatlaridan, havola bilan.
- [ ] Yuk poyezdining 1 soat turib qolish narxi (manba bilan).
- [ ] Bir yo‘lli liniyalarning dolzarb ulushi (UTY sayti yoki davlat statistikasi).
- [ ] Jamoaga texnik a’zo.

---

## Manbalar

1. «O‘zbekiston temir yo‘llari», CAREC taqdimoti (tarmoq uzunligi, bir/ikki yo‘lli): https://www.carecprogram.org/uploads/03-Presentation-by-Uzbekistan-Railways.pdf
2. World Bank (2026). *Integration: World-Class Trade Logistics Along the Trans-Caspian Transport Corridor*: https://www.worldbank.org/en/region/eca/publication/world-class-trade-logistics-along-trans-caspian-transport-corridor
3. World Bank press-relizi, 2026-yil 28-sentabr: https://www.worldbank.org/en/news/press-release/2026/09/28/trans-caspian-transport-corridor-investments-spur-growth-and-create-millions-jobs
4. Kun.uz (2025-yil 28-may), Chuqursoy: https://kun.uz/en/news/2025/05/28/president-mirziyoyev-reviews-plans-to-modernize-railway-system
5. AIIB, Buxoro–Miskin–Urganch–Xiva loyihasi: https://www.aiib.org/en/projects/details/2022/_download/uzbekistan/AIIB-PD000341-Uzbekistan-Bukhara-Miskin-Urgench-Khiva-Railway-Electrification-Project-SBF.-APD.pdf
6. Gazeta.uz (2025-yil 13-noyabr): https://www.gazeta.uz/ru/2025/11/13/railway-modernization/
7. Yang F., Yang Y., Ni S., Liu S., Xu C., Chen D., Zhang Q. (2023). Single-track railway scheduling with a novel gridworld model and scalable deep reinforcement learning. *Transportation Research Part C*, 154, 104237. https://doi.org/10.1016/j.trc.2023.104237
8. Yang F., Liu J., Li J., Liu L., Wang S., Li W., Ni S. (2025). Causal reinforcement learning for train scheduling on single-track railway networks. *Transportation Research Part C*, 178, 105215. https://doi.org/10.1016/j.trc.2025.105215
9. D’Ariano A., Pacciarelli D., Pranzo M. (2007). A branch and bound algorithm for scheduling trains in a railway network. *European Journal of Operational Research*, 183(2), 643–657. https://ideas.repec.org/a/eee/ejores/v183y2007i2p643-657.html
10. INFORMS, Franz Edelman Award 2008 — Netherlands Railways (Kroon va boshq.): https://www.informs.org/Recognizing-Excellence/INFORMS-Prizes/Franz-Edelman-Award/Franz-Edelman-Laureates2/Franz-Edelman-Laureates-Class-of-2008
11. Jacque Fresco — Wikipedia: https://en.wikipedia.org/wiki/Jacque_Fresco
12. Eisenmann T., «False Starts» (Stanford eCorner): https://stvp.stanford.edu/clips/false-starts
13. Google OR-Tools (CP-SAT): https://developers.google.com/optimization
