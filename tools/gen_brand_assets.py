"""Apply the user-provided brand art (icon + presplash) into place.

The launcher/window icon and the presplash are authored by hand and live under
`swellfire_media/re/`. This script resizes/copies them into the canonical
locations the build configs reference:
  - icon.png       (512x512)  at repo root + swellfire_media/
  - presplash.png  (native)   at repo root + swellfire_media/

Re-run: `venv/bin/python tools/gen_brand_assets.py`
"""

import os
import shutil

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "swellfire_media")
RE = os.path.join(MEDIA, "re")

RAW_LOGO_SRC = os.path.join(RE, "swellfire_logo.png")
RAW_PRESPLASH_SRC = os.path.join(RE, "swellfire_presplash.png")
# Clean release clones may omit the optional hand-authored source directory.
# The tracked canonical outputs are lossless fallbacks, so the pipeline remains
# reproducible without inventing or downloading replacement artwork.
LOGO_SRC = RAW_LOGO_SRC if os.path.exists(RAW_LOGO_SRC) else os.path.join(ROOT, "icon.png")
PRESPLASH_SRC = (RAW_PRESPLASH_SRC if os.path.exists(RAW_PRESPLASH_SRC)
                 else os.path.join(ROOT, "presplash.png"))


def make_icon():
    """The app/launcher/window icon: the hand-authored logo, square 512x512."""
    return Image.open(LOGO_SRC).convert("RGBA").resize((512, 512), Image.LANCZOS)


def make_presplash():
    """The splash screen: the hand-authored presplash, at its native size."""
    return Image.open(PRESPLASH_SRC).convert("RGB")


def main():
    os.makedirs(MEDIA, exist_ok=True)
    icon = make_icon()
    presplash = make_presplash()
    icon.save(os.path.join(ROOT, "icon.png"))
    presplash.save(os.path.join(ROOT, "presplash.png"))
    shutil.copy(os.path.join(ROOT, "icon.png"), os.path.join(MEDIA, "icon.png"))
    shutil.copy(os.path.join(ROOT, "presplash.png"), os.path.join(MEDIA, "presplash.png"))
    print("applied icon.png (512x512) + presplash.png from canonical brand art")


if __name__ == "__main__":
    main()
