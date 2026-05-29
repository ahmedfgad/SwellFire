"""Upscale the 8 phone screenshots (1280x720) to tablet size (1920x1080) with
LANCZOS — same approach as CoinTex. Run: `venv/bin/python tools/upscale_screenshots.py`
"""

import glob
import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "swellfire_media")
DST = os.path.join(SRC, "tablet_screenshots")
TARGET = (1920, 1080)


def main():
    os.makedirs(DST, exist_ok=True)
    srcs = sorted(glob.glob(os.path.join(SRC, "0*_*.png")))
    assert srcs, "no phone screenshots found; run make_screenshots.py first"
    for p in srcs:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        assert abs(w / h - 16 / 9) < 1e-3, "{} is not 16:9".format(p)
        im.resize(TARGET, Image.LANCZOS).save(
            os.path.join(DST, os.path.basename(p)), optimize=True)
    print("wrote", len(srcs), "tablet screenshots to", DST)


if __name__ == "__main__":
    main()
