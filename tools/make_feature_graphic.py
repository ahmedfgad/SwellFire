"""Google Play feature graphic (1024x500), Swellfire brand. Pure PIL + brandkit.

Left: title + tagline + info line. Right: the core-loop battle scene composed
from the game's own sprites. Run: `venv/bin/python tools/make_feature_graphic.py`
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

from tools import brandkit as bk

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "swellfire_media", "feature_graphic_1024x500.png")


def make():
    w, h = 1024, 500
    img = bk.solid_bg((w, h))

    # Right: a ×2 gate above a squad firing upward.
    gx = int(w * 0.74)
    bk.draw_gate_panel(img, gx, int(h * 0.46), int(w * 0.30), int(h * 0.15), "×2")
    bk.draw_squad_row(img, gx, int(h * 0.96), n=3, hero_h=int(h * 0.30), fire=True)

    d = ImageDraw.Draw(img)
    # Left: title + tagline + info line.
    wm = bk.load_font(int(h * 0.19))
    tx, ty = int(w * 0.04), int(h * 0.27)
    d.text((tx + 4, ty + 4), "Swellfire", font=wm, fill=(4, 30, 30, 200), anchor="lm")
    bk.draw_wordmark(d, (tx, ty), wm, anchor="lm")
    tag = bk.load_font(int(h * 0.072))
    d.text((tx, int(h * 0.50)), "Grow your squad. Open fire.", font=tag,
           fill=bk.EMBER["cream"])
    info = bk.load_font(int(h * 0.052))
    d.text((tx, int(h * 0.70)), "60 levels · 6 worlds · 2-player versus",
           font=info, fill=bk.EMBER["gold"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT)
    return img


def main():
    make()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
