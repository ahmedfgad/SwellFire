"""Google Play feature graphic (1024x500) from the hand-authored cover art.

The user supplied a logo, presplash, and YouTube cover but no feature graphic,
so we derive one from the cover (same style): center-crop it to the 1024:500
aspect ratio, then resize. Run: `venv/bin/python tools/make_feature_graphic.py`
"""

import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_SRC = os.path.join(ROOT, "swellfire_media", "re", "swellfire_youtube_cover.png")
FALLBACK_SRC = os.path.join(ROOT, "swellfire_media", "youtube_thumbnail_1280x720.png")
SRC = RAW_SRC if os.path.exists(RAW_SRC) else FALLBACK_SRC
OUT = os.path.join(ROOT, "swellfire_media", "feature_graphic_1024x500.png")
TARGET = (1024, 500)


def make():
    im = Image.open(SRC).convert("RGB")
    w, h = im.size
    target_ratio = TARGET[0] / TARGET[1]
    if w / h > target_ratio:                 # too wide -> crop width
        nw = int(round(h * target_ratio))
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:                                     # too tall -> crop height
        nh = int(round(w / target_ratio))
        y = (h - nh) // 2
        im = im.crop((0, y, w, y + nh))
    return im.resize(TARGET, Image.LANCZOS)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    make().save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
