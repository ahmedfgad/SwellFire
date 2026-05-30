"""Ember title-card frames (from the hand-authored logo) and lower-third labels
for the Swellfire videos. Pure PIL."""

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGO = os.path.join(ROOT, "swellfire_media", "re", "swellfire_logo.png")
BG = (18, 20, 16)            # dark ember to match the logo art
GOLD = (255, 214, 120)

_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(size):
    for p in _FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def make_card(size, caption=None):
    """A held title card: the logo centered on a dark ember field + caption."""
    w, h = size
    img = Image.new("RGB", size, BG)
    logo = Image.open(LOGO).convert("RGBA")
    lw = int(w * 0.9)
    scale = lw / logo.width
    logo = logo.resize((lw, int(logo.height * scale)), Image.LANCZOS)
    img.paste(logo, ((w - lw) // 2, int(h * 0.28)), logo)
    if caption:
        d = ImageDraw.Draw(img)
        d.text((w / 2, int(h * 0.66)), caption, font=_font(int(h * 0.030)),
               fill=GOLD, anchor="mm")
    return img


def card_frames(out_dir, seconds, fps, size, caption=None):
    """Write a held title card as a frame sequence f%05d.png. Returns frame count."""
    os.makedirs(out_dir, exist_ok=True)
    frame = make_card(size, caption)
    n = max(1, int(seconds * fps))
    for i in range(n):
        frame.save(os.path.join(out_dir, "f%05d.png" % i))
    return n


def overlay_lower_third(frame_path, text):
    """Burn a lower-third label bar onto an existing frame PNG (in place)."""
    im = Image.open(frame_path).convert("RGBA")
    w, h = im.size
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    bh = int(h * 0.058)
    y = int(h * 0.905)
    d.rounded_rectangle((int(w * 0.04), y, int(w * 0.96), y + bh),
                        radius=int(bh * 0.35), fill=(12, 14, 10, 210))
    d.text((w / 2, y + bh / 2), text, font=_font(int(h * 0.030)),
           fill=GOLD, anchor="mm")
    Image.alpha_composite(im, ov).convert("RGB").save(frame_path)
