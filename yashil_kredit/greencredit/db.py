"""Lokal SQLite ma'lumotlar bazasi. Hech qanday ma'lumot internetga yuborilmaydi."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from .calc import Kiritma, Sozlamalar


def standart_yol() -> Path:
    """Windows: %APPDATA%\\GreenCredit\\greencredit.db; boshqa tizimlar: ~/.greencredit/."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        papka = Path(os.environ["APPDATA"]) / "GreenCredit"
    else:
        papka = Path.home() / ".greencredit"
    papka.mkdir(parents=True, exist_ok=True)
    return papka / "greencredit.db"


class Baza:
    def __init__(self, yol: str | Path | None = None):
        self.yol = Path(yol) if yol else standart_yol()
        self.conn = sqlite3.connect(self.yol)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS hisoblar (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                yaratilgan TEXT NOT NULL,
                korxona    TEXT NOT NULL,
                loyiha     TEXT NOT NULL,
                kiritma    TEXT NOT NULL,
                ball       INTEGER,
                daraja     TEXT
            );
            CREATE TABLE IF NOT EXISTS sozlamalar (
                id     INTEGER PRIMARY KEY CHECK (id = 1),
                qiymat TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def yopish(self) -> None:
        self.conn.close()

    # --- Hisoblar ---

    def saqlash(self, k: Kiritma, ball: int | None = None, daraja: str | None = None,
                hisob_id: int | None = None) -> int:
        """Yangi hisobni saqlaydi yoki `hisob_id` berilsa mavjudini yangilaydi."""
        vaqt = datetime.now().strftime("%Y-%m-%d %H:%M")
        matn = json.dumps(k.to_dict(), ensure_ascii=False)
        if hisob_id is not None:
            cur = self.conn.execute(
                "UPDATE hisoblar SET yaratilgan=?, korxona=?, loyiha=?, kiritma=?, ball=?, daraja=? "
                "WHERE id=?",
                (vaqt, k.korxona, k.loyiha_nomi, matn, ball, daraja, hisob_id),
            )
            if cur.rowcount:
                self.conn.commit()
                return hisob_id
        cur = self.conn.execute(
            "INSERT INTO hisoblar (yaratilgan, korxona, loyiha, kiritma, ball, daraja) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (vaqt, k.korxona, k.loyiha_nomi, matn, ball, daraja),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def royxat(self) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT id, yaratilgan, korxona, loyiha, ball, daraja FROM hisoblar ORDER BY id DESC"
        ))

    def olish(self, hisob_id: int) -> Kiritma | None:
        row = self.conn.execute("SELECT kiritma FROM hisoblar WHERE id=?", (hisob_id,)).fetchone()
        return Kiritma.from_dict(json.loads(row["kiritma"])) if row else None

    def ochirish(self, hisob_id: int) -> None:
        self.conn.execute("DELETE FROM hisoblar WHERE id=?", (hisob_id,))
        self.conn.commit()

    # --- Sozlamalar ---

    def sozlamalar(self) -> Sozlamalar:
        row = self.conn.execute("SELECT qiymat FROM sozlamalar WHERE id=1").fetchone()
        return Sozlamalar.from_dict(json.loads(row["qiymat"])) if row else Sozlamalar()

    def sozlamalarni_saqlash(self, s: Sozlamalar) -> None:
        self.conn.execute(
            "INSERT INTO sozlamalar (id, qiymat) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET qiymat=excluded.qiymat",
            (json.dumps(s.to_dict()),),
        )
        self.conn.commit()
