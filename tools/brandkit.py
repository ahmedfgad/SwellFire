"""Shared brand palette and PIL helpers for Swellfire media.

Pure Pillow so it runs anywhere the repo does. Every static-graphic generator
(icon, presplash, feature graphic, YouTube cover, video title cards) imports
this so the look stays unified, built from the game's OWN sprites:

* the ICON is deliberately simple — a single hero avatar on a solid, harmonious
  background (`compose_hero_icon`);
* the larger marketing pieces add a squad of hero avatars firing tracer rounds
  up through a glowing multiplier gate (`draw_squad_row` + `draw_gate_panel`),
  with the "Swellfire" wordmark (gold "Swell" + cream "fire").
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Warm "ember/fire" accent palette (gate, tracers, glow, wordmark).
EMBER = {
    "ember_black": (22, 6, 4),     # #160604
    "blood":       (122, 13, 18),  # #7a0d12
    "red":         (214, 31, 31),  # #d61f1f
    "orange":      (255, 122, 24), # #ff7a18
    "gold":        (255, 211, 77), # #ffd34d
    "cream":       (255, 240, 214),
    "white":       (255, 255, 255),
}

# Brand background: a solid, harmonious teal. Dark hero sprites and the warm
# gold/orange action both pop against it. Both stops equal -> a flat solid fill
# from vertical_gradient() (no shading).
BG_TOP = (20, 138, 144)
BG_BOTTOM = (20, 138, 144)

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
    """RGB image with a smooth vertical gradient top->bottom (solid if equal)."""
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


def solid_bg(size):
    """The brand's flat solid background as an RGBA image."""
    return Image.new("RGBA", size, BG_TOP + (255,))


def radial_glow(size, center, radius, color, max_alpha=180):
    """RGBA overlay: a soft radial glow you can alpha-composite onto a base."""
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


# --- real-sprite composition (professional look: use the game's own art) ----

SPRITES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "sprites"))


def load_sprite(name, height=None, scale=None):
    """Load a game sprite (assets/sprites/<name>.png) as RGBA, optionally
    resized to a target pixel `height` or by `scale` (LANCZOS, alpha-safe)."""
    fname = name if name.endswith(".png") else name + ".png"
    im = Image.open(os.path.join(SPRITES_DIR, fname)).convert("RGBA")
    if height:
        s = height / im.height
        im = im.resize((max(1, round(im.width * s)), int(height)), Image.LANCZOS)
    elif scale and scale != 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)),
                       Image.LANCZOS)
    return im


def sprite_shadow(sprite, blur=6, alpha=120):
    """A soft drop-shadow image (blurred black silhouette) for a sprite."""
    a = sprite.split()[3]
    sh = Image.new("RGBA", a.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", a.size, (0, 0, 0, alpha))
    sh.paste(solid, (0, 0), a)
    return sh.filter(ImageFilter.GaussianBlur(blur))


def paste_center(base, sprite, cx, cy, shadow=False):
    """Alpha-composite `sprite` centered at (cx, cy); optional soft shadow."""
    if shadow:
        sh = sprite_shadow(sprite, blur=max(3, sprite.height // 18))
        base.alpha_composite(sh, (int(cx - sh.width / 2),
                                  int(cy - sh.height / 2 + sprite.height * 0.06)))
    base.alpha_composite(sprite, (int(cx - sprite.width / 2),
                                  int(cy - sprite.height / 2)))


def draw_gate_panel(img, cx, cy, w, h, label):
    """A polished, glowing gate bar carrying a multiplier label, composited
    onto `img` (RGBA). Gradient fill, neon edge, drop shadow, top highlight."""
    pad = int(h * 1.4)
    tile = Image.new("RGBA", (int(w) + pad * 2, int(h) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    bx0, by0 = pad, pad
    bx1, by1 = pad + int(w), pad + int(h)
    rad = int(h * 0.34)

    glow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((bx0, by0, bx1, by1), radius=rad,
                                           fill=(255, 170, 40, 150))
    tile.alpha_composite(glow.filter(ImageFilter.GaussianBlur(h * 0.28)))

    grad = vertical_gradient((int(w), int(h)), EMBER["orange"], EMBER["gold"]).convert("RGBA")
    mask = Image.new("L", (int(w), int(h)), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, int(w) - 1, int(h) - 1),
                                           radius=rad, fill=255)
    tile.paste(grad, (bx0, by0), mask)

    d.rounded_rectangle((bx0, by0, bx1, by1), radius=rad, outline=EMBER["cream"],
                        width=max(2, int(h * 0.05)))
    d.rounded_rectangle((bx0 + int(h * 0.12), by0 + int(h * 0.12),
                         bx1 - int(h * 0.12), by0 + int(h * 0.34)),
                        radius=int(h * 0.16), fill=(255, 255, 255, 70))

    font = load_font(int(h * 0.62))
    d.text((bx0 + w / 2 + 2, by0 + h / 2 + 3), label, font=font,
           fill=(60, 12, 8, 200), anchor="mm")
    d.text((bx0 + w / 2, by0 + h / 2), label, font=font,
           fill=EMBER["ember_black"], anchor="mm")

    img.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))


def draw_muzzle_burst(img, x, y, r, color=None):
    """A glowing muzzle/impact flash: soft orange glow + gold starburst + white
    hot core, composited onto `img` at (x, y)."""
    color = color or EMBER["orange"]
    pad = int(r * 3) + 2
    tile = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    c = pad
    glow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((c - r, c - r, c + r, c + r),
                                 fill=(color[0], color[1], color[2], 210))
    tile.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r * 0.6)))
    d = ImageDraw.Draw(tile)
    pts = []
    for k in range(12):
        ang = k * math.pi / 6.0
        rad = r * 0.95 if k % 2 == 0 else r * 0.40
        pts.append((c + math.cos(ang) * rad, c + math.sin(ang) * rad))
    d.polygon(pts, fill=EMBER["gold"])
    d.ellipse((c - r * 0.4, c - r * 0.4, c + r * 0.4, c + r * 0.4), fill=EMBER["white"])
    img.alpha_composite(tile, (int(x - c), int(y - c)))


def draw_tracer_round(img, x, y, length, width, angle_deg=0.0, color=None):
    """One realistic tracer round: a blurred orange glow streak + bright gold
    body capsule + white-hot head, rotated to `angle_deg` (0 = up), at (x, y)."""
    color = color or EMBER["gold"]
    pad = int(width * 4) + 2
    tw = int(width) + pad * 2
    th = int(length) + pad * 2
    tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    cx = tw / 2.0
    x0, x1 = cx - width / 2.0, cx + width / 2.0
    y_top, y_bot = pad, pad + length
    glow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((x0 - width, y_top, x1 + width, y_bot),
                                           radius=width, fill=(255, 140, 36, 200))
    tile.alpha_composite(glow.filter(ImageFilter.GaussianBlur(width * 0.9)))
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle((x0, y_top + length * 0.28, x1, y_bot),
                        radius=width / 2.0, fill=color)
    hr = width * 0.95
    d.ellipse((cx - hr, y_top, cx + hr, y_top + 2 * hr), fill=EMBER["white"])
    rot = tile.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(rot, (int(x - rot.width / 2.0), int(y - rot.height / 2.0)))


def draw_tracer(img, x_from, y_from, x_to, y_to, n=2, size=None):
    """Gunfire from (x_from,y_from) toward (x_to,y_to): a few angled tracer
    rounds streaking along the path plus a bright impact burst at the target.
    (The muzzle flash at the origin is drawn separately, after the shooter.)"""
    dx, dy = x_to - x_from, y_to - y_from
    dist = math.hypot(dx, dy)
    if dist < 1.0:
        return
    angle = math.degrees(math.atan2(-dy, dx)) - 90.0   # 0 = straight up
    length = dist * 0.30
    width = size or max(4.0, dist * 0.045)
    for i in range(n):
        t = 0.22 + 0.50 * (i / max(1, n - 1)) if n > 1 else 0.45
        px = x_from + dx * t
        py = y_from + dy * t
        draw_tracer_round(img, px, py, length, width, angle_deg=angle)
    draw_muzzle_burst(img, x_to, y_to, width * 1.7, color=EMBER["white"])


def compose_hero_icon(img, box, hero="hero_blue"):
    """The simple app icon: one hero avatar, centered on a soft disc with a
    drop shadow. `box` = (x0, y0, x1, y1) on an RGBA image."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = x0 + w * 0.5, y0 + h * 0.5
    # soft light disc behind the hero for a clean, harmonious focal point
    disc = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = min(w, h) * 0.46
    ImageDraw.Draw(disc).ellipse((cx - dr, cy - dr, cx + dr, cy + dr),
                                 fill=(255, 255, 255, 42))
    img.alpha_composite(disc.filter(ImageFilter.GaussianBlur(dr * 0.05)))
    hero_img = load_sprite(hero, height=int(h * 0.76))
    paste_center(img, hero_img, cx, cy + h * 0.02, shadow=True)


def draw_squad_row(img, cx, base_y, n, hero_h, fire=True, hero="hero_blue"):
    """A row of `n` hero avatars standing on `base_y`. When `fire`, each emits a
    clean upward tracer streak + a muzzle flash at the gun (no floating impacts).
    Returns the x positions."""
    sol = load_sprite(hero, height=int(hero_h))
    sw = sol.width
    gap = sw * 1.08
    xs = [cx + (i - (n - 1) / 2.0) * gap for i in range(n)]
    for x in xs:
        paste_center(img, sol, x, base_y - hero_h / 2.0, shadow=True)
    if fire:
        width = max(4.0, hero_h * 0.05)
        for x in xs:
            mx, my = x + sw * 0.16, base_y - hero_h * 0.52
            draw_tracer_round(img, mx, my - hero_h * 0.55, hero_h * 0.7, width)
            draw_muzzle_burst(img, mx, my, max(6.0, hero_h * 0.07))
    return xs


def draw_logo_glyph(img, box, **_kw):
    """Brand glyph for the icon = the simple hero avatar."""
    compose_hero_icon(img, box)


def draw_wordmark(draw, xy, font, anchor="lm"):
    """'Swellfire' — gold 'Swell' + cream 'fire'. Returns total width."""
    x, y = xy
    swell, fire = "Swell", "fire"
    sw = draw.textlength(swell, font=font)
    draw.text((x, y), swell, font=font, fill=EMBER["gold"], anchor=anchor)
    draw.text((x + sw, y), fire, font=font, fill=EMBER["cream"], anchor=anchor)
    return sw + draw.textlength(fire, font=font)
