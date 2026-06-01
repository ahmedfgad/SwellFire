# Swellfire graphics.
#
# Top of file: the Mesh-batched renderer that gameplay uses from M3 onwards
# (atlas loader, parallel-array entity pool, batched-mesh widget that draws
# the whole pool with a single Kivy `Mesh` instruction, debug overlay).
#
# Bottom of file: the static placeholder sprite widgets the M1 tutorial /
# guide screens reference. They use canvas primitives and are intentionally
# lo-fi; M14 swaps them for atlas-backed sprites and the real character art.

from __future__ import annotations

import json
import math
import os

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line, Mesh
from kivy.core.image import Image as CoreImage
from kivy.resources import resource_find
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp, Metrics
from kivy.properties import BooleanProperty, NumericProperty


# ===========================================================================
# World pixel scale (density independence)
# ===========================================================================
#
# The whole game *world* (sprite sizes, speeds, distances, gate boxes) is
# dimensioned in raw pixels that were tuned on a density-1.0 desktop window.
# On a high-density (Retina) mobile surface, Kivy reports Window.size in
# physical pixels and Metrics.density is 2-3, so those raw-pixel magnitudes
# render tiny while sp()/dp() text scales up with density — gate equations
# overflow their fixed-px box, sprites/coins/monsters look small.
#
# `ws(value)` multiplies a world-space pixel magnitude by the device density so
# the world becomes density-independent: identical look AND feel at any
# density, and a *no-op at density 1.0* (so the desktop build is unchanged).
# Apply it at every runtime read of a world-px size/speed/distance/offset;
# leave positions derived from the (already-scaled) stage bounds alone.
_WORLD_SCALE = None


def world_scale() -> float:
    """Cached world-space pixel scale (= Metrics.density, clamped to >= 1.0).

    Read lazily and cached so it is stable for the whole run and picks up the
    real density only after the Window (and thus Metrics.density) exists —
    reading it at import time would bake in the pre-window default of 1.0.
    """
    global _WORLD_SCALE
    if _WORLD_SCALE is None:
        try:
            d = float(Metrics.density)
        except Exception:
            d = 1.0
        _WORLD_SCALE = d if d and d > 0.0 else 1.0
    return _WORLD_SCALE


def ws(value: float) -> float:
    """Scale a world-space pixel magnitude by the device density."""
    return value * world_scale()


def set_world_scale(value) -> None:
    """Override / reset the cached scale. Pass None to re-read on next use.

    Used by headless tests to exercise the density-3 path without a Retina
    display; production code never calls this.
    """
    global _WORLD_SCALE
    _WORLD_SCALE = float(value) if value else None


# ===========================================================================
# Mesh-batched renderer (M3)
# ===========================================================================

class SpriteAtlas:
    """Loads a packed PNG atlas + its UV-map JSON.

    The companion `tools/gen_placeholder_atlas.py` produces the placeholder
    bank used through M13; `tools/pack_atlas.py` (added later) packs real
    sprite-sheet frames during the M14 asset pass.

    JSON shape::

        {
            "atlas_width": 128,
            "atlas_height": 128,
            "frames": {
                "runner_blue": {"x": 0, "y": 0, "w": 64, "h": 64},
                ...
            }
        }

    `x` and `y` are PIL coordinates (origin top-left); the loader converts to
    GL texture coords (origin bottom-left).
    """

    def __init__(self, png_path: str, json_path: str):
        # Import here so unit tests that don't touch the texture don't pay
        # the cost of initializing Kivy's image providers.
        self._image = CoreImage(png_path, nocache=True)
        self.texture = self._image.texture
        # Pixel-art-style: nearest filtering keeps frames crisp at any scale.
        self.texture.min_filter = "nearest"
        self.texture.mag_filter = "nearest"

        with open(resource_find(json_path) or json_path) as f:
            meta = json.load(f)
        # name -> (u0, v0, u1, v1) in the atlas texture's normalized space.
        self._frames: dict[str, tuple[float, float, float, float]] = {}
        # Pixel-space (x, y, w, h) per frame with y measured top-down,
        # as ``Texture.get_region`` expects. Used by ``frame_region`` to
        # carve out a sub-texture for AtlasSprite.
        self._frame_px: dict[str, tuple[int, int, int, int]] = {}
        self._region_cache: dict[str, "Texture"] = {}
        self._build_frames(meta)

    def _build_frames(self, meta: dict) -> None:
        """Populate ``_frames`` / ``_frame_px`` from a parsed atlas JSON.

        ``_frames`` maps a name to ``(u0, v0, u1, v1)`` where ``v0`` is the v
        the renderer puts on the sprite's bottom edge and ``v1`` on the top.

        These atlases load with PIL row 0 at GL ``v=0`` — i.e. **no** vertical
        flip (verified by reading back ``Texture.pixels``: the frames packed at
        PIL ``y=0`` light up at GL ``v∈[0, h/H]``, while sampling ``v=1-…``
        hits the empty top of the texture). The original loader, and Kivy's own
        ``get_region``, both assume the flipped layout, so against the 256×256
        atlases every top-packed frame (enemies, squad runner, projectiles,
        particles) sampled transparent pixels and drew nothing. We therefore
        map directly: a frame at PIL ``(x, y, w, h)`` occupies GL
        ``v∈[y/H, (y+h)/H]``. To keep the sprite upright the renderer's top
        edge (``v1``) takes the smaller v (PIL-top) and the bottom edge
        (``v0``) the larger v (PIL-bottom).
        """
        self.atlas_w = float(meta["atlas_width"])
        self.atlas_h = float(meta["atlas_height"])
        for name, rect in meta["frames"].items():
            x = float(rect["x"]); y = float(rect["y"])
            w = float(rect["w"]); h = float(rect["h"])
            u0 = x / self.atlas_w
            u1 = (x + w) / self.atlas_w
            v0 = (y + h) / self.atlas_h
            v1 = y / self.atlas_h
            self._frames[name] = (u0, v0, u1, v1)
            self._frame_px[name] = (int(x), int(y), int(w), int(h))

    def reload(self, png_path: str, json_path: str) -> None:
        """Swap the underlying texture + frame map without recreating
        the SpriteAtlas object. Used for per-world atlas swaps in M14
        — pool controllers + BatchedRenderers keep their references
        to ``self`` and pick up the new ``.texture`` on next mesh draw.
        """
        self._image = CoreImage(png_path, nocache=True)
        self.texture = self._image.texture
        self.texture.min_filter = "nearest"
        self.texture.mag_filter = "nearest"
        with open(resource_find(json_path) or json_path) as f:
            meta = json.load(f)
        self._frames = {}
        self._frame_px = {}
        self._region_cache = {}
        self._build_frames(meta)

    def frame(self, name: str) -> tuple[float, float, float, float]:
        return self._frames[name]

    def frame_region(self, name: str):
        """Return a sub-texture for ``name``.

        Used by AtlasSprite — sampling a sub-texture with default UVs
        sidesteps a Kivy Rectangle quirk where explicit ``tex_coords``
        rendered as fully transparent against the M14 256×256 atlas.
        Cached because Texture.get_region creates a new texture
        object on every call.
        """
        cached = self._region_cache.get(name)
        if cached is not None:
            return cached
        x, y, w, h = self._frame_px[name]
        region = self.texture.get_region(x, y, w, h)
        self._region_cache[name] = region
        return region

    def names(self) -> list[str]:
        return list(self._frames.keys())


class EntityPool:
    """Fixed-capacity sprite pool stored as parallel arrays.

    Parallel arrays (lists of floats) are faster to iterate than per-entity
    Python objects because the hot loop only touches plain numbers — no
    attribute lookups, no method dispatch. The hot loop lives in
    `BatchedRenderer.rebuild` below; this class only stores state.

    Slot management is intentionally minimal for M3 (linear scan on
    `spawn`). M5's pool keeps a free-list so spawn is O(1).
    """

    def __init__(self, capacity: int, atlas: SpriteAtlas):
        self.capacity = capacity
        self.atlas = atlas
        # Position, velocity, half-size (so the hot loop avoids divides).
        self.cx = [0.0] * capacity
        self.cy = [0.0] * capacity
        self.vx = [0.0] * capacity
        self.vy = [0.0] * capacity
        self.hw = [0.0] * capacity
        self.hh = [0.0] * capacity
        # Per-slot UV rectangle, copied from the atlas at spawn time so the
        # rebuild loop never has to do a dict lookup.
        self.u0 = [0.0] * capacity
        self.v0 = [0.0] * capacity
        self.u1 = [0.0] * capacity
        self.v1 = [0.0] * capacity
        # active[i] == 1 for live entities, 0 for free slots.
        self.active = bytearray(capacity)
        self.active_count = 0

    def spawn(self, x: float, y: float, vx: float, vy: float,
              w: float, h: float, frame_name: str) -> int:
        u0, v0, u1, v1 = self.atlas.frame(frame_name)
        for i in range(self.capacity):
            if not self.active[i]:
                self.cx[i] = x
                self.cy[i] = y
                self.vx[i] = vx
                self.vy[i] = vy
                self.hw[i] = w * 0.5
                self.hh[i] = h * 0.5
                self.u0[i] = u0
                self.v0[i] = v0
                self.u1[i] = u1
                self.v1[i] = v1
                self.active[i] = 1
                self.active_count += 1
                return i
        return -1   # pool full

    def release(self, i: int) -> None:
        if self.active[i]:
            self.active[i] = 0
            self.active_count -= 1


class BatchedRenderer(Widget):
    """Draws an `EntityPool` with one `Mesh` instruction.

    The whole pool turns into a single draw call (one vertex buffer +
    one index buffer + one texture bind), which is what unlocks the
    hundred-plus on-screen entity counts the plan requires. Per-frame
    cost is just the Python-side vertex emit loop — see `rebuild`.
    """

    def __init__(self, pool: EntityPool, *,
                 tint: tuple[float, float, float, float] | None = None,
                 owner_array: "bytearray | None" = None,
                 owner_filter: int | None = None,
                 skip_array: "bytearray | None" = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.pool = pool
        # M13 — owner-filter renderer. When set, only pool slots with
        # ``owner_array[i] == owner_filter`` reach the mesh. Combined
        # with ``tint`` this lets us draw local and opponent
        # projectiles from a single shared pool with different colours,
        # so the player can read whose shots are whose at a glance.
        self._owner_array = owner_array
        self._owner_filter = owner_filter
        # Skip array: when truthy at index i, that slot is rendered as
        # if it were inactive. Used by the per-player pickup pool — the
        # local player's already-collected coins stay in the pool (so
        # the opponent can still grab their copy) but are hidden from
        # the local player's view.
        self._skip_array = skip_array
        with self.canvas:
            # Always emit a Color instruction so callers can mutate the
            # tint after construction via ``set_tint`` — used by M14's
            # per-world theming. Default white = no visual effect.
            if tint is not None:
                self._tint_color = Color(*tint)
            else:
                self._tint_color = Color(1.0, 1.0, 1.0, 1.0)
            self._mesh = Mesh(
                mode="triangles",
                texture=pool.atlas.texture,
                vertices=[],
                indices=[],
            )
        self._verts: list[float] = [0.0] * (pool.capacity * 16)

    def rebuild(self) -> None:
        pool = self.pool
        cx = pool.cx
        cy = pool.cy
        hw = pool.hw
        hh = pool.hh
        u0 = pool.u0
        v0 = pool.v0
        u1 = pool.u1
        v1 = pool.v1
        active = pool.active
        owner_arr = self._owner_array
        owner_filter = self._owner_filter
        skip_arr = self._skip_array
        verts = self._verts
        indices: list[int] = []

        out_i = 0
        cap = pool.capacity
        for i in range(cap):
            if not active[i]:
                continue
            if skip_arr is not None and skip_arr[i]:
                continue
            if (owner_filter is not None and owner_arr is not None
                    and owner_arr[i] != owner_filter):
                continue
            x1 = cx[i] - hw[i]
            x2 = cx[i] + hw[i]
            y1 = cy[i] - hh[i]
            y2 = cy[i] + hh[i]
            base = out_i * 16
            # Bottom-left
            verts[base] = x1
            verts[base + 1] = y1
            verts[base + 2] = u0[i]
            verts[base + 3] = v0[i]
            # Bottom-right
            verts[base + 4] = x2
            verts[base + 5] = y1
            verts[base + 6] = u1[i]
            verts[base + 7] = v0[i]
            # Top-right
            verts[base + 8] = x2
            verts[base + 9] = y2
            verts[base + 10] = u1[i]
            verts[base + 11] = v1[i]
            # Top-left
            verts[base + 12] = x1
            verts[base + 13] = y2
            verts[base + 14] = u0[i]
            verts[base + 15] = v1[i]
            bv = out_i * 4
            # Two triangles: (BL, BR, TR) and (BL, TR, TL).
            indices.extend((bv, bv + 1, bv + 2, bv, bv + 2, bv + 3))
            out_i += 1

        # Kivy's Mesh.vertices accepts a flat sequence of floats; we slice
        # the scratch buffer so we don't ship trailing zeros for empty slots.
        self._mesh.vertices = verts[:out_i * 16]
        self._mesh.indices = indices

    def set_tint(self, color: tuple[float, float, float, float]) -> None:
        """Update the tint Color applied to this renderer's mesh.

        Used by M14's per-world theming — GameScreen calls this when a
        level loads so e.g. desert-world enemies pick up a warm orange
        hue and snowfield enemies cool down toward blue.
        """
        if self._tint_color is None:
            return
        self._tint_color.rgba = color


# --- debug overlay --------------------------------------------------------

class DebugOverlay(Widget):
    """Top-left HUD: FPS + key entity counts + frame time.

    Refreshed at 5 Hz to keep its own cost off the hot path. Any screen can
    drop one of these in and call `report_counts(**counts)` per frame; the
    overlay shows the latest snapshot.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.label = Label(
            text="", font_size=sp(14), color=(0.95, 1.0, 0.55, 1),
            halign="left", valign="top", markup=False,
        )
        self.add_widget(self.label)
        self.bind(pos=self._sync, size=self._sync)
        self._counts: dict[str, int] = {}
        self._tick = Clock.schedule_interval(self._refresh, 1 / 5.0)

    def _sync(self, *_):
        self.label.pos = self.pos
        self.label.size = self.size
        self.label.text_size = self.size

    def report_counts(self, **counts) -> None:
        self._counts = counts

    def _refresh(self, _dt) -> None:
        fps = Clock.get_fps()
        parts = ["FPS {:5.1f}".format(fps)]
        if fps > 0:
            parts.append("({:.1f} ms)".format(1000.0 / fps))
        for k, v in self._counts.items():
            parts.append("{}: {}".format(k, v))
        self.label.text = "  ".join(parts)

    def stop(self) -> None:
        if self._tick is not None:
            self._tick.cancel()
            self._tick = None


# --- single-sprite widget for hero / boss / UI sprites -------------------

# Per-path texture cache shared across all TextureSprites — loading a
# PNG via CoreImage is cheap but not free, and the hero / boss /
# opponent etc. tend to use the same file across screens.
_texture_cache: dict[str, "Texture"] = {}


def load_texture(path: str):
    """Load a PNG into a Kivy Texture, caching by path.

    Sets nearest-neighbour filtering so pixel-art frames stay crisp
    when scaled to the sprite's widget size.
    """
    tex = _texture_cache.get(path)
    if tex is not None:
        return tex
    img = CoreImage(path, nocache=True)
    tex = img.texture
    tex.min_filter = "nearest"
    tex.mag_filter = "nearest"
    _texture_cache[path] = tex
    return tex


class TextureSprite(Widget):
    """One-file sprite widget — loads a PNG as its own Texture and draws
    it with a Rectangle that uses DEFAULT tex_coords (whole texture).

    This is the rendering path we use for the hero, boss, opponent and
    any other lone widget that previously used AtlasSprite. The
    motivation is M14's discovery that Kivy 2.3's Rectangle + custom
    ``tex_coords`` against an atlas Texture renders fully transparent
    against atlases larger than 128×128. A per-sprite Texture (with
    default UVs covering the whole image) sidesteps the issue and also
    makes integrating third-party art a single drop-in: replace the
    PNG, you're done.

    API mirrors AtlasSprite where possible — pos/size, a ``flash``
    overlay used by the M11 damage-feedback layer, and ``set_texture``
    so the boss widget can swap looks mid-fight.
    """

    def __init__(self, png_path: str, **kwargs):
        super().__init__(**kwargs)
        tex = load_texture(png_path)
        with self.canvas:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=tex)
        with self.canvas.after:
            # Flash overlay on canvas.after so its Color() instruction
            # doesn't bleed into the main rect's draw state.
            self._flash_color = Color(1.0, 0.30, 0.30, 0.0)
            self._flash_rect = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self._sync()
        self._flash_remaining = 0.0
        self._flash_max = 0.0
        self._flash_peak_alpha = 0.0

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._flash_rect.pos = self.pos
        self._flash_rect.size = self.size

    def set_texture(self, png_path: str) -> None:
        self._rect.texture = load_texture(png_path)

    def flash(self, duration: float = 0.28,
              color: tuple[float, float, float, float] = (1.0, 0.25, 0.25, 0.78)) -> None:
        self._flash_color.rgba = color
        self._flash_peak_alpha = color[3]
        self._flash_remaining = duration
        self._flash_max = duration

    def tick_flash(self, dt: float) -> None:
        if self._flash_remaining <= 0.0:
            return
        self._flash_remaining = max(0.0, self._flash_remaining - dt)
        if self._flash_remaining <= 0.0:
            self._flash_color.a = 0.0
        else:
            self._flash_color.a = self._flash_peak_alpha * (
                self._flash_remaining / max(self._flash_max, 0.001)
            )


class AtlasSprite(Widget):
    """One sprite from an atlas drawn as a single textured Rectangle.

    Use this for low-count widgets that need detail and interaction (hero,
    boss, gate panel art). Pooled gameplay swarms go through `BatchedRenderer`
    instead — that's where the per-draw-call cost actually matters.

    Includes a `flash()` method for the M11 danger-feedback layer: an
    overlay rectangle is drawn on top with a tint color whose alpha decays
    over `duration` seconds. Call `tick_flash(dt)` from the game loop.
    """

    def __init__(self, atlas: "SpriteAtlas", frame_name: str, **kwargs):
        super().__init__(**kwargs)
        self._atlas = atlas
        u0, v0, u1, v1 = atlas.frame(frame_name)
        with self.canvas:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(
                texture=atlas.texture,
                tex_coords=(u0, v0, u1, v0, u1, v1, u0, v1),
            )
            self._flash_color = Color(1.0, 0.30, 0.30, 0.0)
            self._flash_rect = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self._sync()
        self._flash_remaining = 0.0
        self._flash_max = 0.0
        self._flash_peak_alpha = 0.0

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._flash_rect.pos = self.pos
        self._flash_rect.size = self.size

    def set_frame(self, frame_name: str) -> None:
        u0, v0, u1, v1 = self._atlas.frame(frame_name)
        self._rect.tex_coords = (u0, v0, u1, v0, u1, v1, u0, v1)

    def flash(self, duration: float = 0.28,
              color: tuple[float, float, float, float] = (1.0, 0.25, 0.25, 0.78)) -> None:
        self._flash_color.rgba = color
        self._flash_peak_alpha = color[3]
        self._flash_remaining = duration
        self._flash_max = duration

    def tick_flash(self, dt: float) -> None:
        if self._flash_remaining <= 0.0:
            return
        self._flash_remaining = max(0.0, self._flash_remaining - dt)
        if self._flash_remaining <= 0.0:
            self._flash_color.a = 0.0
        else:
            self._flash_color.a = self._flash_peak_alpha * (
                self._flash_remaining / max(self._flash_max, 0.001)
            )


# Atlas-discovery helper for the runtime: lets gameplay code ask for an
# atlas by base name (e.g. "stress") and get the right paths in dev *and*
# in a frozen PyInstaller bundle.
def find_atlas(base_name: str, project_dir: str = "") -> tuple[str, str]:
    if not project_dir:
        project_dir = os.path.dirname(os.path.abspath(__file__))
    atlas_dir = os.path.join(project_dir, "assets", "atlases")
    return (
        os.path.join(atlas_dir, base_name + ".png"),
        os.path.join(atlas_dir, base_name + ".json"),
    )


# ===========================================================================
# Themed gradient background (used by every meta screen)
# ===========================================================================

class Background(Widget):
    """Full-screen gradient drawn from a world theme."""

    def __init__(self, theme, **kwargs):
        super().__init__(**kwargs)
        self._theme = theme
        with self.canvas.before:
            self._top_color = Color(*theme["top"])
            self._top_rect = Rectangle()
            self._mid_color = Color(
                (theme["top"][0] + theme["bottom"][0]) / 2,
                (theme["top"][1] + theme["bottom"][1]) / 2,
                (theme["top"][2] + theme["bottom"][2]) / 2,
            )
            self._mid_rect = Rectangle()
            self._bot_color = Color(*theme["bottom"])
            self._bot_rect = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *_):
        x, y = self.pos
        w, h = self.size
        third = h / 3.0
        self._bot_rect.pos = (x, y)
        self._bot_rect.size = (w, third)
        self._mid_rect.pos = (x, y + third)
        self._mid_rect.size = (w, third)
        self._top_rect.pos = (x, y + 2 * third)
        self._top_rect.size = (w, third)

    def set_theme(self, theme):
        self._theme = theme
        self._top_color.rgb = theme["top"]
        self._bot_color.rgb = theme["bottom"]
        self._mid_color.rgb = (
            (theme["top"][0] + theme["bottom"][0]) / 2,
            (theme["top"][1] + theme["bottom"][1]) / 2,
            (theme["top"][2] + theme["bottom"][2]) / 2,
        )


# --- five-pointed star (used by the level-select rating) ------------------

def draw_star(cx, cy, outer, color):
    """Add a filled 5-point star to the current canvas at (cx, cy)."""
    inner = outer * 0.45
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / 2 + i * math.pi / 5
        points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    Color(*color)
    Line(points=points + points[:2], width=1.4, close=True)
    Ellipse(pos=(cx - outer * 0.55, cy - outer * 0.55),
            size=(outer * 1.1, outer * 1.1))


# ===========================================================================
# Placeholder sprite widgets used by the M1 tutorial / guide.
# Replaced wholesale at M14 with atlas-backed sprites.
# ===========================================================================

class _PlaceholderSprite(Widget):
    moving = BooleanProperty(False)
    face_x = NumericProperty(1.0)
    face_y = NumericProperty(0.0)
    cx = NumericProperty(0.5)   # normalized play-area coordinates (0..1)
    cy = NumericProperty(0.5)
    tx = NumericProperty(0.5)
    ty = NumericProperty(0.5)

    def start(self):
        pass

    def stop(self):
        pass

    def hit_flash(self):
        pass


class RunnerSprite(_PlaceholderSprite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._color = Color(0.20, 0.65, 0.95, 1)
            self._body = RoundedRectangle(radius=[8])
            self._head_color = Color(1.0, 0.85, 0.65, 1)
            self._head = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._body.pos = (x + w * 0.18, y)
        self._body.size = (w * 0.64, h * 0.66)
        self._head.pos = (x + w * 0.30, y + h * 0.62)
        self._head.size = (w * 0.40, h * 0.36)


class PlayerSprite(RunnerSprite):
    pass


class EnemySprite(_PlaceholderSprite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(0.85, 0.25, 0.30, 1)
            self._body = RoundedRectangle(radius=[8])
            Color(1, 1, 1, 1)
            self._eye = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._body.pos = (x + w * 0.16, y + h * 0.04)
        self._body.size = (w * 0.68, h * 0.84)
        self._eye.pos = (x + w * 0.42, y + h * 0.62)
        self._eye.size = (w * 0.16, h * 0.16)


class MonsterSprite(EnemySprite):
    mtype = NumericProperty(1)
    hp = NumericProperty(1)
    max_hp = NumericProperty(1)


class GateSprite(_PlaceholderSprite):
    label = "+1"

    def __init__(self, label="+1", **kwargs):
        super().__init__(**kwargs)
        self.label = label
        with self.canvas:
            Color(0.30, 0.85, 0.45, 0.85)
            self._frame = RoundedRectangle(radius=[10])
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._frame.pos = (x + w * 0.04, y + h * 0.04)
        self._frame.size = (w * 0.92, h * 0.92)


class Projectile(_PlaceholderSprite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(1.0, 0.92, 0.4, 1)
            self._dot = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._dot.pos = (x + w * 0.30, y + h * 0.30)
        self._dot.size = (w * 0.40, h * 0.40)


class Hazard(_PlaceholderSprite):
    size_factor = NumericProperty(1.0)
    period = NumericProperty(1.0)
    ax = NumericProperty(0.0)
    ay = NumericProperty(0.0)
    bx = NumericProperty(0.0)
    by = NumericProperty(0.0)
    t = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(1, 0.45, 0.15, 0.95)
            self._dot = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._dot.pos = (x + w * 0.2, y + h * 0.2)
        self._dot.size = (w * 0.6, h * 0.6)


class Coin(_PlaceholderSprite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(1.0, 0.85, 0.20, 1)
            self._dot = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._dot.pos = (x + w * 0.20, y + h * 0.20)
        self._dot.size = (w * 0.60, h * 0.60)


class Freezer(_PlaceholderSprite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(0.40, 0.85, 1.0, 1)
            self._dot = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        x, y = self.pos
        w, h = self.size
        self._dot.pos = (x + w * 0.20, y + h * 0.20)
        self._dot.size = (w * 0.60, h * 0.60)


class ShieldAura(Widget):
    """A soft glowing bubble drawn around the hero while a shield is active.

    Replaces the old flat rectangle tint: a translucent filled disc plus a
    brighter pulsing ring reads instantly as a protective bubble and looks
    far nicer. Position it via ``center`` each frame; ``show()`` / ``hide()``
    toggle it (and the ring's gentle alpha pulse).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        with self.canvas:
            self._fill_color = Color(0.35, 0.75, 1.0, 0.16)
            self._fill = Ellipse()
            self._ring_color = Color(0.55, 0.88, 1.0, 0.9)
            self._ring = Line(width=2.6)
            self._ring2_color = Color(0.85, 0.95, 1.0, 0.5)
            self._ring2 = Line(width=1.4)
        self.bind(pos=self._redraw, size=self._redraw)
        self._anim = None
        self._redraw()

    def _redraw(self, *_):
        cx, cy = self.center
        r = max(self.width, self.height) * 0.5
        self._fill.pos = (cx - r, cy - r)
        self._fill.size = (2 * r, 2 * r)
        self._ring.circle = (cx, cy, r * 0.96)
        self._ring2.circle = (cx, cy, r * 0.78)

    def show(self) -> None:
        self.opacity = 1.0
        if self._anim is None:
            anim = (Animation(a=0.45, duration=0.5, t="in_out_sine")
                    + Animation(a=0.95, duration=0.5, t="in_out_sine"))
            anim.repeat = True
            anim.start(self._ring_color)
            self._anim = anim

    def hide(self) -> None:
        self.opacity = 0.0
        if self._anim is not None:
            self._anim.cancel(self._ring_color)
            self._anim = None


class AimReticle(Widget):
    """Manual-aim reticle: a faint line from the squad up to a pulsing ring
    at the convergence point. Cyan normally, red + thicker when a target is
    under it. Drawn in ``canvas`` (no stage depth issue — it sits above the
    road like the shield aura). Position via ``set_endpoints`` each frame.
    """

    R = 16.0   # ring radius in logical px (caller may pass ws()-scaled size)
    SEGMENTS = 5
    BEAM_ALPHA = 0.45   # brightest (squad-end) segment alpha

    def __init__(self, radius: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        self._r = radius if radius is not None else self.R
        self._locked = False
        with self.canvas:
            self._seg_colors = []
            self._segs = []
            n = self.SEGMENTS
            for i in range(n):
                self._seg_colors.append(Color(0.55, 0.88, 1.0, 0.0))
                # width tapers ~2.0 (squad) -> ~1.0 (reticle)
                w = 2.0 - 1.0 * (i / (n - 1))
                self._segs.append(Line(width=max(1.0, w)))
            self._ring_color = Color(0.55, 0.88, 1.0, 0.95)
            self._ring = Line(width=2.2)
            self._dot_color = Color(0.85, 0.97, 1.0, 0.9)
            self._dot = Line(width=1.4)
        self._anim = None
        self._sx = self._sy = self._rx = self._ry = 0.0
        self._base_rgb = (0.55, 0.88, 1.0)   # cyan; set red while locked

    def set_endpoints(self, sx, sy, rx, ry):
        self._sx, self._sy, self._rx, self._ry = sx, sy, rx, ry
        n = self.SEGMENTS
        r, g, b = self._base_rgb
        for i in range(n):
            t0 = i / n
            t1 = (i + 1) / n
            x0 = sx + (rx - sx) * t0
            y0 = sy + (ry - sy) * t0
            x1 = sx + (rx - sx) * t1
            y1 = sy + (ry - sy) * t1
            self._segs[i].points = [x0, y0, x1, y1]
            self._seg_colors[i].rgba = (r, g, b, self.BEAM_ALPHA * (1.0 - i / n))
        self._ring.circle = (rx, ry, self._r)
        self._dot.circle = (rx, ry, self._r * 0.28)

    def set_locked(self, locked: bool):
        if locked == self._locked:
            return
        self._locked = locked
        if locked:
            self._ring_color.rgba = (1.0, 0.35, 0.30, 1.0)
            self._ring.width = 3.0
            self._base_rgb = (1.0, 0.40, 0.35)
        else:
            self._ring_color.rgba = (0.55, 0.88, 1.0, 0.95)
            self._ring.width = 2.2
            self._base_rgb = (0.55, 0.88, 1.0)
        # Beam hue is re-applied from _base_rgb on the next set_endpoints (called
        # every frame), so segments pick up the new color with their fade intact.

    def show(self):
        self.opacity = 1.0
        if self._anim is None:
            anim = (Animation(a=0.55, duration=0.5, t="in_out_sine")
                    + Animation(a=0.98, duration=0.5, t="in_out_sine"))
            anim.repeat = True
            anim.start(self._ring_color)
            self._anim = anim

    def hide(self):
        self.opacity = 0.0
        if self._anim is not None:
            self._anim.cancel(self._ring_color)
            self._anim = None


class RangeLine(Widget):
    """A horizontal 'engagement line' drawn across the lane at the current
    weapon's max reach. Its Y tweens (via the `line_y` NumericProperty) when the
    weapon — hence range — changes, so the player can read how far their shots
    reach. Drawn in ``canvas`` like the other HUD auras.

    Animating a Kivy NumericProperty (not a plain attribute) is what lets
    `Animation(line_y=...)` work — mirrors the gate `emph_scale` pattern.
    """

    line_y = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        with self.canvas:
            self._glow_color = Color(1.0, 0.85, 0.30, 0.18)
            self._glow = Line(width=6.0)
            self._line_color = Color(1.0, 0.88, 0.40, 0.85)
            self._line = Line(width=2.0)
        self._x1 = 0.0
        self._x2 = 0.0
        self._anim = None
        self.bind(line_y=lambda *_: self._redraw())

    def _redraw(self):
        y = self.line_y
        self._glow.points = [self._x1, y, self._x2, y]
        self._line.points = [self._x1, y, self._x2, y]

    def set_line(self, x1, x2, y, animate=True):
        self._x1, self._x2 = x1, x2
        if animate and self.opacity > 0.0 and y != self.line_y:
            if self._anim is not None:
                self._anim.cancel(self)
            self._anim = Animation(line_y=y, duration=0.18, t="out_quad")
            self._anim.start(self)
        else:
            self.line_y = y
            self._redraw()   # ensure redraw even if the value didn't change

    def show(self):
        self.opacity = 1.0

    def hide(self):
        self.opacity = 0.0


class ParticleBurst(Widget):
    """Single-shot hit-burst placeholder. Real particle pool comes in M11."""
    def __init__(self, pos, color=(1, 1, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        with self.canvas:
            Color(*color)
            Ellipse(pos=(pos[0] - 6, pos[1] - 6), size=(12, 12))
