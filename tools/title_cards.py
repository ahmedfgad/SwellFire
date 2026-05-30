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
    """A held title card: the logo on a field matched to its own background
    (so it blends seamlessly), with an auto-fitted caption below it."""
    w, h = size
    logo = Image.open(LOGO).convert("RGBA")
    bg = logo.getpixel((4, 4))[:3]          # blend the field to the logo's corner
    img = Image.new("RGB", size, bg)
    lw = int(w * 0.84)
    scale = lw / logo.width
    lh = int(logo.height * scale)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    ly = int(h * 0.22)
    img.paste(logo, ((w - lw) // 2, ly), logo)
    if caption:
        d = ImageDraw.Draw(img)
        fs = int(h * 0.030)                  # shrink until it fits the width
        while fs > 16 and d.textlength(caption, font=_font(fs)) > 0.92 * w:
            fs -= 2
        f = _font(fs)
        cy = ly + lh + int(h * 0.045)
        d.text((w / 2 + 2, cy + 2), caption, font=f, fill=(0, 0, 0), anchor="mm")
        d.text((w / 2, cy), caption, font=f, fill=GOLD, anchor="mm")
    return img


def card_frames(out_dir, seconds, fps, size, caption=None):
    """Write a held title card as a frame sequence f%05d.png. Returns frame count."""
    os.makedirs(out_dir, exist_ok=True)
    frame = make_card(size, caption)
    n = max(1, int(seconds * fps))
    for i in range(n):
        frame.save(os.path.join(out_dir, "f%05d.png" % i))
    return n


def overlay_caption(frame_path, text, y_frac=0.10):
    """Burn a big bold caption (with shadow) near the top of a frame (in place)."""
    im = Image.open(frame_path).convert("RGB")
    w, h = im.size
    d = ImageDraw.Draw(im)
    f = _font(int(h * 0.045))
    y = int(h * y_frac)
    d.text((w / 2 + 3, y + 3), text, font=f, fill=(0, 0, 0), anchor="mm")
    d.text((w / 2, y), text, font=f, fill=GOLD, anchor="mm")
    im.save(frame_path)


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
