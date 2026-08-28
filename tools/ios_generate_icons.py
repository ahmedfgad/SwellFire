#!/usr/bin/env python3
"""Generate a complete, alpha-free iPhone/iPad AppIcon asset catalog."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


SLOTS = [
    ("iphone", "20x20", "2x", 40, "icon-20@2x.png"),
    ("iphone", "20x20", "3x", 60, "icon-20@3x.png"),
    ("iphone", "29x29", "2x", 58, "icon-29@2x.png"),
    ("iphone", "29x29", "3x", 87, "icon-29@3x.png"),
    ("iphone", "40x40", "2x", 80, "icon-40@2x.png"),
    ("iphone", "40x40", "3x", 120, "icon-40@3x.png"),
    ("iphone", "60x60", "2x", 120, "icon-60@2x.png"),
    ("iphone", "60x60", "3x", 180, "icon-60@3x.png"),
    ("ipad", "20x20", "1x", 20, "icon-ipad-20.png"),
    ("ipad", "20x20", "2x", 40, "icon-ipad-20@2x.png"),
    ("ipad", "29x29", "1x", 29, "icon-ipad-29.png"),
    ("ipad", "29x29", "2x", 58, "icon-ipad-29@2x.png"),
    ("ipad", "40x40", "1x", 40, "icon-ipad-40.png"),
    ("ipad", "40x40", "2x", 80, "icon-ipad-40@2x.png"),
    ("ipad", "76x76", "1x", 76, "icon-ipad-76.png"),
    ("ipad", "76x76", "2x", 152, "icon-ipad-76@2x.png"),
    ("ipad", "83.5x83.5", "2x", 167, "icon-ipad-83.5@2x.png"),
    ("ios-marketing", "1024x1024", "1x", 1024, "icon-app-store-1024.png"),
]


def generate(source_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    # App Store icons may not contain an alpha channel.
    source = Image.open(source_path).convert("RGB")
    images = []
    for idiom, size, scale, pixels, filename in SLOTS:
        source.resize((pixels, pixels), resampling).save(output_dir / filename, optimize=True)
        images.append({"idiom": idiom, "size": size, "scale": scale, "filename": filename})
    (output_dir / "Contents.json").write_text(
        json.dumps({"images": images, "info": {"version": 1, "author": "xcode"}}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: ios_generate_icons.py <source-icon> <AppIcon.appiconset>")
    generate(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
