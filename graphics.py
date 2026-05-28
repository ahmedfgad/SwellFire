# GateRunner graphics — M1 scope.
#
# M1 provides only the bits ui.py needs at startup: a themed gradient
# `Background`, a `draw_star` canvas helper used by the level-select rating,
# and tiny placeholder sprite widgets so the (text-only) tutorial / guide can
# stand up small visual stand-ins for the runner, enemy, gate and projectile
# without crashing.
#
# The real Mesh-batched renderer with atlases lands in M3; everything below
# this comment is intentionally lo-fi and will be swapped wholesale.

import math
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line
from kivy.properties import NumericProperty, BooleanProperty


# --- gradient background ---------------------------------------------------

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


# --- five-pointed star (used by the level-select rating) -------------------

def draw_star(cx, cy, outer, color):
    """Add a filled 5-point star to the current canvas at (cx, cy)."""
    inner = outer * 0.45
    points = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = math.pi / 2 + i * math.pi / 5  # point up
        points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    Color(*color)
    Line(points=points + points[:2], width=1.4, close=True)
    # crude fill: a small ellipse — the M3 renderer replaces this with a triangle fan
    Ellipse(pos=(cx - outer * 0.55, cy - outer * 0.55),
            size=(outer * 1.1, outer * 1.1))


# --- placeholder sprite widgets --------------------------------------------
#
# Each is a simple colored shape so the guide screen and tutorial can show
# *something* without depending on the M3 Mesh renderer or final art. They
# share a no-op start() / stop() / hit_flash() so ui.py code that came from
# CoinTex keeps compiling unchanged after M3 swaps them out.

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
    """Stand-in for a single squad runner (full sprite lands in M3 + M14)."""
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


# Compatibility alias — the CoinTex-style screens reference PlayerSprite.
class PlayerSprite(RunnerSprite):
    pass


class EnemySprite(_PlaceholderSprite):
    """Stand-in for an enemy. M5 replaces with the real Mesh-batched enemy."""
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


# Compatibility alias — CoinTex-named.
class MonsterSprite(EnemySprite):
    mtype = NumericProperty(1)
    hp = NumericProperty(1)
    max_hp = NumericProperty(1)


class GateSprite(_PlaceholderSprite):
    """A single gate panel — full M7 implementation pairs two of these."""
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


# CoinTex carries Hazard/Coin/Freezer as gameplay sprites. GateRunner does not
# use them, but ui.GuideScreen's icon factory references the names — add thin
# placeholders so the guide screen stays paint-clean for M1.

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
