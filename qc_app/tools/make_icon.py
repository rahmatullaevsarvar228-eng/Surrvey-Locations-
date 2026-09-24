# -*- coding: utf-8 -*-
"""Рисует иконку приложения (синий «щит» с галочкой) в packaging/app.ico."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bg = Image.new("RGBA", (S, S))
    top, bottom = (58, 141, 255), (0, 96, 208)
    px = bg.load()
    for y in range(S):
        k = y / (S - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)) + (255,)
        for x in range(S):
            px[x, y] = c
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=220, fill=255)
    img.paste(bg, (0, 0), mask)
    shield = [(512, 190), (790, 300), (790, 520), (760, 650), (680, 760), (512, 850),
              (344, 760), (264, 650), (234, 520), (234, 300)]
    tint = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(tint).polygon(shield, fill=(255, 255, 255, 48))
    img = Image.alpha_composite(img, tint)
    d = ImageDraw.Draw(img)
    d.line(shield + [shield[0]], fill=(255, 255, 255, 255), width=44, joint="curve")
    d.line([(390, 530), (480, 620), (650, 440)], fill=(255, 255, 255, 255), width=64, joint="curve")
    for x, y in [(390, 530), (650, 440)]:
        d.ellipse((x - 32, y - 32, x + 32, y + 32), fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "packaging" / "app.ico")
    draw().save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(out)
