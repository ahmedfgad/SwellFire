"""Build per-world 256×256 atlases with 5 enemy-archetype slots (M14 final).

Layout (4 cols × 4 rows of 64-px slots):

    [runner_blue] [enemy_grunt] [enemy_swarmer] [enemy_tank]
    [enemy_bomber] [enemy_splitter] [projectile] [particle]
    [coin]         [double_coin]    [.]          [.]
    [.]            [.]              [.]          [.]

Each world's PNG hosts the same layout but the 5 enemy slots come from
the matching ``enemy_w{N}_{archetype}.png`` files produced by
``tools/extract_archetype_sprites.py`` so every world's pool looks
visually distinct AND each archetype within a world looks distinct
too. The hero, opponent and boss sprites still live as standalone
PNGs that ``TextureSprite`` loads directly.
"""

from __future__ import annotations

import json
import os
import shutil

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "assets", "atlases")

FRAME = 64
COLS = 4
ROWS = 4
ATLAS_W = FRAME * COLS    # 256
ATLAS_H = FRAME * ROWS    # 256

# Frame name → (col, row).
SLOTS = {
    "runner_blue":   (0, 0),
    "enemy_grunt":   (1, 0),
    "enemy_swarmer": (2, 0),
    "enemy_tank":    (3, 0),
    "enemy_bomber":  (0, 1),
    "enemy_splitter": (1, 1),
    "projectile":    (2, 1),
    "particle":      (3, 1),
    "coin":          (0, 2),
    "double_coin":   (1, 2),
}

ARCHETYPES = ("grunt", "swarmer", "tank", "bomber", "splitter")


def _paste(atlas, slot, src_png):
    col, row = SLOTS[slot]
    x0, y0 = col * FRAME, row * FRAME
    src = Image.open(src_png).convert("RGBA").resize(
        (FRAME, FRAME), Image.NEAREST,
    )
    atlas.paste(src, (x0, y0), src)


def _draw_static(atlas, slot, kind):
    col, row = SLOTS[slot]
    x0, y0 = col * FRAME, row * FRAME
    d = ImageDraw.Draw(atlas)
    if kind == "projectile":
        # Bright tracer round — was rendering too dim on Industrial /
        # Cosmos backgrounds. The white core + bright orange halo makes
        # the shot pop against any background.
        d.ellipse((x0 + 16, y0 + 16, x0 + 48, y0 + 48),
                  fill=(255, 180, 30, 255),
                  outline=(255, 80, 0, 255), width=3)
        d.ellipse((x0 + 22, y0 + 22, x0 + 42, y0 + 42),
                  fill=(255, 230, 120, 255))
        d.ellipse((x0 + 26, y0 + 26, x0 + 38, y0 + 38),
                  fill=(255, 255, 255, 255))
    elif kind == "particle":
        d.ellipse((x0 + 14, y0 + 14, x0 + 50, y0 + 50),
                  fill=(255, 255, 255, 240))
    elif kind == "coin":
        d.ellipse((x0 + 8, y0 + 8, x0 + 56, y0 + 56),
                  fill=(255, 200, 60, 255),
                  outline=(180, 120, 20, 255), width=2)
        d.ellipse((x0 + 18, y0 + 18, x0 + 46, y0 + 46),
                  fill=(255, 220, 100, 255),
                  outline=(180, 120, 20, 200), width=1)
    elif kind == "double_coin":
        d.ellipse((x0 + 6, y0 + 14, x0 + 54, y0 + 62),
                  fill=(255, 200, 60, 255),
                  outline=(180, 120, 20, 255), width=2)
        d.ellipse((x0 + 4, y0 + 4, x0 + 52, y0 + 52),
                  fill=(255, 230, 120, 255),
                  outline=(180, 120, 20, 255), width=2)
        d.ellipse((x0 + 34, y0 + 34, x0 + 60, y0 + 60),
                  fill=(220, 60, 170, 255),
                  outline=(80, 20, 60, 255), width=2)


def build_world(world: int) -> tuple[str, str]:
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))

    # Runner slot — used by the squad-follower pool. Same soldier as the
    # hero so the formation reads as a squad of soldiers.
    runner_src = os.path.join(SPRITES, "hero_blue.png")
    if os.path.exists(runner_src):
        _paste(atlas, "runner_blue", runner_src)

    # Per-archetype enemies — one PNG per archetype per world.
    for archetype in ARCHETYPES:
        slot = f"enemy_{archetype}"
        png = os.path.join(SPRITES, f"enemy_w{world}_{archetype}.png")
        if os.path.exists(png):
            _paste(atlas, slot, png)
        else:
            # Fallback to W1 grunt if a specific archetype PNG is missing.
            fallback = os.path.join(SPRITES, "enemy_w1_grunt.png")
            if os.path.exists(fallback):
                _paste(atlas, slot, fallback)

    _draw_static(atlas, "projectile",  "projectile")
    _draw_static(atlas, "particle",    "particle")
    _draw_static(atlas, "coin",        "coin")
    _draw_static(atlas, "double_coin", "double_coin")

    png_path = os.path.join(OUT, f"world{world}.png")
    json_path = os.path.join(OUT, f"world{world}.json")
    atlas.save(png_path)

    frames = {}
    for name, (c, r) in SLOTS.items():
        frames[name] = {
            "x": c * FRAME, "y": r * FRAME,
            "w": FRAME, "h": FRAME,
        }
    # Backwards-compat alias for the old generic enemy frame.
    frames["enemy_red"] = dict(frames["enemy_grunt"])

    with open(json_path, "w") as f:
        json.dump({
            "atlas_width": ATLAS_W,
            "atlas_height": ATLAS_H,
            "frames": frames,
        }, f, indent=2)
    return png_path, json_path


def main():
    os.makedirs(OUT, exist_ok=True)
    for w in range(1, 7):
        png, json_path = build_world(w)
        print(f"World {w}: {os.path.basename(png)}")
    # Sync default ``stress.*`` to world 1 so legacy paths still work.
    shutil.copy(os.path.join(OUT, "world1.png"),
                os.path.join(OUT, "stress.png"))
    shutil.copy(os.path.join(OUT, "world1.json"),
                os.path.join(OUT, "stress.json"))
    print("Default stress.* synced to world1.")


if __name__ == "__main__":
    main()
