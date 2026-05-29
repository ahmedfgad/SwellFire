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
    # Rounded-square ember background.
    bg = bk.vertical_gradient((size, size), bk.EMBER["red"], bk.EMBER["ember_black"])
    bg = bg.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1),
                                           radius=int(size * 0.22), fill=255)
    img.paste(bg, (0, 0), mask)
    # Glyph centered.
    bk.draw_logo_glyph(img, (int(size * 0.16), int(size * 0.10),
                             int(size * 0.84), int(size * 0.90)))
    return img


def make_presplash():
    w, h = 1920, 1080
    img = bk.vertical_gradient((w, h), bk.EMBER["blood"], bk.EMBER["ember_black"]).convert("RGBA")
    glow = bk.radial_glow((w, h), (w // 2, int(h * 0.42)), int(h * 0.5),
                          bk.EMBER["orange"], max_alpha=120)
    img.alpha_composite(glow)
    # Glyph above center.
    gh = int(h * 0.52)
    gw = gh
    gx = (w - gw) // 2
    bk.draw_logo_glyph(img, (gx, int(h * 0.06), gx + gw, int(h * 0.06) + gh))
    # Wordmark + tagline below.
    d = ImageDraw.Draw(img)
    wm_font = bk.load_font(int(h * 0.11))
    wm_w = d.textlength("Swellfire", font=wm_font)
    bk.draw_wordmark(d, ((w - wm_w) / 2, int(h * 0.74)), wm_font, anchor="lm")
    tag_font = bk.load_font(int(h * 0.040))
    d.text((w / 2, int(h * 0.86)), "Grow your squad. Open fire.",
           font=tag_font, fill=bk.EMBER["cream"], anchor="mm")
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
