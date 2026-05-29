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
    img = bk.vertical_gradient((w, h), bk.BG_TOP, bk.BG_BOTTOM).convert("RGBA")

    # Battle scene on the right (squad -> x2 gate -> dragon boss).
    scene_h = int(h * 0.94)
    scene_w = int(scene_h * 0.82)
    sx0 = w - scene_w - int(w * 0.02)
    sy0 = int(h * 0.03)
    bk.compose_battle_scene(img, (sx0, sy0, sx0 + scene_w, sy0 + scene_h),
                            squad_n=4, boss="enemy_w5", label="×2")

    d = ImageDraw.Draw(img)
    # Title wordmark with shadow (left).
    wm = bk.load_font(int(h * 0.24))
    tx, ty = int(w * 0.05), int(h * 0.30)
    d.text((tx + 4, ty + 4), "Swellfire", font=wm, fill=(4, 20, 24, 200), anchor="lm")
    bk.draw_wordmark(d, (tx, ty), wm, anchor="lm")
    # Tagline + info line.
    tag = bk.load_font(int(h * 0.085))
    d.text((tx, int(h * 0.55)), "Grow your squad. Open fire.", font=tag,
           fill=bk.EMBER["cream"])
    info = bk.load_font(int(h * 0.058))
    d.text((tx, int(h * 0.74)), "60 levels  ·  6 worlds  ·  2-player versus",
           font=info, fill=bk.EMBER["gold"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT)
    return img


def main():
    make()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
