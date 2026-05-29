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
    # Simple icon: a single hero avatar on the solid background.
    bk.compose_hero_icon(img, (int(size * 0.10), int(size * 0.10),
                               int(size * 0.90), int(size * 0.90)))
    return img


def make_presplash():
    w, h = 1920, 1080
    img = bk.solid_bg((w, h))
    d = ImageDraw.Draw(img)
    # Title + tagline up top.
    wm_font = bk.load_font(int(h * 0.135))
    wm_w = d.textlength("Swellfire", font=wm_font)
    wm_x, wm_y = (w - wm_w) / 2, int(h * 0.17)
    d.text((wm_x + 5, wm_y + 5), "Swellfire", font=wm_font,
           fill=(4, 30, 30, 200), anchor="lm")
    bk.draw_wordmark(d, (wm_x, wm_y), wm_font, anchor="lm")
    tag_font = bk.load_font(int(h * 0.046))
    d.text((w / 2, int(h * 0.30)), "Grow your squad. Open fire.",
           font=tag_font, fill=bk.EMBER["cream"], anchor="mm")
    # A ×2 gate above the squad; the heroes fire upward beneath it.
    bk.draw_gate_panel(img, w / 2, int(h * 0.52), int(w * 0.34), int(h * 0.10), "×2")
    bk.draw_squad_row(img, w / 2, int(h * 0.965), n=7, hero_h=int(h * 0.20), fire=True)
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
