"""Extract one sprite per archetype per world from the CraftPix packs.

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

from PIL import Image

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


def extract(src: str, dest_name: str, grid_cols: int | None = None) -> None:
    frame = _first_frame(os.path.join(RAW, src), grid_cols=grid_cols)
    out = _fit(frame)
    out.save(os.path.join(OUT, dest_name))


# --- Per-world archetype mappings ---------------------------------------

# Each tuple is (grunt, swarmer, tank, bomber, splitter) and each entry
# is a relative path under assets/raw/. ``None`` falls back to ``grunt``.
WORLD_ARCHETYPES = {
    1: {
        "grunt":    "w1_forest/extracted/1/Idle.png",
        "swarmer":  "w1_forest/extracted/2/Idle.png",
        "tank":     "w1_forest/extracted/3/Idle.png",
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
        # Industrial — use soldier variants + mummy as variety.
        "grunt":    "soldier/extracted/Soldier_3/Idle.png",
        "swarmer":  "w2_desert/extracted/1 Snake/Snake_idle.png",
        "tank":     "w2_desert/extracted/5 Mummy/Mummy_idle.png",
        "bomber":   "w2_desert/extracted/4 Vulture/Vulture_idle.png",
        "splitter": "soldier/extracted/Soldier_2/Idle.png",
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
    base = os.path.basename(src)
    if base in SLIME_GRID_PATHS:
        return 6
    if base in SOLDIER_GRID_PATHS:
        return 7
    return None


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
            extract(src, dest, grid_cols=grid_cols_for(src))
            print(f"  {archetype}: {dest}")


if __name__ == "__main__":
    main()
