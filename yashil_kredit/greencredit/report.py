"""3-tugma: bank uchun "Yashil pasport" PDF hisobotini yaratish."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .calc import OYLAR, Kiritma, Natija, Sozlamalar, mln, pul, son, yil_matn

YASHIL = colors.HexColor("#1E7A3C")
YASHIL_OCH = colors.HexColor("#EDF4EA")
CHEGARA = colors.HexColor("#CFE3D4")
QORA = colors.HexColor("#15301F")
KULRANG = colors.HexColor("#5B6B60")
DARAJA_RANG = {
    "A": colors.HexColor("#1E7A3C"),
    "B": colors.HexColor("#4E9A3A"),
    "C": colors.HexColor("#C98A0B"),
    "D": colors.HexColor("#B45309"),
}

_matn = ParagraphStyle("matn", fontName="Helvetica", fontSize=9.5, leading=13, textColor=QORA)
_kichik = ParagraphStyle("kichik", parent=_matn, fontSize=8, leading=11, textColor=KULRANG)
_bolim = ParagraphStyle("bolim", parent=_matn, fontName="Helvetica-Bold", fontSize=12.5,
                        leading=16, textColor=YASHIL, spaceBefore=10, spaceAfter=6)
_metrik_nom = ParagraphStyle("mn", parent=_matn, fontSize=8.5, leading=11, textColor=KULRANG,
                             alignment=TA_CENTER)
_metrik_qiymat = ParagraphStyle("mq", parent=_matn, fontName="Helvetica-Bold", fontSize=17,
                                leading=21, alignment=TA_CENTER)
_xulosa = ParagraphStyle("xulosa", parent=_matn, fontName="Helvetica-Bold", fontSize=13,
                         leading=17)


def _jadval_uslubi(sarlavha: bool = True) -> TableStyle:
    buyruqlar = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), QORA),
        ("GRID", (0, 0), (-1, -1), 0.5, CHEGARA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if sarlavha:
        buyruqlar += [
            ("BACKGROUND", (0, 0), (-1, 0), YASHIL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    return TableStyle(buyruqlar)


def _score_doirasi(daraja: str, ball: int) -> Drawing:
    d = Drawing(36 * mm, 36 * mm)
    r = 17 * mm
    d.add(Circle(18 * mm, 18 * mm, r, fillColor=DARAJA_RANG.get(daraja, YASHIL), strokeColor=None))
    d.add(String(18 * mm, 17 * mm, daraja, fontName="Helvetica-Bold", fontSize=40,
                 fillColor=colors.white, textAnchor="middle"))
    d.add(String(18 * mm, 9 * mm, f"{ball} / 100", fontName="Helvetica-Bold", fontSize=10,
                 fillColor=colors.white, textAnchor="middle"))
    return d


def _sarlavha_va_pastki(hujjat_no: str, sana: str):
    def chiz(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(YASHIL)
        canvas.rect(0, h - 30 * mm, w, 30 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 22)
        canvas.drawString(18 * mm, h - 16 * mm, "YASHIL PASPORT")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(18 * mm, h - 23 * mm, "Green Credit Passport - yashil kredit uchun loyiha hisoboti")
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(w - 18 * mm, h - 16 * mm, f"Hujjat: {hujjat_no}")
        canvas.drawRightString(w - 18 * mm, h - 23 * mm, f"Sana: {sana}")
        canvas.setFillColor(KULRANG)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 10 * mm,
                          "GreenCredit lokal dasturida tayyorlandi. Ma'lumotlar internetga yuborilmagan.")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"{doc.page}-bet")
        canvas.restoreState()
    return chiz


def pasport_yarat(yol: str | Path, k: Kiritma, n: Natija, s: Sozlamalar,
                  hujjat_id: int | None = None) -> Path:
    yol = Path(yol)
    sana = datetime.now().strftime("%d.%m.%Y")
    hujjat_no = f"GC-{datetime.now():%Y%m%d}-{hujjat_id or 0:04d}"
    eni = A4[0] - 36 * mm

    doc = SimpleDocTemplate(
        str(yol), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=38 * mm, bottomMargin=18 * mm,
        title=f"Yashil pasport - {k.korxona}", author=k.korxona, subject="Yashil kredit",
    )
    el: list = []

    # 1. Korxona va loyiha
    el.append(Paragraph("1. Korxona va loyiha", _bolim))
    malumot = [
        ["Korxona", k.korxona or "-"],
        ["Faoliyat turi", k.faoliyat or "-"],
        ["Hudud", k.hudud or "-"],
        ["Loyiha", k.loyiha_nomi or "-"],
        ["Investitsiya", f"{pul(k.investitsiya)} so'm"],
        ["Quyosh panellari quvvati", f"{son(k.quyosh_quvvati, 1)} kVt" if k.quyosh_quvvati else "-"],
        ["Qo'shimcha elektr tejash", f"{son(k.elektr_tejash_foiz, 0)}%" if k.elektr_tejash_foiz else "-"],
        ["Gaz tejash", f"{son(k.gaz_tejash_foiz, 0)}%" if k.gaz_tejash_foiz else "-"],
    ]
    t = Table(malumot, colWidths=[eni * 0.38, eni * 0.62])
    st = _jadval_uslubi(sarlavha=False)
    st.add("BACKGROUND", (0, 0), (0, -1), YASHIL_OCH)
    st.add("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold")
    t.setStyle(st)
    el.append(t)

    # 2. Asosiy ko'rsatkichlar + Green Score
    el.append(Paragraph("2. Asosiy ko'rsatkichlar", _bolim))
    metrikalar = [
        ("Investitsiya", f"{mln(n.investitsiya)} so'm"),
        ("O'zini oqlash", yil_matn(n.oqlash_muddati, n.tahlil_muddati)),
        (f"{n.tahlil_muddati} yilda tejash", f"{mln(n.jami_tejash)} so'm"),
        (f"CO<sub>2</sub> kamayishi ({n.tahlil_muddati} yil)", f"{son(n.co2_jami_t, 1)} t"),
    ]
    qator = [[Paragraph(nom, _metrik_nom), Paragraph(q, _metrik_qiymat)] for nom, q in metrikalar]
    mt = Table([[Table([[a], [b]]) for a, b in qator]], colWidths=[eni / 4] * 4)
    mt.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, CHEGARA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, CHEGARA),
        ("BACKGROUND", (0, 0), (-1, -1), YASHIL_OCH),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(mt)
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        f"1-yilgi tejash: <b>{pul(n.yillik_tejash)} so'm</b> "
        f"(energiya xarajatining {son(n.tejash_ulush_foiz, 0)}%). "
        f"Yillik CO<sub>2</sub> kamayishi: <b>{son(n.co2_yillik_t, 1)} t</b> "
        f"(bazaviy chiqindining {son(n.co2_ulush_foiz, 0)}%). "
        f"ROI ({n.tahlil_muddati} yil): <b>{son(n.roi_foiz, 0)}%</b>.", _matn))

    sc = n.score
    tarkib = Table([
        ["Mezon", "Ball", "Maks."],
        ["CO2 kamayishi (bazaviy chiqindiga nisbatan)", son(sc.co2_ball, 1), "40"],
        ["O'zini oqlash muddati", son(sc.oqlash_ball, 1), "30"],
        ["Energiya xarajatini tejash", son(sc.tejash_ball, 1), "30"],
        ["Jami", str(sc.ball), "100"],
    ], colWidths=[eni - 44 * mm - 2 * 22 * mm, 22 * mm, 22 * mm])
    ts = _jadval_uslubi()
    ts.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    ts.add("ALIGN", (1, 0), (-1, -1), "CENTER")
    tarkib.setStyle(ts)
    o_ng = [Paragraph(f"Green Score: {sc.daraja} - {sc.xulosa}", _xulosa), Spacer(1, 4), tarkib]
    blok = Table([[_score_doirasi(sc.daraja, sc.ball), o_ng]], colWidths=[40 * mm, eni - 40 * mm])
    blok.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el.append(Spacer(1, 6))
    el.append(KeepTogether([blok]))

    # 3. Yillar bo'yicha
    yillik = [["Yil", "Tejash, so'm", "Jami tejash, so'm", "Sof foyda, so'm", "CO2, t"]]
    for q in n.yillar:
        yillik.append([str(q.yil), pul(q.tejash), pul(q.jami_tejash), pul(q.sof_foyda), son(q.co2_t, 1)])
    yt = Table(yillik, colWidths=[eni * 0.08, eni * 0.23, eni * 0.25, eni * 0.26, eni * 0.18],
               repeatRows=1)
    ys = _jadval_uslubi()
    ys.add("ALIGN", (0, 0), (-1, -1), "RIGHT")
    ys.add("ALIGN", (0, 0), (0, -1), "CENTER")
    for i, q in enumerate(n.yillar, start=1):
        if q.sof_foyda < 0:
            ys.add("TEXTCOLOR", (3, i), (3, i), DARAJA_RANG["D"])
    yt.setStyle(ys)
    el.append(KeepTogether([Paragraph("3. Yillar bo'yicha tejash", _bolim), yt]))

    # 4. Kredit taqqoslash
    kr = n.kredit
    kt = Table([
        ["", "Oddiy kredit", "Yashil kredit"],
        ["Yillik foiz", f"{son(kr.oddiy_foiz, 1)}%", f"{son(kr.yashil_foiz, 1)}%"],
        ["Kredit summasi", f"{pul(kr.summa)} so'm", f"{pul(kr.summa)} so'm"],
        ["Muddat", f"{kr.muddat_yil} yil", f"{kr.muddat_yil} yil"],
        ["Oylik to'lov", f"{pul(kr.oddiy_oylik)} so'm", f"{pul(kr.yashil_oylik)} so'm"],
        ["Jami foiz to'lovi", f"{pul(kr.oddiy_foiz_jami)} so'm", f"{pul(kr.yashil_foiz_jami)} so'm"],
    ], colWidths=[eni * 0.34, eni * 0.33, eni * 0.33])
    ks = _jadval_uslubi()
    ks.add("ALIGN", (1, 0), (-1, -1), "RIGHT")
    ks.add("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold")
    kt.setStyle(ks)
    el.append(KeepTogether([
        Paragraph("4. Kredit taqqoslash", _bolim), kt, Spacer(1, 4),
        Paragraph(f"Yashil kredit bilan foiz to'lovidan tejash: <b>{pul(kr.yutuq)} so'm</b>.", _matn),
    ]))

    # 5. O'tgan yilgi iste'mol
    qisqa = [o[:3] for o in OYLAR]
    ist = [["", *qisqa, "Jami"],
           ["Elektr, kVt·soat", *[pul(v) for v in k.elektr_oylik], pul(k.yillik_elektr)],
           ["Gaz, m³", *[pul(v) for v in k.gaz_oylik], pul(k.yillik_gaz)]]
    birinchi = eni * 0.15
    qolgan = (eni - birinchi) / 13
    it = Table(ist, colWidths=[birinchi] + [qolgan] * 13)
    is_ = _jadval_uslubi()
    is_.add("FONTSIZE", (0, 0), (-1, -1), 7)
    is_.add("ALIGN", (1, 0), (-1, -1), "RIGHT")
    it.setStyle(is_)
    el.append(KeepTogether([
        Paragraph("5. O'tgan yilgi energiya iste'moli", _bolim), it, Spacer(1, 4),
        Paragraph(f"Tariflar: elektr {pul(k.elektr_tarif)} so'm/kVt·soat, gaz {pul(k.gaz_tarif)} so'm/m³. "
                  f"Bazaviy energiya xarajati: {pul(n.bazaviy_xarajat)} so'm/yil, "
                  f"bazaviy CO<sub>2</sub>: {son(n.bazaviy_co2_t, 1)} t/yil.", _matn),
    ]))

    # Farazlar va imzolar
    el.append(KeepTogether([
        Paragraph("Hisob-kitob farazlari", _bolim),
        Paragraph(
            f"Quyosh panellari unumdorligi {son(s.quyosh_unumdorligi, 0)} kVt·soat/kVt/yil, degradatsiya "
            f"{son(s.panel_degradatsiyasi, 1)}%/yil; faqat korxonaning o'z iste'molini qoplaydigan qismi "
            f"hisobga olingan. Tariflarning yillik o'sishi {son(s.tarif_osishi, 1)}%. Emissiya koeffitsientlari: "
            f"elektr {son(s.elektr_co2, 2)} kg CO<sub>2</sub>/kVt·soat, gaz {son(s.gaz_co2, 2)} kg CO<sub>2</sub>/m³. "
            "Green Score - dasturning ichki metodikasi (CO<sub>2</sub> 40 ball, o'zini oqlash 30 ball, "
            "tejash 30 ball); u rasmiy sertifikat emas va bank tomonidan tekshirilishi kerak.", _kichik),
        Spacer(1, 18),
        Table([["Tadbirkor: ______________________", "Bank xodimi: ______________________"]],
              colWidths=[eni / 2, eni / 2],
              style=TableStyle([("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                                ("FONTSIZE", (0, 0), (-1, -1), 9.5)])),
    ]))

    chiz = _sarlavha_va_pastki(hujjat_no, sana)
    doc.build(el, onFirstPage=chiz, onLaterPages=chiz)
    return yol
