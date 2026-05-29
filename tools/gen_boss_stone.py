"""Generate desaturated "stone" twins of the per-world boss sprites.

The boss uses the world's main enemy PNG (`assets/sprites/enemy_w{N}.png`,
see `game._spawn_boss`). The monster-health effect recolors the depleted
top slice of the body to lifeless grey "stone" by overdrawing that slice
with a greyscale copy of the same sprite. A Kivy `Color` multiply can only
*darken* a colored texture, not desaturate it, so we bake a real grey twin
here:

    enemy_w{N}.png  →  enemy_w{N}_stone.png   (N = 1..6)

Each twin is the source sprite with its RGB flattened to luminance and biased
slightly toward a cool stone grey, with the **alpha channel preserved** so the
silhouette stays intact (transparent stays transparent).

Run once and commit the twins:

    venv/bin/python tools/gen_boss_stone.py
"""

from __future__ import annotations

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, "assets", "sprites")

WORLDS = range(1, 7)

# Pull the luminance toward a cool stone grey rather than pure neutral, and
# compress the range a touch so the dead part reads as flat/lifeless next to
# the living, saturated body.
# TRUE neutral grey (R=G=B, no hue) in a LIGHT, compressed band. The monster
# cross-fades to this as it dies, so the petrified state must read clearly
# against the game's DARK background — hence a pale, bright grey rather than a
# dark one (dark grey camouflages against the dark stage). Only `lum`
# modulates the value, to keep a little form.
STONE_FLOOR = 0.60                # darkest the stone gets (0..1)
STONE_CEIL = 0.82                 # brightest the stone gets (0..1)


def _to_stone(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    opx = out.load()
    span = STONE_CEIL - STONE_FLOOR
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue  # keep the silhouette's transparent pixels
            # Rec.601 luminance, compressed into [FLOOR, CEIL], emitted as a
            # neutral grey (R=G=B) — no hue at all.
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            v = int(max(0, min(255, (STONE_FLOOR + lum * span) * 255)))
            opx[x, y] = (v, v, v, a)
    return out


def main() -> None:
    made = 0
    for n in WORLDS:
        src = os.path.join(SPRITES, "enemy_w{}.png".format(n))
        if not os.path.exists(src):
            print("skip (missing):", src)
            continue
        dst = os.path.join(SPRITES, "enemy_w{}_stone.png".format(n))
        _to_stone(Image.open(src)).save(dst)
        print("wrote", dst)
        made += 1
    print("done — {} stone twin(s)".format(made))


if __name__ == "__main__":
    main()
