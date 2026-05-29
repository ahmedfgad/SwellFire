"""Build per-world 128×128 atlases (M14 final).

Each atlas keeps the same 4-frame layout that AtlasSprite/BatchedRenderer
expects (runner_blue, enemy_red, projectile, particle at the 64-px
slots) — the enemy_red slot is swapped per world for the appropriate
CraftPix enemy art so each world's pool feels different.

Hero, opponent and boss are rendered via TextureSprite from their own
per-PNG files in ``assets/sprites/`` so the runner_blue slot here is
unused but kept for compatibility with any code still asking for it.
"""

from __future__ import annotations

import json
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, "assets", "sprites")
OUT = os.path.join(ROOT, "assets", "atlases")

FRAME = 64
ATLAS_W = 128
ATLAS_H = 128

# Frame name → (col, row). Matches the M0 2×2 layout that AtlasSprite
# was designed against — i.e. the layout that actually renders.
SLOTS = {
    "runner_blue": (0, 0),
    "enemy_red":   (1, 0),
    "projectile":  (0, 1),
    "particle":    (1, 1),
}

# Per-world enemy override — one PNG per world dropped in assets/sprites.
# Worlds that don't have a dedicated PNG fall back to the previous
# world's art (so we never have a blank slot during rollout).
WORLD_ENEMY = {
    1: "enemy_w1.png",
    2: "enemy_w2.png",
    3: "enemy_w3.png",
    4: "enemy_w4.png",
    5: "enemy_w5.png",
    6: "enemy_w1.png",   # fallback until we get a cosmos pack
}


def _draw_static_frame(atlas, slot, kind):
    """Paint the projectile or particle frame procedurally — these
    don't change per world."""
    col, row = SLOTS[slot]
    x0, y0 = col * FRAME, row * FRAME
    d = ImageDraw.Draw(atlas)
    if kind == "projectile":
        d.ellipse((x0 + 22, y0 + 8, x0 + 42, y0 + 56),
                  fill=(255, 220, 80, 255),
                  outline=(255, 140, 30, 255), width=2)
        d.ellipse((x0 + 26, y0 + 6, x0 + 38, y0 + 26),
                  fill=(255, 250, 200, 255))
    elif kind == "particle":
        d.ellipse((x0 + 12, y0 + 12, x0 + 52, y0 + 52),
                  fill=(255, 255, 255, 255))


def _paste_into(atlas, slot, src_png):
    col, row = SLOTS[slot]
    x0, y0 = col * FRAME, row * FRAME
    src = Image.open(src_png).convert("RGBA").resize((FRAME, FRAME), Image.NEAREST)
    atlas.paste(src, (x0, y0), src)


def _runner_placeholder(atlas, runner_src=None):
    """The runner_blue slot — used by the SquadController for follower
    sprites. Hero itself draws via TextureSprite, but the followers
    sample from this atlas frame, so we paste the same soldier sprite
    here scaled down to 64×64 so the crowd reads as a squad of
    soldiers instead of a column of blue placeholder squares.
    """
    col, row = SLOTS["runner_blue"]
    x0, y0 = col * FRAME, row * FRAME
    if runner_src and os.path.exists(runner_src):
        src = Image.open(runner_src).convert("RGBA").resize(
            (FRAME, FRAME), Image.NEAREST,
        )
        atlas.paste(src, (x0, y0), src)
    else:
        d = ImageDraw.Draw(atlas)
        d.rounded_rectangle((x0 + 8, y0 + 8, x0 + 56, y0 + 56),
                            radius=10, fill=(60, 160, 240, 255),
                            outline=(20, 50, 90, 220), width=2)


def build_world(world: int) -> tuple[str, str]:
    atlas = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))
    _runner_placeholder(atlas, os.path.join(SPRITES, "hero_blue.png"))
    enemy_png = os.path.join(SPRITES, WORLD_ENEMY[world])
    _paste_into(atlas, "enemy_red", enemy_png)
    _draw_static_frame(atlas, "projectile", "projectile")
    _draw_static_frame(atlas, "particle", "particle")

    png_path = os.path.join(OUT, f"world{world}.png")
    json_path = os.path.join(OUT, f"world{world}.json")
    atlas.save(png_path)

    frames = {}
    # Concrete frame entries — same as M0 placeholder atlas.
    for name, (c, r) in SLOTS.items():
        frames[name] = {"x": c * FRAME, "y": r * FRAME, "w": FRAME, "h": FRAME}
    # All per-archetype + pickup names alias back to base frames so
    # gameplay code can keep using its M14 naming.
    for n in ("enemy_grunt", "enemy_swarmer", "enemy_tank",
              "enemy_bomber", "enemy_splitter"):
        frames[n] = dict(frames["enemy_red"])
    frames["coin"] = dict(frames["projectile"])
    frames["double_coin"] = dict(frames["particle"])

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
    # Also overwrite the default stress.png with world 1 so the existing
    # find_atlas("stress") path keeps loading something sensible.
    import shutil
    shutil.copy(os.path.join(OUT, "world1.png"),
                os.path.join(OUT, "stress.png"))
    shutil.copy(os.path.join(OUT, "world1.json"),
                os.path.join(OUT, "stress.json"))
    print("Default stress.* synced to world1.")


if __name__ == "__main__":
    main()
