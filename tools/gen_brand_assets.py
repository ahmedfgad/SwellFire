"""Generate Swellfire's launcher/window icon and presplash (Ember brand).

Overwrites the repo-root icon.png (512x512) and presplash.png (1920x1080)
that buildozer.spec / Swellfire.spec reference, and copies both into
swellfire_media/. Pure PIL + brandkit. Re-run: `venv/bin/python tools/gen_brand_assets.py`
"""

import os
import sys
import shutil

# Ensure the repo root is on sys.path when run as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

from tools import brandkit as bk

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "swellfire_media")


def make_icon():
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Rounded-square teal background (bright bottom so the dark squad pops).
    bg = bk.vertical_gradient((size, size), bk.BG_TOP, bk.BG_BOTTOM)
    bg = bg.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1),
                                           radius=int(size * 0.22), fill=255)
    img.paste(bg, (0, 0), mask)
    # Real-sprite battle scene (tight 3-soldier squad reads at icon size).
    bk.draw_logo_glyph(img, (int(size * 0.06), int(size * 0.05),
                             int(size * 0.94), int(size * 0.95)),
                       squad_n=3)
    return img


def make_presplash():
    w, h = 1920, 1080
    img = bk.vertical_gradient((w, h), bk.BG_TOP, bk.BG_BOTTOM).convert("RGBA")
    # Subtle warm glow only behind the action band (don't wash the teal).
    glow = bk.radial_glow((w, h), (w // 2, int(h * 0.36)), int(h * 0.30),
                          bk.EMBER["orange"], max_alpha=70)
    img.alpha_composite(glow)
    # Core-loop scene (squad fires up through a ×2 gate at an enemy) up top.
    scene_h = int(h * 0.64)
    scene_w = int(scene_h * 0.82)
    sx = (w - scene_w) // 2
    bk.draw_logo_glyph(img, (sx, int(h * 0.02), sx + scene_w, int(h * 0.02) + scene_h),
                       squad_n=6)
    # Wordmark + tagline below.
    d = ImageDraw.Draw(img)
    wm_font = bk.load_font(int(h * 0.11))
    wm_w = d.textlength("Swellfire", font=wm_font)
    wm_x, wm_y = (w - wm_w) / 2, int(h * 0.74)
    # drop shadow for legibility on the bright teal
    d.text((wm_x + 4, wm_y + 4), "Swellfire", font=wm_font,
           fill=(4, 20, 24, 200), anchor="lm")
    bk.draw_wordmark(d, (wm_x, wm_y), wm_font, anchor="lm")
    tag_font = bk.load_font(int(h * 0.040))
    d.text((w / 2 + 2, int(h * 0.86) + 2), "Grow your squad. Open fire.",
           font=tag_font, fill=(4, 20, 24, 200), anchor="mm")
    d.text((w / 2, int(h * 0.86)), "Grow your squad. Open fire.",
           font=tag_font, fill=bk.EMBER["white"], anchor="mm")
    return img


def main():
    os.makedirs(MEDIA, exist_ok=True)
    icon = make_icon()
    presplash = make_presplash()
    icon.save(os.path.join(ROOT, "icon.png"))
    presplash.convert("RGB").save(os.path.join(ROOT, "presplash.png"))
    shutil.copy(os.path.join(ROOT, "icon.png"), os.path.join(MEDIA, "icon.png"))
    shutil.copy(os.path.join(ROOT, "presplash.png"), os.path.join(MEDIA, "presplash.png"))
    print("wrote icon.png, presplash.png, and swellfire_media/ copies")


if __name__ == "__main__":
    main()
