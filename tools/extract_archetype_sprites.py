"""Extract one sprite per archetype per world from the CraftPix packs.

Some source packs (W1 forest folder 3, W3 industrial) ship sheets whose
sprites are tiny figures embedded in a wide transparent strip. The
default bbox crop turns those into a thin line that resizes to a black
bar. To work around this we provide a ``hue_shift`` overlay so the same
pair of working sprites can produce 5 visually-distinct archetypes per
world without depending on a broken extraction pipeline.

Each world gets 5 PNGs at 64x64 in ``assets/sprites/``:
    enemy_w{N}_grunt.png
    enemy_w{N}_swarmer.png
    enemy_w{N}_tank.png
    enemy_w{N}_bomber.png
    enemy_w{N}_splitter.png

The pack-to-archetype mapping is curated below — chosen to match the
visual feel of each archetype:
    grunt     → the world's "standard" enemy
    swarmer   → the smallest / fastest looking creature
    tank      → the biggest / armoured / boss-like creature
    bomber    → something that looks like it explodes
    splitter  → something with multiple parts or a fragmenting shape

Worlds that don't have 5 distinct creatures reuse one of the others.
"""

from __future__ import annotations

import os

from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "assets", "raw")
OUT = os.path.join(ROOT, "assets", "sprites")

TARGET = (64, 64)


def _first_frame(png_path: str, grid_cols: int | None = None) -> Image.Image:
    """Best-effort extraction of the first frame of an animation sheet."""
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    if grid_cols:
        fw = w // grid_cols
        frame = img.crop((0, 0, fw, h))
    elif w > h and w % h == 0:
        # Horizontal strip with square frames.
        frame = img.crop((0, 0, h, h))
    elif w == h:
        frame = img
    else:
        frame = img
    bbox = frame.getbbox()
    if bbox:
        frame = frame.crop(bbox)
    return frame


def _fit(img: Image.Image, target=TARGET) -> Image.Image:
    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    iw, ih = img.size
    scale = min(target[0] / iw, target[1] / ih)
    new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
    img = img.resize(new_size, Image.NEAREST)
    fx = (target[0] - img.size[0]) // 2
    fy = (target[1] - img.size[1]) // 2
    canvas.paste(img, (fx, fy), img)
    return canvas


def _recolor(img: Image.Image, hue_shift_deg: float) -> Image.Image:
    """Rotate the hue channel by ``hue_shift_deg`` (0-360) leaving alpha
    untouched. Used to fake visual variety when the source pack only
    ships two distinct creatures."""
    if hue_shift_deg == 0:
        return img
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    hsv = rgb.convert("HSV")
    h, s, v = hsv.split()
    shift = int(round(hue_shift_deg * 255.0 / 360.0)) % 256
    h = h.point(lambda p: (p + shift) % 256)
    rgb2 = Image.merge("HSV", (h, s, v)).convert("RGB")
    r2, g2, b2 = rgb2.split()
    return Image.merge("RGBA", (r2, g2, b2, a))


def extract(src: str, dest_name: str, grid_cols: int | None = None,
            hue_shift: float = 0.0, scale: float = 1.0) -> None:
    frame = _first_frame(os.path.join(RAW, src), grid_cols=grid_cols)
    if hue_shift:
        frame = _recolor(frame, hue_shift)
    if scale != 1.0:
        w, h = frame.size
        frame = frame.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.NEAREST)
    out = _fit(frame)
    out.save(os.path.join(OUT, dest_name))


# --- Per-world archetype mappings ---------------------------------------

# Each tuple is (grunt, swarmer, tank, bomber, splitter) and each entry
# is a relative path under assets/raw/. ``None`` falls back to ``grunt``.
WORLD_ARCHETYPES = {
    1: {
        # Folder 3 has a busted strip layout (figures lost in transparent
        # gutter), so we synthesize the 5 archetypes from folders 1 and 2
        # by hue-rotating the working sprites.
        "grunt":    "w1_forest/extracted/1/Idle.png",
        "swarmer":  "w1_forest/extracted/2/Idle.png",
        # Tank = folder 2 sprite, large, blood-red tint.
        "tank":     "w1_forest/extracted/2/Idle.png",
        "bomber":   "w1_forest/extracted/2/Idle.png",
        "splitter": "w1_forest/extracted/1/Idle.png",
    },
    2: {
        "grunt":    "w2_desert/extracted/1 Snake/Snake_idle.png",
        "swarmer":  "w2_desert/extracted/2 Hyena/Hyena_idle.png",
        "tank":     "w2_desert/extracted/5 Mummy/Mummy_idle.png",
        "bomber":   "w2_desert/extracted/4 Vulture/Vulture_idle.png",
        "splitter": "w2_desert/extracted/3 Scorpio/Scorpio_idle.png",
    },
    3: {
        # Industrial — earlier the grunt was a soldier silhouette which
        # the player mistook for the hero. Now every W3 archetype is a
        # desert creature, hue-rotated so they don't read as W2 reruns.
        "grunt":    "w2_desert/extracted/5 Mummy/Mummy_idle.png",
        "swarmer":  "w2_desert/extracted/1 Snake/Snake_idle.png",
        "tank":     "w2_desert/extracted/5 Mummy/Mummy_idle.png",
        "bomber":   "w2_desert/extracted/4 Vulture/Vulture_idle.png",
        "splitter": "w2_desert/extracted/3 Scorpio/Scorpio_idle.png",
    },
    4: {
        # RPG monsters pack has 6 distinct fantasy creatures.
        "grunt":    "w4_snow_rpg/extracted/PNG/demon/Attack1.png",
        "swarmer":  "w4_snow_rpg/extracted/PNG/lizard/Attack1.png",
        "tank":     "w4_snow_rpg/extracted/PNG/dragon/Attack1.png",
        "bomber":   "w4_snow_rpg/extracted/PNG/jinn_animation/Attack1.png",
        "splitter": "w4_snow_rpg/extracted/PNG/medusa/Attack1.png",
    },
    5: {
        # Volcano — three slime variants + dragon for the tank.
        "grunt":    "w5_volcano_slime/extracted/PNG/Slime1/Parts/Slime1_Idle_body.png",
        "swarmer":  "w5_volcano_slime/extracted/PNG/Slime2/Parts/Slime2_Idle_body.png",
        "tank":     "w4_snow_rpg/extracted/PNG/dragon/Attack1.png",
        "bomber":   "w4_snow_rpg/extracted/PNG/jinn_animation/Attack1.png",
        "splitter": "w5_volcano_slime/extracted/PNG/Slime3/Parts/Slime3_Idle_body.png",
    },
    6: {
        # Cosmos — fallback to W4 RPG monsters with different mapping.
        "grunt":    "w4_snow_rpg/extracted/PNG/medusa/Attack1.png",
        "swarmer":  "w4_snow_rpg/extracted/PNG/lizard/Attack1.png",
        "tank":     "w4_snow_rpg/extracted/PNG/dragon/Attack1.png",
        "bomber":   "w4_snow_rpg/extracted/PNG/jinn_animation/Attack1.png",
        "splitter": "w4_snow_rpg/extracted/PNG/small_dragon/Attack1.png",
    },
}

# For slime sheets — they're 6x4 grids of 64x64.
SLIME_GRID_PATHS = {
    "Slime1_Idle_body.png", "Slime2_Idle_body.png", "Slime3_Idle_body.png",
}

# For CraftPix soldier — 7 frames of 128x128 (894/128 ≈ 7).
SOLDIER_GRID_PATHS = {"Idle.png"}


def grid_cols_for(src: str) -> int | None:
    # IMPORTANT: SOLDIER_GRID_PATHS only stores basenames, but lots of
    # other packs also ship an ``Idle.png``. Scope the soldier check to
    # the actual ``soldier/`` subtree so we don't accidentally treat the
    # forest grunt's idle strip as a 7-column soldier sheet (which
    # collapsed the swarmer to a blank PNG).
    base = os.path.basename(src)
    if base in SLIME_GRID_PATHS:
        return 6
    if base in SOLDIER_GRID_PATHS and "soldier/" in src.replace(os.sep, "/"):
        return 7
    return None


# Per (world, archetype) -> (hue_shift_deg, scale). Hue rotation gives
# distinct colour variants; scale > 1 reads as a "big/tank" creature.
RECOLOR: dict[tuple[int, str], tuple[float, float]] = {
    (1, "swarmer"):  (210.0, 1.0),  # purple → blue/teal
    (1, "tank"):     (320.0, 1.4),  # purple → red, larger
    (1, "bomber"):   ( 90.0, 1.0),  # purple → yellow/lime
    (1, "splitter"): (170.0, 1.0),  # green  → cyan
    # W3 industrial — mummy and scorpio are reused with hue rotations
    # to keep the archetypes legible at a glance.
    (3, "tank"):     ( 30.0, 1.4),  # mummy tinted warm + scaled up
    (3, "splitter"): (200.0, 1.0),  # scorpio recoloured cool
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for world, mapping in WORLD_ARCHETYPES.items():
        print(f"World {world}:")
        for archetype, src in mapping.items():
            full = os.path.join(RAW, src)
            if not os.path.exists(full):
                print(f"  {archetype}: MISSING {src}")
                continue
            dest = f"enemy_w{world}_{archetype}.png"
            hue, scale = RECOLOR.get((world, archetype), (0.0, 1.0))
            extract(src, dest, grid_cols=grid_cols_for(src),
                    hue_shift=hue, scale=scale)
            print(f"  {archetype}: {dest}"
                  + (f" (hue {hue:.0f}°, scale {scale})" if hue or scale != 1.0 else ""))


if __name__ == "__main__":
    main()
