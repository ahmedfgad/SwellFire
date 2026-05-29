"""YouTube cover/thumbnail (1280x720), Swellfire brand. Pure PIL + brandkit.

Big title (left) + the core-loop battle scene composed from the game's own
sprites (right). Run: `venv/bin/python tools/make_youtube_thumbnail.py`
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

from tools import brandkit as bk

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "swellfire_media", "youtube_thumbnail_1280x720.png")


def make():
    w, h = 1280, 720
    img = bk.solid_bg((w, h))

    d = ImageDraw.Draw(img)
    # Big title top-left.
    title = bk.load_font(int(h * 0.17))
    tx, ty = int(w * 0.05), int(h * 0.16)
    d.text((tx + 6, ty + 6), "Swellfire", font=title, fill=(0, 0, 0, 210), anchor="lm")
    bk.draw_wordmark(d, (tx, ty), title, anchor="lm")
    sub = bk.load_font(int(h * 0.065))
    d.text((tx + 2, int(h * 0.30) + 2), "Grow your squad. Open fire.", font=sub,
           fill=(4, 30, 30, 200))
    d.text((tx, int(h * 0.30)), "Grow your squad. Open fire.", font=sub,
           fill=bk.EMBER["cream"])
    chip = bk.load_font(int(h * 0.05))
    d.text((tx, int(h * 0.41)), "60 levels · 6 worlds · 2-player versus",
           font=chip, fill=bk.EMBER["gold"])

    # A ×2 gate above a squad firing upward across the bottom.
    bk.draw_gate_panel(img, w / 2, int(h * 0.56), int(w * 0.26), int(h * 0.10), "×2")
    bk.draw_squad_row(img, w / 2, int(h * 0.97), n=6, hero_h=int(h * 0.22), fire=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT)
    return img


def main():
    make()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
