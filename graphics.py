# GateRunner graphics.
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

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line, Mesh
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty


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
        from kivy.core.image import Image as CoreImage

        self._image = CoreImage(png_path, nocache=True)
        self.texture = self._image.texture
        # Pixel-art-style: nearest filtering keeps frames crisp at any scale.
        self.texture.min_filter = "nearest"
        self.texture.mag_filter = "nearest"

        with open(json_path) as f:
            meta = json.load(f)
        self.atlas_w = float(meta["atlas_width"])
        self.atlas_h = float(meta["atlas_height"])
        # name -> (u0, v0, u1, v1) where v=0 is the bottom of the texture.
        self._frames: dict[str, tuple[float, float, float, float]] = {}
        for name, rect in meta["frames"].items():
            x = float(rect["x"])
            y = float(rect["y"])
            w = float(rect["w"])
            h = float(rect["h"])
            u0 = x / self.atlas_w
            u1 = (x + w) / self.atlas_w
            # Flip y axis from PIL (top-left) to GL (bottom-left).
            v0 = 1.0 - (y + h) / self.atlas_h
            v1 = 1.0 - y / self.atlas_h
            self._frames[name] = (u0, v0, u1, v1)

    def frame(self, name: str) -> tuple[float, float, float, float]:
        return self._frames[name]

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
            if tint is not None:
                self._tint_color = Color(*tint)
            else:
                self._tint_color = None
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


class ParticleBurst(Widget):
    """Single-shot hit-burst placeholder. Real particle pool comes in M11."""
    def __init__(self, pos, color=(1, 1, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        with self.canvas:
            Color(*color)
            Ellipse(pos=(pos[0] - 6, pos[1] - 6), size=(12, 12))
