"""GreenCredit — yashil kredit uchun lokal dastur (tkinter oynasi).

Uchta asosiy tugma:
  1. Ma'lumot kiritish   — korxona, 12 oylik elektr/gaz hisoblari, loyiha
  2. Foyda hisobi (ROI)  — tejash, o'zini oqlash, CO2, Green Score
  3. Bank uchun pasport  — PDF hisobot
Hamma ma'lumot shu kompyuterdagi SQLite bazasida saqlanadi.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__
from .calc import (OYLAR, Kiritma, KiritmaXatosi, Natija, Sozlamalar, hisobla, mln, namuna_kiritma,
                   pul, raqam_oqi, son, yil_matn)
from .db import Baza
from .report import pasport_yarat

# Ranglar (taqdimot bilan bir xil)
FON = "#F7F9F4"
FON2 = "#EDF4EA"
KARTA = "#FDFEFC"
CHEGARA = "#CFE3D4"
QORA = "#15301F"
MATN = "#3D4F43"
KULRANG = "#5B6B60"
YASHIL = "#1E7A3C"
YASHIL_TO = "#16602F"
APELSIN = "#B45309"
DARAJA_RANG = {"A": "#1E7A3C", "B": "#4E9A3A", "C": "#C98A0B", "D": "#B45309"}

LOYIHA_TURLARI = [
    "Quyosh panellari",
    "Quyosh panellari + issiqlik izolyatsiyasi",
    "Energiya tejovchi yoritish (LED)",
    "Issiqlik izolyatsiyasi",
    "Gaz qozonini almashtirish",
    "Issiqlik nasosi",
]


def _qiymat_matn(v: float) -> str:
    if v == int(v):
        return pul(v)
    return f"{v}".replace(".", ",")


def _moslashuvchan(lbl: tk.Label, chet: int = 32) -> None:
    """Matn qatorini yorliq kengligiga qarab o'raydi (ekran o'lchami har xil bo'lganda ham)."""
    lbl.bind("<Configure>", lambda e: lbl.configure(wraplength=max(e.width - chet, 80)))


def _fayl_och(yol: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(yol))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(yol)])
        else:
            subprocess.Popen(["xdg-open", str(yol)])
    except OSError as e:
        messagebox.showerror("Xatolik", f"Faylni ochib bo'lmadi:\n{e}")


class Ilova(tk.Tk):
    def __init__(self, baza: Baza | None = None):
        super().__init__()
        self.baza = baza or Baza()
        self.sozlamalar = self.baza.sozlamalar()
        self.kiritma: Kiritma | None = None
        self.natija: Natija | None = None
        self.hisob_id: int | None = None
        self.oxirgi_pdf: Path | None = None

        self.title("GreenCredit — Yashil kredit kalkulyatori")
        olcham = self.winfo_fpixels("1i") / 96  # Windows ekran masshtabi (125%, 150%...)
        w = min(int(1240 * olcham), self.winfo_screenwidth() - 40)
        h = min(int(800 * olcham), self.winfo_screenheight() - 80)
        self.geometry(f"{w}x{h}")
        self.minsize(min(w, int(1100 * olcham)), min(h, int(700 * olcham)))
        self.configure(bg=FON)
        self._shriftlar()
        self._uslublar()

        self.sidebar = tk.Frame(self, bg=YASHIL, width=270)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.asosiy = tk.Frame(self, bg=FON)
        self.asosiy.pack(side="left", fill="both", expand=True)

        self.sahifalar: dict[str, tk.Frame] = {}
        self.menyu_tugmalari: dict[str, tk.Button] = {}
        self._sidebar_qur()
        self._kiritish_sahifasi()
        self._roi_sahifasi()
        self._pasport_sahifasi()
        self._tarix_sahifasi()
        self._sozlamalar_sahifasi()
        self.korsat("kiritish")
        self.protocol("WM_DELETE_WINDOW", self._yopish)

    # ------------------------------------------------------------------ umumiy

    def _shriftlar(self) -> None:
        oilalar = set(tkfont.families(self))
        asos = next((f for f in ("Segoe UI", "Helvetica Neue", "DejaVu Sans", "Arial") if f in oilalar),
                    "TkDefaultFont")
        self.f_oddiy = (asos, 11)
        self.f_kichik = (asos, 10)
        self.f_qalin = (asos, 11, "bold")
        self.f_sarlavha = (asos, 22, "bold")
        self.f_ichki = (asos, 13, "bold")
        self.f_katta = (asos, 18, "bold")
        self.f_menyu = (asos, 12, "bold")
        default = tkfont.nametofont("TkDefaultFont")
        default.configure(family=asos, size=11)

    def _uslublar(self) -> None:
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=FON, foreground=QORA, font=self.f_oddiy)
        st.configure("TFrame", background=FON)
        st.configure("Karta.TFrame", background=KARTA)
        st.configure("TLabel", background=FON, foreground=QORA)
        st.configure("Karta.TLabel", background=KARTA, foreground=QORA)
        st.configure("Izoh.TLabel", background=FON, foreground=KULRANG, font=self.f_kichik)
        st.configure("KartaIzoh.TLabel", background=KARTA, foreground=KULRANG, font=self.f_kichik)
        st.configure("TLabelframe", background=KARTA, bordercolor=CHEGARA, relief="solid")
        st.configure("TLabelframe.Label", background=KARTA, foreground=YASHIL, font=self.f_ichki)
        st.configure("TEntry", fieldbackground="#FFFFFF", bordercolor=CHEGARA, padding=4)
        st.configure("TCombobox", fieldbackground="#FFFFFF", padding=4)
        st.configure("Asosiy.TButton", background=YASHIL, foreground="#FFFFFF", font=self.f_qalin,
                     padding=(18, 10), borderwidth=0)
        st.map("Asosiy.TButton", background=[("active", YASHIL_TO), ("disabled", "#9DBBA6")])
        st.configure("Oddiy.TButton", background=FON2, foreground=QORA, padding=(14, 8),
                     bordercolor=CHEGARA)
        st.map("Oddiy.TButton", background=[("active", "#DDEBD9")])
        st.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", rowheight=28,
                     bordercolor=CHEGARA)
        st.configure("Treeview.Heading", background=YASHIL, foreground="#FFFFFF", font=self.f_qalin,
                     relief="flat")
        st.map("Treeview.Heading", background=[("active", YASHIL_TO)])
        st.map("Treeview", background=[("selected", "#CDE5D3")], foreground=[("selected", QORA)])

    def _sidebar_qur(self) -> None:
        tk.Label(self.sidebar, text="GreenCredit", bg=YASHIL, fg="#FFFFFF",
                 font=(self.f_sarlavha[0], 20, "bold"), anchor="w").pack(fill="x", padx=24, pady=(28, 0))
        tk.Label(self.sidebar, text="Yashil kredit kalkulyatori", bg=YASHIL, fg="#D7EBDD",
                 font=self.f_kichik, anchor="w").pack(fill="x", padx=24, pady=(0, 24))

        for kalit, matn in (("kiritish", "1   Ma'lumot kiritish"),
                            ("roi", "2   Foyda hisobi (ROI)"),
                            ("pasport", "3   Bank uchun pasport")):
            self._menyu_tugma(kalit, matn)
        tk.Frame(self.sidebar, bg="#3F9159", height=1).pack(fill="x", padx=24, pady=16)
        self._menyu_tugma("tarix", "Saqlangan hisoblar")
        self._menyu_tugma("sozlamalar", "Sozlamalar")

        tk.Label(self.sidebar, text="Sarvar Rahmatullaev",
                 bg=YASHIL, fg="#D7EBDD", font=self.f_oddiy, justify="left",
                 anchor="w").pack(side="bottom", fill="x", padx=24, pady=24)

    def _menyu_tugma(self, kalit: str, matn: str) -> None:
        b = tk.Button(self.sidebar, text=matn, anchor="w", relief="flat", bd=0, cursor="hand2",
                      font=self.f_menyu, bg=YASHIL, fg="#FFFFFF", activebackground=YASHIL_TO,
                      activeforeground="#FFFFFF", padx=24, pady=12,
                      command=lambda: self.korsat(kalit))
        b.pack(fill="x")
        self.menyu_tugmalari[kalit] = b

    def korsat(self, kalit: str) -> None:
        if kalit == "roi":
            self._roi_yangila()
        elif kalit == "pasport":
            self._pasport_yangila()
        elif kalit == "tarix":
            self._tarix_yangila()
        for k, b in self.menyu_tugmalari.items():
            faol = k == kalit
            b.configure(bg="#FDFEFC" if faol else YASHIL, fg=YASHIL if faol else "#FFFFFF")
        self.sahifalar[kalit].tkraise()

    def _sahifa(self, kalit: str, sarlavha: str, izoh: str) -> tk.Frame:
        f = tk.Frame(self.asosiy, bg=FON)
        f.place(relx=0, rely=0, relwidth=1, relheight=1)
        tk.Label(f, text=sarlavha, bg=FON, fg=QORA, font=self.f_sarlavha,
                 anchor="w").pack(fill="x", padx=32, pady=(24, 0))
        izoh_lbl = tk.Label(f, text=izoh, bg=FON, fg=KULRANG, font=self.f_oddiy,
                            anchor="w", justify="left")
        izoh_lbl.pack(fill="x", padx=32, pady=(2, 16))
        _moslashuvchan(izoh_lbl, 8)
        self.sahifalar[kalit] = f
        return f

    def _yopish(self) -> None:
        self.baza.yopish()
        self.destroy()

    # ------------------------------------------------------------ 1-tugma

    def _kiritish_sahifasi(self) -> None:
        f = self._sahifa("kiritish", "1. Ma'lumot kiritish",
                         "O'tgan yilgi elektr va gaz hisoblarini hamda rejalashtirilgan loyihani kiriting. "
                         "Ma'lumotlar hech qayerga yuborilmaydi.")
        past = tk.Frame(f, bg=FON)
        past.pack(side="bottom", fill="x", padx=32, pady=16)
        tana = tk.Frame(f, bg=FON)
        tana.pack(fill="both", expand=True, padx=32)
        tana.columnconfigure(0, weight=5, uniform="k")
        tana.columnconfigure(1, weight=4, uniform="k")

        chap = tk.Frame(tana, bg=FON)
        chap.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ong = tk.Frame(tana, bg=FON)
        ong.grid(row=0, column=1, sticky="nsew")

        self.v: dict[str, tk.StringVar] = {}

        def maydon(ota, qator, kalit, nom, birlik=""):
            ttk.Label(ota, text=nom, style="Karta.TLabel").grid(row=qator, column=0, sticky="w",
                                                                 pady=2, padx=(0, 12))
            var = tk.StringVar()
            self.v[kalit] = var
            e = ttk.Entry(ota, textvariable=var, width=28)
            e.grid(row=qator, column=1, sticky="ew", pady=2)
            if birlik:
                ttk.Label(ota, text=birlik, style="KartaIzoh.TLabel").grid(row=qator, column=2,
                                                                           sticky="w", padx=(8, 0))
            return e

        kor = ttk.LabelFrame(chap, text="  Korxona  ", padding=(14, 8))
        kor.pack(fill="x", pady=(0, 8))
        kor.columnconfigure(1, weight=1)
        maydon(kor, 0, "korxona", "Korxona nomi")
        maydon(kor, 1, "faoliyat", "Faoliyat turi")
        maydon(kor, 2, "hudud", "Hudud")

        tar = ttk.LabelFrame(chap, text="  Tariflar  ", padding=(14, 8))
        tar.pack(fill="x", pady=(0, 8))
        tar.columnconfigure(1, weight=1)
        maydon(tar, 0, "elektr_tarif", "Elektr tarifi", "so'm / kVt·soat")
        maydon(tar, 1, "gaz_tarif", "Gaz tarifi", "so'm / m³")

        loy = ttk.LabelFrame(chap, text="  Loyiha  ", padding=(14, 8))
        loy.pack(fill="x")
        loy.columnconfigure(1, weight=1)
        ttk.Label(loy, text="Loyiha turi", style="Karta.TLabel").grid(row=0, column=0, sticky="w", pady=2)
        self.v["loyiha_nomi"] = tk.StringVar(value=LOYIHA_TURLARI[0])
        ttk.Combobox(loy, textvariable=self.v["loyiha_nomi"], values=LOYIHA_TURLARI).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=2)
        maydon(loy, 1, "investitsiya", "Loyiha narxi", "so'm")
        maydon(loy, 2, "quyosh_quvvati", "Quyosh panellari quvvati", "kVt")
        maydon(loy, 3, "elektr_tejash_foiz", "Qo'shimcha elektr tejash", "%")
        maydon(loy, 4, "gaz_tejash_foiz", "Gaz tejash", "%")
        ttk.Label(loy, text="Panel yo'q bo'lsa quvvatga 0 yozing.",
                  style="KartaIzoh.TLabel").grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))

        oy = ttk.LabelFrame(ong, text="  O'tgan yilgi hisoblar  ", padding=(14, 8))
        oy.pack(fill="both", expand=True)
        for c in (1, 2):
            oy.columnconfigure(c, weight=1)
        ttk.Label(oy, text="Oy", style="KartaIzoh.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(oy, text="Elektr, kVt·soat", style="KartaIzoh.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(oy, text="Gaz, m³", style="KartaIzoh.TLabel").grid(row=0, column=2, sticky="w", padx=(8, 0))
        self.elektr_v: list[tk.StringVar] = []
        self.gaz_v: list[tk.StringVar] = []
        for i, nom in enumerate(OYLAR, start=1):
            ttk.Label(oy, text=nom, style="Karta.TLabel").grid(row=i, column=0, sticky="w", pady=2,
                                                               padx=(0, 12))
            ev, gv = tk.StringVar(), tk.StringVar()
            for var in (ev, gv):
                var.trace_add("write", lambda *_: self._jami_yangila())
            ttk.Entry(oy, textvariable=ev, width=12).grid(row=i, column=1, sticky="ew", pady=1)
            ttk.Entry(oy, textvariable=gv, width=12).grid(row=i, column=2, sticky="ew", pady=1, padx=(8, 0))
            self.elektr_v.append(ev)
            self.gaz_v.append(gv)
        self.jami_lbl = ttk.Label(oy, text="", style="Karta.TLabel", font=self.f_qalin)
        self.jami_lbl.grid(row=13, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Button(past, text="Saqlash va hisoblash  →", style="Asosiy.TButton",
                   command=self._hisobla).pack(side="right")
        ttk.Button(past, text="Namuna bilan to'ldirish", style="Oddiy.TButton",
                   command=lambda: self._formaga_yoz(namuna_kiritma(), yangi=True)).pack(side="left")
        ttk.Button(past, text="Tozalash", style="Oddiy.TButton",
                   command=lambda: self._formaga_yoz(Kiritma(), yangi=True)).pack(side="left", padx=8)
        self._formaga_yoz(Kiritma(), yangi=True)

    def _jami_yangila(self) -> None:
        def yig(vs):
            jami = 0.0
            for v in vs:
                try:
                    jami += raqam_oqi(v.get())
                except ValueError:
                    pass
            return jami
        self.jami_lbl.configure(
            text=f"Yillik jami:\nelektr {pul(yig(self.elektr_v))} kVt·soat,  gaz {pul(yig(self.gaz_v))} m³",
            justify="left")

    def _formaga_yoz(self, k: Kiritma, yangi: bool = False) -> None:
        for kalit in ("korxona", "faoliyat", "hudud", "loyiha_nomi"):
            self.v[kalit].set(getattr(k, kalit))
        for kalit in ("elektr_tarif", "gaz_tarif", "investitsiya", "quyosh_quvvati",
                      "elektr_tejash_foiz", "gaz_tejash_foiz"):
            val = getattr(k, kalit)
            self.v[kalit].set(_qiymat_matn(val) if val else "")
        for var, val in zip(self.elektr_v, k.elektr_oylik):
            var.set(_qiymat_matn(val) if val else "")
        for var, val in zip(self.gaz_v, k.gaz_oylik):
            var.set(_qiymat_matn(val) if val else "")
        if yangi:
            self.hisob_id = None
            self.natija = None
            self.oxirgi_pdf = None

    def _formadan_oqi(self) -> Kiritma:
        xatolar = []

        def r(nom, var):
            try:
                return raqam_oqi(var.get())
            except ValueError:
                xatolar.append(f"«{nom}» maydonida son noto'g'ri: {var.get()!r}")
                return 0.0

        k = Kiritma(
            korxona=self.v["korxona"].get().strip(),
            faoliyat=self.v["faoliyat"].get().strip(),
            hudud=self.v["hudud"].get().strip(),
            loyiha_nomi=self.v["loyiha_nomi"].get().strip() or LOYIHA_TURLARI[0],
            elektr_tarif=r("Elektr tarifi", self.v["elektr_tarif"]),
            gaz_tarif=r("Gaz tarifi", self.v["gaz_tarif"]),
            investitsiya=r("Loyiha narxi", self.v["investitsiya"]),
            quyosh_quvvati=r("Quyosh panellari quvvati", self.v["quyosh_quvvati"]),
            elektr_tejash_foiz=r("Qo'shimcha elektr tejash", self.v["elektr_tejash_foiz"]),
            gaz_tejash_foiz=r("Gaz tejash", self.v["gaz_tejash_foiz"]),
            elektr_oylik=[r(f"Elektr, {o}", v) for o, v in zip(OYLAR, self.elektr_v)],
            gaz_oylik=[r(f"Gaz, {o}", v) for o, v in zip(OYLAR, self.gaz_v)],
        )
        if xatolar:
            raise KiritmaXatosi("\n".join(xatolar))
        return k

    def _hisobla(self) -> None:
        try:
            k = self._formadan_oqi()
            n = hisobla(k, self.sozlamalar)
        except KiritmaXatosi as e:
            messagebox.showwarning("Ma'lumot yetarli emas", str(e))
            return
        self.kiritma, self.natija = k, n
        self.oxirgi_pdf = None
        self.hisob_id = self.baza.saqlash(k, n.score.ball, n.score.daraja, self.hisob_id)
        self.korsat("roi")

    # ------------------------------------------------------------ 2-tugma

    def _roi_sahifasi(self) -> None:
        f = self._sahifa("roi", "2. Foyda hisobi (ROI)",
                         "Dastur o'zi hisoblaydi: loyiha necha yilda o'zini oqlaydi, qancha tejaydi "
                         "va CO₂ ni qanchaga kamaytiradi.")
        self.roi_bosh = tk.Label(f, text="Avval «1. Ma'lumot kiritish» bo'limida ma'lumotlarni kiriting "
                                         "va «Saqlash va hisoblash» tugmasini bosing.",
                                 bg=FON, fg=KULRANG, font=self.f_ichki)
        self.roi_tana = tk.Frame(f, bg=FON)

        kartalar = tk.Frame(self.roi_tana, bg=FON)
        kartalar.pack(fill="x")
        self.karta_lbl: dict[str, tuple[tk.Label, tk.Label]] = {}
        for i, kalit in enumerate(("investitsiya", "oqlash", "tejash", "co2", "score")):
            kartalar.columnconfigure(i, weight=1, uniform="karta")
            box = tk.Frame(kartalar, bg=KARTA, highlightbackground=CHEGARA, highlightthickness=1)
            box.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            nom = tk.Label(box, text="", bg=KARTA, fg=KULRANG, font=self.f_kichik, anchor="w")
            nom.pack(fill="x", padx=16, pady=(14, 0))
            qiymat = tk.Label(box, text="", bg=KARTA, fg=QORA, font=self.f_katta, anchor="w")
            qiymat.pack(fill="x", padx=16)
            izoh = tk.Label(box, text="", bg=KARTA, fg=MATN, font=self.f_kichik, anchor="w",
                            justify="left")
            izoh.pack(fill="x", padx=16, pady=(0, 14))
            _moslashuvchan(izoh, 8)
            self.karta_lbl[kalit] = (nom, qiymat, izoh)  # type: ignore[assignment]

        orta = tk.Frame(self.roi_tana, bg=FON)
        orta.pack(fill="both", expand=True, pady=16)
        orta.columnconfigure(0, weight=1, uniform="o")
        orta.columnconfigure(1, weight=1, uniform="o")
        orta.rowconfigure(0, weight=1)

        grafik_box = tk.Frame(orta, bg=KARTA, highlightbackground=CHEGARA, highlightthickness=1)
        grafik_box.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(grafik_box, text="Jami tejash va investitsiya", bg=KARTA, fg=QORA,
                 font=self.f_qalin, anchor="w").pack(fill="x", padx=16, pady=(12, 0))
        self.grafik = tk.Canvas(grafik_box, bg=KARTA, highlightthickness=0, height=260)
        self.grafik.pack(fill="both", expand=True, padx=8, pady=8)
        self.grafik.bind("<Configure>", lambda _e: self._grafik_chiz())

        jadval_box = tk.Frame(orta, bg=FON)
        jadval_box.grid(row=0, column=1, sticky="nsew")
        ustunlar = ("yil", "tejash", "jami", "sof", "co2")
        self.jadval = ttk.Treeview(jadval_box, columns=ustunlar, show="headings", height=10)
        for kalit, nom, eni in (("yil", "Yil", 36), ("tejash", "Tejash", 100),
                                ("jami", "Jami", 105), ("sof", "Sof foyda", 112),
                                ("co2", "CO₂, t", 52)):
            self.jadval.heading(kalit, text=nom)
            self.jadval.column(kalit, width=eni, minwidth=40, stretch=True,
                               anchor="e" if kalit != "yil" else "center")
        self.jadval.tag_configure("manfiy", foreground=APELSIN)
        self.jadval.pack(fill="both", expand=True)

        past = tk.Frame(self.roi_tana, bg=FON)
        past.pack(fill="x")
        ttk.Button(past, text="3. Pasport yaratish  →", style="Asosiy.TButton",
                   command=lambda: self.korsat("pasport")).pack(side="right", padx=(16, 0))
        self.kredit_lbl = tk.Label(past, text="", bg=FON2, fg=QORA, font=self.f_oddiy, justify="left",
                                   anchor="w", padx=16, pady=12)
        self.kredit_lbl.pack(side="left", fill="x", expand=True)
        _moslashuvchan(self.kredit_lbl)

    def _roi_yangila(self) -> None:
        n = self.natija
        if n is None:
            self.roi_tana.pack_forget()
            self.roi_bosh.pack(fill="x", padx=32, pady=40)
            return
        self.roi_bosh.pack_forget()
        self.roi_tana.pack(fill="both", expand=True, padx=32, pady=(0, 20))

        def karta(kalit, nom, qiymat, izoh, rang=QORA):
            a, b, c = self.karta_lbl[kalit]  # type: ignore[misc]
            a.configure(text=nom)
            b.configure(text=qiymat, fg=rang)
            c.configure(text=izoh)

        karta("investitsiya", "Investitsiya", mln(n.investitsiya), "so'm")
        karta("oqlash", "O'zini oqlaydi", yil_matn(n.oqlash_muddati, n.tahlil_muddati),
              f"1-yil: {mln(n.yillik_tejash)} so'm", YASHIL)
        karta("tejash", f"{n.tahlil_muddati} yilda", mln(n.jami_tejash),
              f"so'm · ROI {son(n.roi_foiz, 0)}%", YASHIL)
        karta("co2", f"CO₂ ({n.tahlil_muddati} yil)", f"{son(n.co2_jami_t, 0)} t",
              f"yiliga {son(n.co2_yillik_t, 1)} t", YASHIL)
        sc = n.score
        karta("score", "Green Score", f"{sc.daraja} · {sc.ball}", sc.xulosa,
              DARAJA_RANG.get(sc.daraja, QORA))

        self.jadval.delete(*self.jadval.get_children())
        for q in n.yillar:
            self.jadval.insert("", "end", values=(q.yil, pul(q.tejash), pul(q.jami_tejash),
                                                  pul(q.sof_foyda), son(q.co2_t, 1)),
                               tags=("manfiy",) if q.sof_foyda < 0 else ())

        kr = n.kredit
        self.kredit_lbl.configure(
            text=f"Kredit {mln(kr.summa)} so'm, {kr.muddat_yil} yil. Oylik to'lov: oddiy "
                 f"({son(kr.oddiy_foiz, 0)}%) {pul(kr.oddiy_oylik)} so'm, yashil ({son(kr.yashil_foiz, 0)}%) "
                 f"{pul(kr.yashil_oylik)} so'm.\nYashil kredit foiz to'lovidan {pul(kr.yutuq)} so'm tejaydi.")
        self._grafik_chiz()

    def _grafik_chiz(self) -> None:
        c = self.grafik
        c.delete("all")
        n = self.natija
        if n is None:
            return
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:
            return
        chap, ong, tepa, past = 64, 16, 16, 34
        maks = max(max(q.jami_tejash for q in n.yillar), n.investitsiya) * 1.1
        eni = (w - chap - ong) / len(n.yillar)

        def y(v):
            return tepa + (h - tepa - past) * (1 - v / maks)

        for i in range(5):
            v = maks * i / 4
            c.create_line(chap, y(v), w - ong, y(v), fill="#E4ECE2")
            c.create_text(chap - 8, y(v), text=mln(v) if v else "0", anchor="e", fill=KULRANG,
                          font=self.f_kichik)
        for i, q in enumerate(n.yillar):
            x0 = chap + i * eni + eni * 0.18
            x1 = chap + (i + 1) * eni - eni * 0.18
            rang = YASHIL if q.jami_tejash >= n.investitsiya else "#9DC7A8"
            c.create_rectangle(x0, y(q.jami_tejash), x1, y(0), fill=rang, outline="")
            c.create_text((x0 + x1) / 2, h - past + 14, text=str(q.yil), fill=KULRANG, font=self.f_kichik)
        yi = y(n.investitsiya)
        c.create_line(chap, yi, w - ong, yi, fill=APELSIN, width=2, dash=(6, 4))
        yozuv = c.create_text(chap + 8, yi - 12, text=f"Investitsiya {mln(n.investitsiya)}", anchor="w",
                              fill=APELSIN, font=self.f_kichik)
        x0, y0, x1, y1 = c.bbox(yozuv)
        c.tag_lower(c.create_rectangle(x0 - 4, y0 - 1, x1 + 4, y1 + 1, fill=KARTA, outline=""), yozuv)

    # ------------------------------------------------------------ 3-tugma

    def _pasport_sahifasi(self) -> None:
        f = self._sahifa("pasport", "3. Bank uchun pasport",
                         "Bir tugma bilan Green Score bo'lgan PDF hisobot yarating va uni bankka olib boring.")
        self.pasport_bosh = tk.Label(f, text="Avval «1. Ma'lumot kiritish» va «2. Foyda hisobi» "
                                             "bosqichlarini bajaring.",
                                     bg=FON, fg=KULRANG, font=self.f_ichki)
        self.pasport_tana = tk.Frame(f, bg=FON)

        karta = tk.Frame(self.pasport_tana, bg=KARTA, highlightbackground=CHEGARA, highlightthickness=1)
        karta.pack(fill="x")
        self.score_canvas = tk.Canvas(karta, width=180, height=180, bg=KARTA, highlightthickness=0)
        self.score_canvas.pack(side="left", padx=28, pady=24)
        matn = tk.Frame(karta, bg=KARTA)
        matn.pack(side="left", fill="both", expand=True, pady=24, padx=(0, 28))
        self.pasport_sarlavha = tk.Label(matn, text="", bg=KARTA, fg=QORA, font=self.f_sarlavha,
                                         anchor="w", justify="left")
        self.pasport_sarlavha.pack(fill="x")
        self.pasport_xulosa = tk.Label(matn, text="", bg=KARTA, fg=YASHIL, font=self.f_ichki,
                                       anchor="w", justify="left")
        self.pasport_xulosa.pack(fill="x")
        self.pasport_matn = tk.Label(matn, text="", bg=KARTA, fg=MATN, font=self.f_oddiy,
                                     anchor="w", justify="left")
        self.pasport_matn.pack(fill="x", pady=(8, 0))
        _moslashuvchan(self.pasport_matn, 8)

        tugmalar = tk.Frame(self.pasport_tana, bg=FON)
        tugmalar.pack(fill="x", pady=20)
        ttk.Button(tugmalar, text="PDF pasport yaratish", style="Asosiy.TButton",
                   command=self._pdf_yarat).pack(side="left")
        self.och_tugma = ttk.Button(tugmalar, text="PDF ni ochish", style="Oddiy.TButton",
                                    command=lambda: self.oxirgi_pdf and _fayl_och(self.oxirgi_pdf))
        self.papka_tugma = ttk.Button(tugmalar, text="Papkani ochish", style="Oddiy.TButton",
                                      command=lambda: self.oxirgi_pdf and _fayl_och(self.oxirgi_pdf.parent))
        self.pdf_lbl = tk.Label(self.pasport_tana, text="", bg=FON, fg=YASHIL, font=self.f_oddiy,
                                anchor="w", justify="left")
        self.pdf_lbl.pack(fill="x")
        _moslashuvchan(self.pdf_lbl, 8)

        tk.Label(self.pasport_tana,
                 text="Bankda nima deyish kerak:\n«Mana hisob-kitoblar. Loyiha ekologik va o'zini "
                      "oqlaydi —\nmenga yashil kredit bering.»",
                 bg=FON2, fg=QORA, font=self.f_ichki, anchor="w", justify="left",
                 padx=20, pady=16).pack(fill="x", pady=(24, 0))

    def _pasport_yangila(self) -> None:
        n = self.natija
        if n is None or self.kiritma is None:
            self.pasport_tana.pack_forget()
            self.pasport_bosh.pack(fill="x", padx=32, pady=40)
            return
        self.pasport_bosh.pack_forget()
        self.pasport_tana.pack(fill="both", expand=True, padx=32)
        sc = n.score
        c = self.score_canvas
        c.delete("all")
        rang = DARAJA_RANG.get(sc.daraja, YASHIL)
        c.create_oval(10, 10, 170, 170, fill=rang, outline="")
        c.create_text(90, 78, text=sc.daraja, fill="#FFFFFF", font=(self.f_sarlavha[0], 56, "bold"))
        c.create_text(90, 132, text=f"{sc.ball} / 100", fill="#FFFFFF", font=self.f_qalin)
        self.pasport_sarlavha.configure(text=f"Green Score: {sc.daraja}")
        self.pasport_xulosa.configure(text=sc.xulosa, fg=rang)
        self.pasport_matn.configure(
            text=f"{self.kiritma.korxona} · {self.kiritma.loyiha_nomi}\n\n"
                 f"Investitsiya {mln(n.investitsiya)} so'm, o'zini oqlash "
                 f"{yil_matn(n.oqlash_muddati, n.tahlil_muddati)}, {n.tahlil_muddati} yilda "
                 f"{mln(n.jami_tejash)} so'm tejash, CO₂ {son(n.co2_jami_t, 1)} t ga kamayadi.\n\n"
                 f"Ball tarkibi: CO₂ {son(sc.co2_ball, 0)}/40, o'zini oqlash {son(sc.oqlash_ball, 0)}/30, "
                 f"tejash {son(sc.tejash_ball, 0)}/30.")
        self._pdf_holati()

    def _pdf_holati(self) -> None:
        if self.oxirgi_pdf:
            self.och_tugma.pack(side="left", padx=(12, 0))
            self.papka_tugma.pack(side="left", padx=(8, 0))
            self.pdf_lbl.configure(text=f"Saqlandi: {self.oxirgi_pdf}")
        else:
            self.och_tugma.pack_forget()
            self.papka_tugma.pack_forget()
            self.pdf_lbl.configure(text="")

    def _pdf_yarat(self) -> None:
        if self.natija is None or self.kiritma is None:
            return
        xavfsiz = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in self.kiritma.korxona)
        nom = f"Yashil_pasport_{xavfsiz.strip().replace(' ', '_') or 'korxona'}.pdf"
        yol = filedialog.asksaveasfilename(
            title="PDF pasportni saqlash", defaultextension=".pdf", initialfile=nom,
            initialdir=str(Path.home() / "Documents") if (Path.home() / "Documents").exists() else None,
            filetypes=[("PDF fayl", "*.pdf")])
        if not yol:
            return
        try:
            self.oxirgi_pdf = pasport_yarat(yol, self.kiritma, self.natija, self.sozlamalar, self.hisob_id)
        except OSError as e:
            messagebox.showerror("Xatolik", f"PDF saqlanmadi:\n{e}\n\nFayl boshqa dasturda ochiq emasligini "
                                            "tekshiring.")
            return
        self._pdf_holati()
        if messagebox.askyesno("Tayyor", "PDF pasport yaratildi. Hozir ochilsinmi?"):
            _fayl_och(self.oxirgi_pdf)

    # ------------------------------------------------------------ tarix

    def _tarix_sahifasi(self) -> None:
        f = self._sahifa("tarix", "Saqlangan hisoblar",
                         "Barcha hisoblar shu kompyuterdagi lokal bazada saqlanadi.")
        tana = tk.Frame(f, bg=FON)
        tana.pack(fill="both", expand=True, padx=32, pady=(0, 20))
        ustunlar = ("id", "sana", "korxona", "loyiha", "score")
        self.tarix = ttk.Treeview(tana, columns=ustunlar, show="headings")
        for kalit, nom, eni in (("id", "№", 40), ("sana", "Sana", 150), ("korxona", "Korxona", 220),
                                ("loyiha", "Loyiha", 280), ("score", "Green Score", 120)):
            self.tarix.heading(kalit, text=nom)
            self.tarix.column(kalit, width=eni, anchor="w" if kalit in ("korxona", "loyiha") else "center")
        self.tarix.pack(fill="both", expand=True)
        self.tarix.bind("<Double-1>", lambda _e: self._tarixdan_och())
        t = tk.Frame(tana, bg=FON)
        t.pack(fill="x", pady=(12, 0))
        ttk.Button(t, text="Ochish", style="Asosiy.TButton", command=self._tarixdan_och).pack(side="left")
        ttk.Button(t, text="O'chirish", style="Oddiy.TButton", command=self._tarixdan_ochir).pack(
            side="left", padx=8)
        ttk.Label(tana, text=f"Baza fayli: {self.baza.yol}", style="Izoh.TLabel").pack(anchor="w", pady=(8, 0))

    def _tarix_yangila(self) -> None:
        self.tarix.delete(*self.tarix.get_children())
        for r in self.baza.royxat():
            score = f"{r['daraja']} · {r['ball']}" if r["daraja"] else "-"
            self.tarix.insert("", "end", iid=str(r["id"]),
                              values=(r["id"], r["yaratilgan"], r["korxona"], r["loyiha"], score))

    def _tanlangan_id(self) -> int | None:
        sel = self.tarix.selection()
        return int(sel[0]) if sel else None

    def _tarixdan_och(self) -> None:
        hid = self._tanlangan_id()
        if hid is None:
            messagebox.showinfo("Tanlang", "Ro'yxatdan hisobni tanlang.")
            return
        k = self.baza.olish(hid)
        if k is None:
            return
        self._formaga_yoz(k, yangi=True)
        self.hisob_id = hid
        try:
            self.kiritma, self.natija = k, hisobla(k, self.sozlamalar)
        except KiritmaXatosi:
            self.korsat("kiritish")
            return
        self.korsat("roi")

    def _tarixdan_ochir(self) -> None:
        hid = self._tanlangan_id()
        if hid is None:
            return
        if messagebox.askyesno("O'chirish", "Tanlangan hisob o'chirilsinmi? Buni qaytarib bo'lmaydi."):
            self.baza.ochirish(hid)
            if self.hisob_id == hid:
                self.hisob_id = None
            self._tarix_yangila()

    # ------------------------------------------------------------ sozlamalar

    SOZLAMA_MAYDONLARI = [
        ("quyosh_unumdorligi", "Quyosh panellari unumdorligi", "kVt·soat / kVt / yil"),
        ("panel_degradatsiyasi", "Panel quvvatining yillik kamayishi", "%"),
        ("tarif_osishi", "Tariflarning yillik o'sishi", "%"),
        ("elektr_co2", "Elektr emissiya koeffitsienti", "kg CO₂ / kVt·soat"),
        ("gaz_co2", "Gaz emissiya koeffitsienti", "kg CO₂ / m³"),
        ("tahlil_muddati", "Tahlil muddati", "yil"),
        ("oddiy_foiz", "Oddiy kredit foizi", "% yillik"),
        ("yashil_foiz", "Yashil kredit foizi", "% yillik"),
        ("kredit_muddati", "Kredit muddati", "yil"),
        ("kredit_ulushi", "Investitsiyaning kreditdan qismi", "%"),
    ]

    def _sozlamalar_sahifasi(self) -> None:
        f = self._sahifa("sozlamalar", "Sozlamalar",
                         "Hisob-kitob farazlari. Ular PDF pasportda ham ko'rsatiladi — mahalliy "
                         "ma'lumotlarga moslab o'zgartiring.")
        box = ttk.LabelFrame(f, text="  Farazlar  ", padding=18)
        box.pack(fill="x", padx=32)
        box.columnconfigure(3, weight=1)
        self.sv: dict[str, tk.StringVar] = {}
        for i, (kalit, nom, birlik) in enumerate(self.SOZLAMA_MAYDONLARI):
            ttk.Label(box, text=nom, style="Karta.TLabel").grid(row=i, column=0, sticky="w", pady=4,
                                                                padx=(0, 16))
            var = tk.StringVar()
            self.sv[kalit] = var
            ttk.Entry(box, textvariable=var, width=16).grid(row=i, column=1, sticky="w", pady=4)
            ttk.Label(box, text=birlik, style="KartaIzoh.TLabel").grid(row=i, column=2, sticky="w",
                                                                       padx=(8, 0))
        t = tk.Frame(f, bg=FON)
        t.pack(fill="x", padx=32, pady=20)
        ttk.Button(t, text="Saqlash", style="Asosiy.TButton", command=self._sozlamalarni_saqla).pack(
            side="left")
        ttk.Button(t, text="Standart qiymatlar", style="Oddiy.TButton",
                   command=lambda: self._sozlamalarni_yoz(Sozlamalar())).pack(side="left", padx=8)
        self._sozlamalarni_yoz(self.sozlamalar)

    def _sozlamalarni_yoz(self, s: Sozlamalar) -> None:
        for kalit, var in self.sv.items():
            var.set(f"{getattr(s, kalit)}".replace(".", ","))

    def _sozlamalarni_saqla(self) -> None:
        qiymatlar = {}
        for kalit, nom, _ in self.SOZLAMA_MAYDONLARI:
            try:
                v = raqam_oqi(self.sv[kalit].get())
            except ValueError:
                messagebox.showwarning("Xato", f"«{nom}» uchun son kiriting.")
                return
            if v < 0:
                messagebox.showwarning("Xato", f"«{nom}» manfiy bo'lishi mumkin emas.")
                return
            qiymatlar[kalit] = v
        for kalit in ("tahlil_muddati", "kredit_muddati"):
            qiymatlar[kalit] = int(round(qiymatlar[kalit]))
            if not 1 <= qiymatlar[kalit] <= 30:
                messagebox.showwarning("Xato", "Muddatlar 1 dan 30 yilgacha bo'lishi kerak.")
                return
        self.sozlamalar = Sozlamalar.from_dict(qiymatlar)
        self.baza.sozlamalarni_saqlash(self.sozlamalar)
        if self.kiritma is not None:
            try:
                self.natija = hisobla(self.kiritma, self.sozlamalar)
                self.oxirgi_pdf = None
            except KiritmaXatosi:
                self.natija = None
        messagebox.showinfo("Saqlandi", "Sozlamalar saqlandi. Natijalar yangi farazlar bilan qayta hisoblandi.")


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # aniq shriftlar (yuqori DPI ekranlar)
        except (AttributeError, OSError):
            pass
    Ilova().mainloop()


if __name__ == "__main__":
    main()
