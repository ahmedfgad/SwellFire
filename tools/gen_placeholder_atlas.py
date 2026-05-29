"""Generate the GateRunner sprite atlas (M14 asset pass).

Writes `assets/atlases/stress.png` (a 256x256 PNG holding ten 64x64
frames) and `assets/atlases/stress.json` (the frame -> UV-rect map the
SpriteAtlas loader reads).

Frame layout in the PNG (4 cols x 4 rows = 16 slots, 10 used):

    +-----------+-----------+-----------+-----------+
    | runner_   | enemy_    | enemy_    | enemy_    |
    | blue      | grunt     | swarmer   | tank      |
    +-----------+-----------+-----------+-----------+
    | enemy_    | enemy_    | project-  | particle  |
    | bomber    | splitter  | ile       |           |
    +-----------+-----------+-----------+-----------+
    | coin      | double_   |           |           |
    |           | coin      |           |           |
    +-----------+-----------+-----------+-----------+
    |           |           |           |           |
    |           |           |           |           |
    +-----------+-----------+-----------+-----------+

Each frame is rendered with 4x oversampling + LANCZOS downsample so
even procedural art reads as polished. The M14 pass swapped the
original four placeholder shapes for ten frames with per-archetype
enemy silhouettes + coin + double-coin pickups + a more detailed
runner.

Backwards-compat: ``enemy_red`` is left in the JSON as an alias for
``enemy_grunt`` so any callers that still reference the old name keep
working until they're migrated.
"""

from __future__ import annotations

import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFilter

FRAME_SIZE = 64
COLS, ROWS = 4, 4
ATLAS_SIZE = FRAME_SIZE * COLS    # 256

# 4x oversampling for anti-aliased edges via LANCZOS downsample.
SS = 4
SF = FRAME_SIZE * SS


def _new_canvas() -> Image.Image:
    return Image.new("RGBA", (SF, SF), (0, 0, 0, 0))


def _downsample(img: Image.Image) -> Image.Image:
    return img.resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS)


def _outline_w(scale: float = 1.0) -> int:
    return max(2, int(SS * 0.5 * scale))


# --- frame painters --------------------------------------------------------

def _runner_blue() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    pad = SF * 0.10
    # Body — rounded blue capsule.
    d.rounded_rectangle(
        (pad, SF * 0.34, SF - pad, SF * 0.88),
        radius=int(SF * 0.18),
        fill=(60, 160, 240, 255),
        outline=(20, 50, 90, 220), width=_outline_w(),
    )
    # Chest highlight.
    d.rounded_rectangle(
        (SF * 0.20, SF * 0.40, SF * 0.80, SF * 0.55),
        radius=int(SF * 0.10),
        fill=(120, 200, 255, 200),
    )
    # Head — skin tone with hair tuft.
    head_box = (SF * 0.30, SF * 0.06, SF * 0.70, SF * 0.46)
    d.ellipse(head_box, fill=(250, 218, 175, 255),
              outline=(80, 50, 30, 220), width=_outline_w())
    # Hair (top half).
    d.pieslice(head_box, start=200, end=340, fill=(80, 50, 30, 255))
    # Eyes.
    d.ellipse((SF * 0.37, SF * 0.22, SF * 0.43, SF * 0.28),
              fill=(20, 20, 20, 255))
    d.ellipse((SF * 0.57, SF * 0.22, SF * 0.63, SF * 0.28),
              fill=(20, 20, 20, 255))
    # Gun barrel (dark) — points right.
    d.rounded_rectangle(
        (SF * 0.58, SF * 0.58, SF * 0.96, SF * 0.70),
        radius=int(SF * 0.04),
        fill=(40, 40, 50, 255),
    )
    d.rectangle(
        (SF * 0.86, SF * 0.62, SF * 0.96, SF * 0.66),
        fill=(140, 140, 150, 255),
    )
    return _downsample(img)


def _enemy_grunt() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    pad = SF * 0.10
    d.rounded_rectangle(
        (pad, pad, SF - pad, SF - pad),
        radius=int(SF * 0.20),
        fill=(210, 60, 70, 255),
        outline=(70, 10, 20, 220), width=_outline_w(),
    )
    # Top highlight.
    d.ellipse((SF * 0.20, SF * 0.15, SF * 0.55, SF * 0.30),
              fill=(255, 130, 130, 180))
    # Eyes.
    for ex in (0.24, 0.60):
        d.ellipse((SF * ex, SF * 0.34, SF * (ex + 0.16), SF * 0.50),
                  fill=(255, 255, 255, 255))
    d.ellipse((SF * 0.30, SF * 0.40, SF * 0.36, SF * 0.46),
              fill=(30, 30, 30, 255))
    d.ellipse((SF * 0.66, SF * 0.40, SF * 0.72, SF * 0.46),
              fill=(30, 30, 30, 255))
    # Mouth.
    d.rounded_rectangle(
        (SF * 0.30, SF * 0.62, SF * 0.70, SF * 0.78),
        radius=int(SF * 0.05),
        fill=(60, 10, 20, 255),
    )
    # Two fangs.
    d.polygon([
        (SF * 0.36, SF * 0.62), (SF * 0.42, SF * 0.62), (SF * 0.39, SF * 0.72)
    ], fill=(255, 255, 255, 255))
    d.polygon([
        (SF * 0.58, SF * 0.62), (SF * 0.64, SF * 0.62), (SF * 0.61, SF * 0.72)
    ], fill=(255, 255, 255, 255))
    return _downsample(img)


def _enemy_swarmer() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = SF / 2, SF / 2
    # Magenta diamond for "fast" silhouette.
    body = [
        (cx, SF * 0.18),
        (SF * 0.86, cy),
        (cx, SF * 0.82),
        (SF * 0.14, cy),
    ]
    d.polygon(body, fill=(180, 70, 200, 255),
              outline=(40, 10, 50, 220))
    # Inner light.
    d.polygon([
        (cx, SF * 0.25),
        (SF * 0.70, cy),
        (cx, SF * 0.55),
        (SF * 0.30, cy),
    ], fill=(220, 130, 230, 200))
    # Single big eye.
    d.ellipse((SF * 0.36, SF * 0.40, SF * 0.64, SF * 0.62),
              fill=(255, 255, 255, 255),
              outline=(40, 10, 50, 230), width=_outline_w())
    d.ellipse((SF * 0.44, SF * 0.46, SF * 0.56, SF * 0.58),
              fill=(40, 10, 50, 255))
    return _downsample(img)


def _enemy_tank() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    pad = SF * 0.06
    # Big armored body.
    d.rounded_rectangle(
        (pad, pad, SF - pad, SF - pad),
        radius=int(SF * 0.14),
        fill=(95, 100, 115, 255),
        outline=(30, 30, 40, 230), width=_outline_w(scale=1.2),
    )
    # Top plate (lighter).
    d.rounded_rectangle(
        (pad, pad, SF - pad, SF * 0.42),
        radius=int(SF * 0.12),
        fill=(135, 140, 155, 255),
    )
    # Rivets.
    for fx, fy in [(0.18, 0.18), (0.50, 0.14), (0.82, 0.18),
                   (0.18, 0.84), (0.50, 0.88), (0.82, 0.84)]:
        d.ellipse(
            (SF * fx - SF * 0.04, SF * fy - SF * 0.04,
             SF * fx + SF * 0.04, SF * fy + SF * 0.04),
            fill=(50, 55, 65, 255),
            outline=(25, 25, 30, 255), width=max(1, SS // 3),
        )
    # Red visor.
    d.rounded_rectangle(
        (SF * 0.20, SF * 0.48, SF * 0.80, SF * 0.62),
        radius=int(SF * 0.04),
        fill=(220, 40, 50, 255),
        outline=(60, 10, 10, 255), width=_outline_w(),
    )
    d.rounded_rectangle(
        (SF * 0.24, SF * 0.50, SF * 0.40, SF * 0.55),
        radius=int(SF * 0.02),
        fill=(255, 180, 180, 220),
    )
    return _downsample(img)


def _enemy_bomber() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = SF / 2, SF * 0.58
    r = SF * 0.36
    d.ellipse(
        (cx - r, cy - r, cx + r, cy + r),
        fill=(30, 30, 40, 255),
        outline=(0, 0, 0, 230), width=_outline_w(),
    )
    # Specular.
    d.ellipse(
        (cx - r * 0.7, cy - r * 0.8, cx - r * 0.2, cy - r * 0.4),
        fill=(110, 110, 130, 180),
    )
    # Red eyes.
    d.ellipse(
        (SF * 0.28, SF * 0.46, SF * 0.42, SF * 0.58),
        fill=(255, 70, 70, 255),
    )
    d.ellipse(
        (SF * 0.58, SF * 0.46, SF * 0.72, SF * 0.58),
        fill=(255, 70, 70, 255),
    )
    # Fuse + spark.
    d.rectangle(
        (SF * 0.44, SF * 0.06, SF * 0.56, SF * 0.22),
        fill=(140, 90, 40, 255),
    )
    d.ellipse(
        (SF * 0.36, SF * 0.0, SF * 0.64, SF * 0.16),
        fill=(255, 220, 60, 255),
        outline=(255, 130, 30, 255), width=_outline_w(),
    )
    return _downsample(img)


def _enemy_splitter() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    pad = SF * 0.10
    cx = SF / 2
    # Left half (teal).
    d.pieslice(
        (pad, pad, SF - pad, SF - pad),
        start=90, end=270,
        fill=(50, 170, 160, 255),
        outline=(20, 60, 60, 220), width=_outline_w(),
    )
    # Right half (yellow).
    d.pieslice(
        (pad, pad, SF - pad, SF - pad),
        start=270, end=450,
        fill=(245, 200, 60, 255),
        outline=(120, 80, 20, 220), width=_outline_w(),
    )
    # Seam down the middle.
    d.rectangle(
        (cx - SF * 0.02, pad, cx + SF * 0.02, SF - pad),
        fill=(20, 20, 30, 220),
    )
    # Eyes.
    d.ellipse(
        (SF * 0.22, SF * 0.36, SF * 0.40, SF * 0.54),
        fill=(255, 255, 255, 255),
        outline=(20, 20, 30, 230), width=_outline_w(),
    )
    d.ellipse(
        (SF * 0.60, SF * 0.36, SF * 0.78, SF * 0.54),
        fill=(255, 255, 255, 255),
        outline=(20, 20, 30, 230), width=_outline_w(),
    )
    d.ellipse((SF * 0.28, SF * 0.42, SF * 0.34, SF * 0.48),
              fill=(20, 20, 30, 255))
    d.ellipse((SF * 0.66, SF * 0.42, SF * 0.72, SF * 0.48),
              fill=(20, 20, 30, 255))
    return _downsample(img)


def _projectile() -> Image.Image:
    img = _new_canvas()
    # Soft glow halo behind the bullet.
    halo = Image.new("RGBA", (SF, SF), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((SF * 0.18, SF * 0.18, SF * 0.82, SF * 0.82),
               fill=(255, 220, 80, 130))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=SF * 0.06))
    img.alpha_composite(halo)
    # Bullet capsule.
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (SF * 0.35, SF * 0.10, SF * 0.65, SF * 0.90),
        radius=int(SF * 0.14),
        fill=(255, 220, 80, 255),
        outline=(255, 140, 30, 255), width=_outline_w(),
    )
    # Bright tip.
    d.ellipse(
        (SF * 0.36, SF * 0.08, SF * 0.64, SF * 0.34),
        fill=(255, 250, 200, 255),
    )
    return _downsample(img)


def _particle() -> Image.Image:
    img = _new_canvas()
    # Soft halo.
    halo = Image.new("RGBA", (SF, SF), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((SF * 0.08, SF * 0.08, SF * 0.92, SF * 0.92),
               fill=(255, 255, 255, 150))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=SF * 0.04))
    img.alpha_composite(halo)
    d = ImageDraw.Draw(img)
    d.ellipse((SF * 0.30, SF * 0.30, SF * 0.70, SF * 0.70),
              fill=(255, 255, 255, 255))
    return _downsample(img)


def _coin() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    # Outer gold ring.
    d.ellipse(
        (SF * 0.10, SF * 0.10, SF * 0.90, SF * 0.90),
        fill=(255, 200, 60, 255),
        outline=(180, 120, 20, 255), width=_outline_w(scale=1.3),
    )
    # Inner ring.
    d.ellipse(
        (SF * 0.22, SF * 0.22, SF * 0.78, SF * 0.78),
        fill=(255, 220, 100, 255),
        outline=(180, 120, 20, 220), width=_outline_w(),
    )
    # "C"-shaped arc.
    d.arc(
        (SF * 0.30, SF * 0.30, SF * 0.70, SF * 0.70),
        start=40, end=320,
        fill=(120, 70, 10, 255), width=_outline_w(scale=1.5),
    )
    # Specular highlight.
    halo = Image.new("RGBA", (SF, SF), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((SF * 0.20, SF * 0.20, SF * 0.45, SF * 0.45),
               fill=(255, 255, 220, 230))
    halo = halo.filter(ImageFilter.GaussianBlur(radius=SF * 0.05))
    img.alpha_composite(halo)
    return _downsample(img)


def _double_coin() -> Image.Image:
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    # Lower (back) coin.
    d.ellipse(
        (SF * 0.10, SF * 0.20, SF * 0.90, SF * 1.00),
        fill=(255, 200, 60, 255),
        outline=(180, 120, 20, 255), width=_outline_w(scale=1.3),
    )
    # Front coin (offset up + lighter).
    d.ellipse(
        (SF * 0.05, SF * 0.05, SF * 0.85, SF * 0.85),
        fill=(255, 230, 120, 255),
        outline=(180, 120, 20, 255), width=_outline_w(scale=1.3),
    )
    # Magenta "x2" badge on the bottom-right.
    d.ellipse(
        (SF * 0.55, SF * 0.55, SF * 0.98, SF * 0.98),
        fill=(220, 60, 170, 255),
        outline=(80, 20, 60, 255), width=_outline_w(),
    )
    # Stylised "2" inside the badge (rectangles arranged like a 7-seg "2").
    for bbox in [
        (SF * 0.66, SF * 0.66, SF * 0.86, SF * 0.72),  # top
        (SF * 0.78, SF * 0.72, SF * 0.86, SF * 0.80),  # upper right
        (SF * 0.66, SF * 0.78, SF * 0.86, SF * 0.84),  # middle
        (SF * 0.66, SF * 0.80, SF * 0.74, SF * 0.86),  # lower left
        (SF * 0.66, SF * 0.86, SF * 0.86, SF * 0.92),  # bottom
    ]:
        d.rounded_rectangle(bbox, radius=int(SF * 0.02),
                            fill=(255, 255, 255, 255))
    return _downsample(img)


# --- atlas assembly --------------------------------------------------------

FRAMES = [
    # (slot_col, slot_row, name, painter)
    (0, 0, "runner_blue",   _runner_blue),
    (1, 0, "enemy_grunt",   _enemy_grunt),
    (2, 0, "enemy_swarmer", _enemy_swarmer),
    (3, 0, "enemy_tank",    _enemy_tank),
    (0, 1, "enemy_bomber",  _enemy_bomber),
    (1, 1, "enemy_splitter", _enemy_splitter),
    (2, 1, "projectile",    _projectile),
    (3, 1, "particle",      _particle),
    (0, 2, "coin",          _coin),
    (1, 2, "double_coin",   _double_coin),
]

# Backwards-compat alias for the old generic enemy frame.
ALIASES = {
    "enemy_red": "enemy_grunt",
}


def build(out_dir: str) -> None:
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    # SpriteAtlas loader (graphics.py) expects pixel-space {x, y, w, h}
    # with y=0 at the TOP of the PNG; it flips the Y axis internally
    # for the GL UV coordinates.
    frame_map: dict[str, dict[str, int]] = {}
    for col, row, name, painter in FRAMES:
        x0 = col * FRAME_SIZE
        y0 = row * FRAME_SIZE
        frame_img = painter()
        atlas.paste(frame_img, (x0, y0), frame_img)
        frame_map[name] = {
            "x": x0,
            "y": y0,
            "w": FRAME_SIZE,
            "h": FRAME_SIZE,
        }
    for alias, target in ALIASES.items():
        if target in frame_map:
            frame_map[alias] = dict(frame_map[target])

    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "stress.png")
    json_path = os.path.join(out_dir, "stress.json")
    atlas.save(png_path)
    with open(json_path, "w") as f:
        json.dump({
            "atlas_width": ATLAS_SIZE,
            "atlas_height": ATLAS_SIZE,
            "frames": frame_map,
        }, f, indent=2)
    print("Wrote", png_path)
    print("Wrote", json_path)
    print("Frames:", sorted(frame_map.keys()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/atlases",
                    help="Output directory for the atlas PNG + JSON")
    args = ap.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
