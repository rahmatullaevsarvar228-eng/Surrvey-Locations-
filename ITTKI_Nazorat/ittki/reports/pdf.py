"""M10. Report for the audit committee (PDF, reportlab): summary by project, exception list, signature."""
from __future__ import annotations

import os
from datetime import date, datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import clock
from ..core.appsettings import AppSettings
from ..i18n import uz
from ..services import Analysis

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def _fonts() -> tuple[str, str, bool]:
    """(regular, bold, unicode). Uses a system TTF when available, else Helvetica (Latin-1 only)."""
    for reg, bold in _FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                if "ITTKI" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("ITTKI", reg))
                    pdfmetrics.registerFont(TTFont("ITTKI-Bold", bold))
                return "ITTKI", "ITTKI-Bold", True
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", False


_ASCII = {"—": "-", "–": "-", "↔": "<->", "→": "->", "•": "-", "ʻ": "'", "’": "'", "«": '"', "»": '"'}


def export_audit_report(analyses: list[Analysis], path, settings: AppSettings, signer, at: date):
    reg, bold, uni = _fonts()

    def tx(s) -> str:
        s = str(s)
        if not uni:
            for a, b in _ASCII.items():
                s = s.replace(a, b)
            s = s.encode("latin-1", "replace").decode("latin-1")
        return escape(s)

    ss = getSampleStyleSheet()
    base = ParagraphStyle("b", parent=ss["Normal"], fontName=reg, fontSize=8.5, leading=10.5)
    small = ParagraphStyle("s", parent=base, fontSize=7.5, leading=9)
    right = ParagraphStyle("r", parent=base, alignment=TA_RIGHT)
    h1 = ParagraphStyle("h1", parent=base, fontName=bold, fontSize=15, leading=19, textColor=colors.HexColor("#1F4E79"))
    h2 = ParagraphStyle("h2", parent=base, fontName=bold, fontSize=11, leading=14, spaceBefore=8, spaceAfter=4,
                        textColor=colors.HexColor("#1F4E79"))
    hb = ParagraphStyle("hb", parent=base, fontName=bold)

    def P(s, st=base):
        return Paragraph(tx(s), st)

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title="ITTKI Nazorat — audit qo'mitasi",
                            author=signer.name)
    story = [P("ITTKI xarajatlari bo'yicha nazorat hisoboti — audit qo'mitasi uchun", h1),
             P(f"{settings.organization} · {uz.fdate(at)} holatiga · BHMS 11 (2024) | IAS 38"), Spacer(1, 3 * mm)]
    if any(a.record.is_demo for a in analyses):
        story.append(P(f"{uz.DEMO_MARK}. Raqamlar shartli.", small))

    # ---- summary
    n_find = [f for a in analyses for f in a.findings]
    cnt = {lv: sum(1 for f in n_find if f.level == lv) for lv in ("high", "medium", "info")}
    tot_cap = {fw: sum(a.res[fw]["capitalized"] for a in analyses) for fw in ("IAS38", "NAS11")}
    tot_car = {fw: sum(a.carrying[fw] for a in analyses) for fw in ("IAS38", "NAS11")}
    story.append(P("1. Umumiy ko'rsatkichlar", h2))
    kp = [[P("Loyihalar", hb), P("Kapitallashtirilgan IAS 38", hb), P("Kapitallashtirilgan BHMS 11", hb),
           P("Balans qiymati IAS 38", hb), P("Balans qiymati BHMS 11", hb), P("Istisnolar", hb)],
          [P(len(analyses)), P(uz.money(tot_cap["IAS38"]), right), P(uz.money(tot_cap["NAS11"]), right),
           P(uz.money(tot_car["IAS38"]), right), P(uz.money(tot_car["NAS11"]), right),
           P(f"{len(n_find)} (yuqori {cnt['high']}, o'rta {cnt['medium']}, ma'lumot {cnt['info']})")]]
    story.append(_tbl(kp, [25 * mm, 40 * mm, 40 * mm, 40 * mm, 40 * mm, 84 * mm], reg))

    story.append(P("2. Loyihalar bo'yicha", h2))
    rows = [[P(h, hb) for h in ("Kod", "Nomi", "Bosqich", "Qaror IAS 38", "Qaror BHMS 11", "Balans IAS 38",
                                "Balans BHMS 11", "Istisnolar")]]
    for a in analyses:
        rows.append([P(a.record.code), P(a.record.name, small), P(uz.STAGE[a.record.stage]),
                     P(uz.DECISION_SHORT[a.res["IAS38"]["decision"]]), P(uz.DECISION_SHORT[a.res["NAS11"]["decision"]]),
                     P(uz.money(a.carrying["IAS38"]), right), P(uz.money(a.carrying["NAS11"]), right),
                     P(str(len(a.findings)), right)])
    story.append(_tbl(rows, [27 * mm, 78 * mm, 26 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm, 26 * mm], reg))

    story.append(P("3. Nazorat istisnolari", h2))
    order = {"high": 0, "medium": 1, "info": 2}
    items = sorted(((a.record, f) for a in analyses for f in a.findings),
                   key=lambda x: (order[x[1].level], int(x[1].code[1:]), x[0].code))
    rows = [[P(h, hb) for h in ("Daraja", "Kod", "Loyiha", "Qoida", "Tavsif")]]
    level_bg = []
    for i, (rec, f) in enumerate(items, 1):
        rows.append([P(uz.LEVEL[f.level]), P(f.code), P(rec.code), P(uz.CONTROL_TITLE[f.code], small),
                     P((f"[{uz.FW[f.framework]}] " if f.framework else "") + f.message, small)])
        level_bg.append((i, {"high": "#F8E3E1", "medium": "#FBF0D0"}.get(f.level)))
    if not items:
        rows.append([P("—"), P(""), P(""), P("Istisnolar yo'q"), P("")])
    t = _tbl(rows, [18 * mm, 12 * mm, 27 * mm, 60 * mm, 152 * mm], reg)
    for i, bg in level_bg:
        if bg:
            t.setStyle(TableStyle([("BACKGROUND", (0, i), (0, i), colors.HexColor(bg))]))
    story.append(t)

    story += [Spacer(1, 10 * mm),
              P(f"Tayyorladi: {signer.name}, {uz.ROLE.get(signer.role, signer.role)}"),
              P(f"Sana: {uz.fdate(clock.today())}"),
              Spacer(1, 6 * mm), P("Imzo: ____________________________"),
              Spacer(1, 6 * mm),
              P(f"{uz.APP_NAME} dasturida {clock.now_tashkent()} (Toshkent, UTC+5) da avtomatik tuzildi.", small)]

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(reg, 7)
        canvas.drawRightString(d.pagesize[0] - 14 * mm, 8 * mm, f"{d.page}-bet")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def _tbl(rows, widths, font):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9CED6")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t
