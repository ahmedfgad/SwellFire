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
    img = bk.vertical_gradient((w, h), bk.BG_TOP, bk.BG_BOTTOM).convert("RGBA")

    # Battle scene on the right.
    scene_h = int(h * 0.96)
    scene_w = int(scene_h * 0.82)
    sx0 = w - scene_w - int(w * 0.02)
    sy0 = int(h * 0.02)
    bk.compose_battle_scene(img, (sx0, sy0, sx0 + scene_w, sy0 + scene_h),
                            squad_n=5, boss="enemy_w5", label="×2")

    d = ImageDraw.Draw(img)
    # Huge title (left), heavy shadow for punch.
    title = bk.load_font(int(h * 0.20))
    tx, ty = int(w * 0.05), int(h * 0.26)
    d.text((tx + 6, ty + 6), "Swellfire", font=title, fill=(0, 0, 0, 210), anchor="lm")
    bk.draw_wordmark(d, (tx, ty), title, anchor="lm")
    # Tagline.
    sub = bk.load_font(int(h * 0.075))
    d.text((tx + 2, int(h * 0.46) + 2), "Grow your squad. Open fire.", font=sub,
           fill=(4, 20, 24, 200))
    d.text((tx, int(h * 0.46)), "Grow your squad. Open fire.", font=sub,
           fill=bk.EMBER["cream"])
    # Info chip.
    chip = bk.load_font(int(h * 0.052))
    d.text((tx, int(h * 0.62)), "60 levels · 6 worlds · 2-player versus",
           font=chip, fill=bk.EMBER["gold"])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT)
    return img


def main():
    make()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
