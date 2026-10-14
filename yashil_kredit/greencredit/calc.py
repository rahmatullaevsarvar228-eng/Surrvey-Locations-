"""Yashil loyiha uchun hisob-kitoblar: tejash, o'zini oqlash (ROI), CO2 va Green Score.

Barcha funksiyalar sof (GUI va ma'lumotlar bazasiga bog'liq emas), shuning uchun
ularni alohida test qilish oson.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

OYLAR = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]


@dataclass
class Sozlamalar:
    """Hisob-kitob farazlari. Foydalanuvchi ularni dasturda o'zgartira oladi."""

    quyosh_unumdorligi: float = 1500.0      # kVt·soat / kVt quvvat / yil
    panel_degradatsiyasi: float = 0.5       # % / yil
    tarif_osishi: float = 5.0               # energiya tarifining yillik o'sishi, %
    elektr_co2: float = 0.5                 # kg CO2 / kVt·soat (elektr tarmog'i)
    gaz_co2: float = 1.9                    # kg CO2 / m³ tabiiy gaz
    tahlil_muddati: int = 10                # yil
    oddiy_foiz: float = 22.0                # oddiy kredit, % yillik
    yashil_foiz: float = 12.0               # yashil kredit, % yillik
    kredit_muddati: int = 5                 # yil
    kredit_ulushi: float = 100.0            # investitsiyaning kredit hisobidan qismi, %

    @classmethod
    def from_dict(cls, data: dict) -> "Sozlamalar":
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Kiritma:
    """1-tugma: korxona, o'tgan yilgi hisoblar va rejalashtirilgan loyiha."""

    korxona: str = ""
    faoliyat: str = ""
    hudud: str = ""
    elektr_oylik: list[float] = field(default_factory=lambda: [0.0] * 12)  # kVt·soat
    gaz_oylik: list[float] = field(default_factory=lambda: [0.0] * 12)     # m³
    elektr_tarif: float = 0.0       # so'm / kVt·soat
    gaz_tarif: float = 0.0          # so'm / m³
    loyiha_nomi: str = "Quyosh panellari"
    investitsiya: float = 0.0       # so'm
    quyosh_quvvati: float = 0.0     # kVt
    elektr_tejash_foiz: float = 0.0  # qolgan elektr iste'molidan qo'shimcha tejash, %
    gaz_tejash_foiz: float = 0.0     # gaz iste'molidan tejash, %

    @property
    def yillik_elektr(self) -> float:
        return sum(self.elektr_oylik)

    @property
    def yillik_gaz(self) -> float:
        return sum(self.gaz_oylik)

    @classmethod
    def from_dict(cls, data: dict) -> "Kiritma":
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


class KiritmaXatosi(ValueError):
    """Kiritilgan ma'lumotlar hisob-kitob uchun yetarli emas."""


def tekshir(k: Kiritma) -> list[str]:
    """Xatolar ro'yxatini qaytaradi (bo'sh ro'yxat = hammasi joyida)."""
    xatolar = []
    if not k.korxona.strip():
        xatolar.append("Korxona nomini kiriting.")
    if len(k.elektr_oylik) != 12 or len(k.gaz_oylik) != 12:
        xatolar.append("12 oylik hisoblar to'liq emas.")
    if any(v < 0 for v in k.elektr_oylik + k.gaz_oylik):
        xatolar.append("Oylik iste'mol manfiy bo'lishi mumkin emas.")
    if k.yillik_elektr <= 0 and k.yillik_gaz <= 0:
        xatolar.append("Kamida elektr yoki gaz iste'molini kiriting.")
    if k.yillik_elektr > 0 and k.elektr_tarif <= 0:
        xatolar.append("Elektr tarifini kiriting (so'm / kVt·soat).")
    if k.yillik_gaz > 0 and k.gaz_tarif <= 0:
        xatolar.append("Gaz tarifini kiriting (so'm / m³).")
    if k.investitsiya <= 0:
        xatolar.append("Loyiha narxini (investitsiya) kiriting.")
    if k.quyosh_quvvati < 0:
        xatolar.append("Quyosh panellari quvvati manfiy bo'lishi mumkin emas.")
    for nom, v in (("Elektr tejash", k.elektr_tejash_foiz), ("Gaz tejash", k.gaz_tejash_foiz)):
        if not 0 <= v <= 100:
            xatolar.append(f"{nom} foizi 0 dan 100 gacha bo'lishi kerak.")
    if k.quyosh_quvvati == 0 and k.elektr_tejash_foiz == 0 and k.gaz_tejash_foiz == 0:
        xatolar.append("Loyiha hech narsani tejamaydi: quyosh quvvati yoki tejash foizini kiriting.")
    return xatolar


@dataclass
class YillikQator:
    yil: int
    tejash: float          # shu yilgi tejash, so'm
    jami_tejash: float     # boshidan beri jami, so'm
    sof_foyda: float       # jami tejash - investitsiya, so'm
    co2_t: float           # shu yilgi CO2 kamayishi, tonna


@dataclass
class KreditTaqqoslash:
    summa: float
    muddat_yil: int
    oddiy_foiz: float
    yashil_foiz: float
    oddiy_oylik: float
    yashil_oylik: float
    oddiy_foiz_jami: float
    yashil_foiz_jami: float

    @property
    def yutuq(self) -> float:
        return self.oddiy_foiz_jami - self.yashil_foiz_jami


@dataclass
class GreenScore:
    ball: int
    daraja: str
    xulosa: str
    co2_ball: float
    oqlash_ball: float
    tejash_ball: float


@dataclass
class Natija:
    investitsiya: float
    quyosh_ishlab_chiqarish: float     # kVt·soat, 1-yil
    elektr_tejash: float               # kVt·soat, 1-yil
    gaz_tejash: float                  # m³, 1-yil
    yillik_tejash: float               # so'm, 1-yil
    bazaviy_xarajat: float             # so'm/yil, loyihasiz
    oddiy_oqlash: float | None         # yil (investitsiya / 1-yil tejash)
    oqlash_muddati: float | None       # yil, tarif o'sishi va degradatsiya hisobga olingan
    jami_tejash: float                 # so'm, tahlil muddati davomida
    sof_foyda: float                   # so'm
    roi_foiz: float
    co2_yillik_t: float
    co2_jami_t: float
    bazaviy_co2_t: float
    co2_ulush_foiz: float
    tejash_ulush_foiz: float
    yillar: list[YillikQator]
    kredit: KreditTaqqoslash
    score: GreenScore
    tahlil_muddati: int


def annuitet_oylik(summa: float, yillik_foiz: float, muddat_yil: int) -> float:
    """Annuitet (teng) oylik to'lov."""
    n = int(round(muddat_yil * 12))
    if summa <= 0 or n <= 0:
        return 0.0
    r = yillik_foiz / 100 / 12
    if r == 0:
        return summa / n
    return summa * r / (1 - (1 + r) ** -n)


def kredit_taqqosla(summa: float, s: Sozlamalar) -> KreditTaqqoslash:
    n = int(round(s.kredit_muddati * 12))
    oddiy = annuitet_oylik(summa, s.oddiy_foiz, s.kredit_muddati)
    yashil = annuitet_oylik(summa, s.yashil_foiz, s.kredit_muddati)
    return KreditTaqqoslash(
        summa=summa,
        muddat_yil=s.kredit_muddati,
        oddiy_foiz=s.oddiy_foiz,
        yashil_foiz=s.yashil_foiz,
        oddiy_oylik=oddiy,
        yashil_oylik=yashil,
        oddiy_foiz_jami=max(oddiy * n - summa, 0.0),
        yashil_foiz_jami=max(yashil * n - summa, 0.0),
    )


def _chiziqli(qiymat: float, nol: float, toliq: float) -> float:
    """qiymat `nol` da 0, `toliq` da 1 bo'ladigan chiziqli shkala (0..1 oralig'ida)."""
    if toliq == nol:
        return 1.0 if qiymat >= toliq else 0.0
    t = (qiymat - nol) / (toliq - nol)
    return max(0.0, min(1.0, t))


def green_score(co2_ulush: float, oqlash: float | None, tejash_ulush: float) -> GreenScore:
    """Dastur ichki metodikasi bo'yicha 0–100 ball.

    * CO2 kamayishi (40 ball): bazaviy chiqindining 50% va undan ko'pi — to'liq ball.
    * O'zini oqlash muddati (30 ball): 3 yil va kam — to'liq, 10 yil va ko'p — 0.
    * Energiya xarajatini tejash (30 ball): bazaviy xarajatning 50% va undan ko'pi — to'liq.
    """
    co2_b = 40 * _chiziqli(co2_ulush, 0, 50)
    oqlash_b = 0.0 if oqlash is None else 30 * _chiziqli(oqlash, 10, 3)
    tejash_b = 30 * _chiziqli(tejash_ulush, 0, 50)
    ball = int(round(co2_b + oqlash_b + tejash_b))
    if ball >= 80:
        daraja, xulosa = "A", "Yashil kreditga to'liq mos"
    elif ball >= 65:
        daraja, xulosa = "B", "Yashil kreditga mos"
    elif ball >= 50:
        daraja, xulosa = "C", "Qo'shimcha tekshiruv tavsiya etiladi"
    else:
        daraja, xulosa = "D", "Yashil kredit uchun samaradorlik past"
    return GreenScore(ball, daraja, xulosa, co2_b, oqlash_b, tejash_b)


def hisobla(k: Kiritma, s: Sozlamalar | None = None) -> Natija:
    """2-tugma: loyiha natijalarini hisoblaydi."""
    s = s or Sozlamalar()
    xatolar = tekshir(k)
    if xatolar:
        raise KiritmaXatosi("\n".join(xatolar))

    E, G = k.yillik_elektr, k.yillik_gaz
    quyosh = k.quyosh_quvvati * s.quyosh_unumdorligi
    # Faqat o'z iste'molini qoplagan qismi hisobga olinadi (ortiqcha ishlab chiqarish — 0).
    quyosh_foydali = min(E, quyosh)
    qolgan = E - quyosh_foydali
    qoshimcha_elektr = qolgan * k.elektr_tejash_foiz / 100
    gaz_tejash = G * k.gaz_tejash_foiz / 100

    bazaviy_xarajat = E * k.elektr_tarif + G * k.gaz_tarif
    bazaviy_co2 = (E * s.elektr_co2 + G * s.gaz_co2) / 1000

    yillar: list[YillikQator] = []
    jami = 0.0
    co2_jami = 0.0
    oqlash = None
    for t in range(1, s.tahlil_muddati + 1):
        deg = (1 - s.panel_degradatsiyasi / 100) ** (t - 1)
        osish = (1 + s.tarif_osishi / 100) ** (t - 1)
        elektr_t = quyosh_foydali * deg + qoshimcha_elektr
        tejash_t = (elektr_t * k.elektr_tarif + gaz_tejash * k.gaz_tarif) * osish
        co2_t = (elektr_t * s.elektr_co2 + gaz_tejash * s.gaz_co2) / 1000
        oldingi = jami
        jami += tejash_t
        co2_jami += co2_t
        if oqlash is None and jami >= k.investitsiya and tejash_t > 0:
            oqlash = (t - 1) + (k.investitsiya - oldingi) / tejash_t
        yillar.append(YillikQator(t, tejash_t, jami, jami - k.investitsiya, co2_t))

    birinchi = yillar[0]
    elektr_1 = quyosh_foydali + qoshimcha_elektr
    tejash_ulush = 100 * birinchi.tejash / bazaviy_xarajat if bazaviy_xarajat else 0.0
    co2_ulush = 100 * birinchi.co2_t / bazaviy_co2 if bazaviy_co2 else 0.0
    kredit_summa = k.investitsiya * s.kredit_ulushi / 100

    return Natija(
        investitsiya=k.investitsiya,
        quyosh_ishlab_chiqarish=quyosh,
        elektr_tejash=elektr_1,
        gaz_tejash=gaz_tejash,
        yillik_tejash=birinchi.tejash,
        bazaviy_xarajat=bazaviy_xarajat,
        oddiy_oqlash=k.investitsiya / birinchi.tejash if birinchi.tejash > 0 else None,
        oqlash_muddati=oqlash,
        jami_tejash=jami,
        sof_foyda=jami - k.investitsiya,
        roi_foiz=100 * (jami - k.investitsiya) / k.investitsiya,
        co2_yillik_t=birinchi.co2_t,
        co2_jami_t=co2_jami,
        bazaviy_co2_t=bazaviy_co2,
        co2_ulush_foiz=co2_ulush,
        tejash_ulush_foiz=tejash_ulush,
        yillar=yillar,
        kredit=kredit_taqqosla(kredit_summa, s),
        score=green_score(co2_ulush, oqlash, tejash_ulush),
        tahlil_muddati=s.tahlil_muddati,
    )


def namuna_kiritma() -> Kiritma:
    """Taqdimot uchun namuna (raqamlar o'ylab topilgan, haqiqiy korxona emas)."""
    elektr = [7200, 6800, 6500, 5900, 5600, 6200, 7400, 7600, 6300, 5800, 6100, 6900]
    gaz = [5200, 4800, 3600, 2100, 900, 400, 300, 300, 800, 2400, 3900, 5000]
    return Kiritma(
        korxona="Namuna MChJ",
        faoliyat="Non va qandolat mahsulotlari",
        hudud="Samarqand viloyati",
        elektr_oylik=[float(v) for v in elektr],
        gaz_oylik=[float(v) for v in gaz],
        elektr_tarif=900.0,
        gaz_tarif=1500.0,
        loyiha_nomi="Quyosh panellari + issiqlik izolyatsiyasi",
        investitsiya=150_000_000.0,
        quyosh_quvvati=30.0,
        elektr_tejash_foiz=0.0,
        gaz_tejash_foiz=20.0,
    )


# --- Formatlash yordamchilari (GUI va PDF uchun umumiy) ---

def pul(x: float) -> str:
    """150000000 -> '150 000 000'."""
    return f"{x:,.0f}".replace(",", " ")


def mln(x: float) -> str:
    """150000000 -> '150 mln'; 1 500 000 000 -> '1,5 mlrd'."""
    if abs(x) >= 1e9:
        return f"{x / 1e9:.1f} mlrd".replace(".", ",")
    if abs(x) >= 1e6:
        v = x / 1e6
        return (f"{v:.0f}" if abs(v) >= 100 else f"{v:.1f}".replace(".", ",")) + " mln"
    return pul(x)


def son(x: float, kasr: int = 1) -> str:
    return f"{x:,.{kasr}f}".replace(",", " ").replace(".", ",")


def yil_matn(y: float | None, muddat: int) -> str:
    if y is None:
        return f"{muddat} yildan ko'p"
    return f"{son(y, 1)} yil"


def raqam_oqi(matn: str) -> float:
    """'150 000 000', '1 234,5', '1234.5' kabi matnni songa aylantiradi."""
    t = (matn or "").strip().replace(" ", "").replace(" ", "")
    if not t:
        return 0.0
    if "," in t and "." in t:
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")
    return float(t)
