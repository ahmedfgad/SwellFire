"""YouTube cover/thumbnail (1280x720) from the hand-authored cover art.

Source: swellfire_media/re/swellfire_youtube_cover.png (16:9), resized to the
1280x720 YouTube thumbnail size. Run: `venv/bin/python tools/make_youtube_thumbnail.py`
"""

import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "swellfire_media", "re", "swellfire_youtube_cover.png")
OUT = os.path.join(ROOT, "swellfire_media", "youtube_thumbnail_1280x720.png")


def make():
    return Image.open(SRC).convert("RGB").resize((1280, 720), Image.LANCZOS)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    make().save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
