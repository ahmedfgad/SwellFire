"""Shared Ember-brand palette and PIL drawing helpers for Swellfire media.

Pure Pillow so it runs anywhere the repo does. Every static-graphic generator
(icon, presplash, feature graphic, YouTube cover, video title cards) imports
this so the Ember look stays unified: deep ember-black -> blood -> red ->
orange -> gold, a squad-chevron-bursting-from-a-flame glyph, and the
"Swellfire" wordmark (gold "Swell" + cream "fire").
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Locked Ember palette (see spec).
EMBER = {
    "ember_black": (22, 6, 4),     # #160604
    "blood":       (122, 13, 18),  # #7a0d12
    "red":         (214, 31, 31),  # #d61f1f
    "orange":      (255, 122, 24), # #ff7a18
    "gold":        (255, 211, 77), # #ffd34d
    "cream":       (255, 240, 214),
    "white":       (255, 255, 255),
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size, bold=True):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def vertical_gradient(size, top_rgb, bottom_rgb):
    """RGB image with a smooth vertical gradient top->bottom."""
    w, h = size
    base = Image.new("RGB", size)
    px = base.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    return base


def radial_glow(size, center, radius, color, max_alpha=180):
    """RGBA overlay: a soft radial glow you can paste with itself as mask."""
    w, h = size
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    px = glow.load()
    cx, cy = center
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy)
            if d < radius:
                a = int(max_alpha * (1.0 - d / radius) ** 2)
                px[x, y] = (color[0], color[1], color[2], a)
    return glow.filter(ImageFilter.GaussianBlur(radius * 0.06))


def _flame_polygon(cx, base_y, w, h):
    """Teardrop flame outline (point up). Returns a list of (x, y)."""
    pts = []
    steps = 28
    for i in range(steps + 1):
        t = i / steps
        # width tapers to 0 at the tip (t=1), bulges near the base.
        bulge = math.sin(t * math.pi) ** 0.6
        half = (w / 2) * bulge * (1.0 - 0.65 * t)
        x = cx - half + (math.sin(t * math.pi * 2) * w * 0.04)
        y = base_y - h * t
        pts.append((x, y))
    for i in range(steps, -1, -1):
        t = i / steps
        bulge = math.sin(t * math.pi) ** 0.6
        half = (w / 2) * bulge * (1.0 - 0.65 * t)
        x = cx + half + (math.sin(t * math.pi * 2) * w * 0.04)
        y = base_y - h * t
        pts.append((x, y))
    return pts


def draw_flame(draw, cx, base_y, w, h):
    """Layered ember flame: blood -> red -> orange -> gold core."""
    layers = [
        (EMBER["blood"], 1.00),
        (EMBER["red"], 0.82),
        (EMBER["orange"], 0.58),
        (EMBER["gold"], 0.30),
    ]
    for color, scale in layers:
        draw.polygon(_flame_polygon(cx, base_y, w * scale, h * scale),
                     fill=color)


def draw_squad_chevron(draw, cx, cy, scale, color):
    """Three runner triangles in a rising V (the 'squad')."""
    def tri(ox, oy, s):
        return [(cx + ox, cy + oy - s),
                (cx + ox - s * 0.8, cy + oy + s * 0.7),
                (cx + ox + s * 0.8, cy + oy + s * 0.7)]
    s = scale
    draw.polygon(tri(0, -s * 1.1, s * 1.0), fill=color)        # leader
    draw.polygon(tri(-s * 1.6, s * 0.2, s * 0.85), fill=color) # left wing
    draw.polygon(tri(s * 1.6, s * 0.2, s * 0.85), fill=color)  # right wing


def draw_gate_tab(draw, xy, text, font, bg, fg):
    """Small rounded-rect gate tag, e.g. '×2'."""
    x, y = xy
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    pad = max(6, th // 3)
    box = (x, y, x + tw + pad * 2, y + th + pad * 2)
    draw.rounded_rectangle(box, radius=pad, fill=bg)
    draw.text((x + pad - l, y + pad - t), text, font=font, fill=fg)
    return box


def draw_logo_glyph(img, box):
    """Compose the brand glyph (flame + rising squad chevron + ×2 tab) inside
    `box` = (x0, y0, x1, y1) on an RGBA image."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx = x0 + w * 0.5
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    draw_flame(d, cx, y0 + h * 0.92, w * 0.72, h * 0.86)
    draw_squad_chevron(d, cx, y0 + h * 0.46, scale=h * 0.085,
                       color=EMBER["cream"])
    tab_font = load_font(max(12, int(h * 0.13)))
    draw_gate_tab(d, (x0 + w * 0.60, y0 + h * 0.05), "×2", tab_font,
                  bg=EMBER["white"], fg=EMBER["red"])
    img.alpha_composite(overlay)


def draw_wordmark(draw, xy, font, anchor="lm"):
    """'Swellfire' — gold 'Swell' + cream 'fire'. Returns total width."""
    x, y = xy
    swell, fire = "Swell", "fire"
    sw = draw.textlength(swell, font=font)
    draw.text((x, y), swell, font=font, fill=EMBER["gold"], anchor=anchor)
    draw.text((x + sw, y), fire, font=font, fill=EMBER["cream"], anchor=anchor)
    return sw + draw.textlength(fire, font=font)
