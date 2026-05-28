"""Generate a placeholder sprite atlas for the M3 rendering POC.

Writes `assets/atlases/stress.png` (a single 128x128 PNG holding four 64x64
frames) and `assets/atlases/stress.json` (the frame -> UV-rect map the
SpriteAtlas loader reads).

Frame layout in the PNG:

    +-------+-------+
    |       |       |
    |  blue |  red  |
    | runner| enemy |
    +-------+-------+
    |       |       |
    |proj   |particle
    | (gold)| (white)
    +-------+-------+

Each frame is a simple rounded shape; the M14 asset pass replaces this with
real character art. Re-run any time to refresh.
"""

from __future__ import annotations

import argparse
import json
import os

from PIL import Image, ImageDraw

FRAME_SIZE = 64
ATLAS_SIZE = 128     # 2 columns x 2 rows of FRAME_SIZE frames


def _make_frame(kind: str) -> Image.Image:
    img = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 6

    if kind == "runner_blue":
        d.rounded_rectangle((margin, margin, FRAME_SIZE - margin, FRAME_SIZE - margin),
                            radius=12, fill=(60, 160, 240, 255))
        # head
        d.ellipse((FRAME_SIZE * 0.32, FRAME_SIZE * 0.10,
                   FRAME_SIZE * 0.68, FRAME_SIZE * 0.46),
                  fill=(252, 220, 178, 255))
        # gun barrel
        d.rectangle((FRAME_SIZE * 0.58, FRAME_SIZE * 0.46,
                     FRAME_SIZE * 0.92, FRAME_SIZE * 0.56),
                    fill=(40, 40, 50, 255))

    elif kind == "enemy_red":
        d.rounded_rectangle((margin, margin, FRAME_SIZE - margin, FRAME_SIZE - margin),
                            radius=12, fill=(210, 60, 70, 255))
        # eyes
        d.ellipse((FRAME_SIZE * 0.26, FRAME_SIZE * 0.36,
                   FRAME_SIZE * 0.38, FRAME_SIZE * 0.48),
                  fill=(255, 255, 255, 255))
        d.ellipse((FRAME_SIZE * 0.62, FRAME_SIZE * 0.36,
                   FRAME_SIZE * 0.74, FRAME_SIZE * 0.48),
                  fill=(255, 255, 255, 255))
        # mouth
        d.rectangle((FRAME_SIZE * 0.30, FRAME_SIZE * 0.66,
                     FRAME_SIZE * 0.70, FRAME_SIZE * 0.74),
                    fill=(60, 10, 20, 255))

    elif kind == "projectile":
        d.ellipse((FRAME_SIZE * 0.20, FRAME_SIZE * 0.20,
                   FRAME_SIZE * 0.80, FRAME_SIZE * 0.80),
                  fill=(255, 220, 70, 255), outline=(255, 140, 30, 255), width=3)
        d.ellipse((FRAME_SIZE * 0.34, FRAME_SIZE * 0.34,
                   FRAME_SIZE * 0.66, FRAME_SIZE * 0.66),
                  fill=(255, 255, 200, 255))

    elif kind == "particle":
        d.ellipse((FRAME_SIZE * 0.10, FRAME_SIZE * 0.10,
                   FRAME_SIZE * 0.90, FRAME_SIZE * 0.90),
                  fill=(255, 255, 255, 220))
        d.ellipse((FRAME_SIZE * 0.30, FRAME_SIZE * 0.30,
                   FRAME_SIZE * 0.70, FRAME_SIZE * 0.70),
                  fill=(255, 200, 100, 255))

    else:
        raise ValueError("unknown frame kind: " + kind)

    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="assets/atlases",
                        help="Output atlas directory (default: ./assets/atlases)")
    parser.add_argument("--name", default="stress",
                        help="Atlas base name (default: stress)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Place four frames in a 2x2 grid.
    layout = [
        ("runner_blue", 0, 0),
        ("enemy_red",   1, 0),
        ("projectile",  0, 1),
        ("particle",    1, 1),
    ]
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    frames_meta = {}
    for name, col, row in layout:
        frame = _make_frame(name)
        x = col * FRAME_SIZE
        # PIL origin is top-left, but the SpriteAtlas loader records frames in
        # PIL coordinates and the loader flips to GL (origin bottom-left) at
        # load time. So we record the PIL-space top-left here.
        y = row * FRAME_SIZE
        atlas.paste(frame, (x, y))
        frames_meta[name] = {"x": x, "y": y, "w": FRAME_SIZE, "h": FRAME_SIZE}

    png_path = os.path.join(args.out, args.name + ".png")
    json_path = os.path.join(args.out, args.name + ".json")
    atlas.save(png_path, optimize=True)
    with open(json_path, "w") as f:
        json.dump({
            "atlas_width": ATLAS_SIZE,
            "atlas_height": ATLAS_SIZE,
            "frames": frames_meta,
        }, f, indent=2)
    print("wrote", png_path)
    print("wrote", json_path)


if __name__ == "__main__":
    main()
