#!/usr/bin/env python3
"""Bot uchun QR-kod: python scripts/make_qr.py <bot_username>  →  web/public/bot-qr.svg"""
from __future__ import annotations

import sys
from pathlib import Path

import qrcode
import qrcode.image.svg

OUT = Path(__file__).resolve().parents[1] / "web" / "public" / "bot-qr.svg"


def main(username: str) -> Path:
    url = f"https://t.me/{username.lstrip('@')}"
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=20, border=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUT))
    print(f"{url} → {OUT}  (keyin: make web-build)")
    return OUT


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("foydalanish: python scripts/make_qr.py <bot_username>")
    main(sys.argv[1])
