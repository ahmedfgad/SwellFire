"""GameScreen — M4 auto-scroll world + hero + free-drag-with-lane-gravity input.

What M4 lands:
    * The world scrolls forward automatically at SCROLL_SPEED.
    * The hero is a single atlas-backed widget that bobs while running.
    * Touch / mouse drag steers the hero horizontally within the road.
    * `lane_gravity_target()` is in place so M7's gate spawner can drop
      gate-slot X positions in, and the hero will soft-snap toward the
      nearer slot when free-drag isn't actively in progress.
    * Distance counter + debug FPS overlay.

Not yet here (later milestones, each leaves a runnable build):
    * Enemies / projectiles / squad      [M5-M8]
    * Gates                              [M7]
    * Boss waves + win condition         [M10]
    * Networked / autoplay overlay       [M12-M13]
"""

from __future__ import annotations

import math

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line
from kivy.metrics import sp, dp
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import graphics
import levels
import ui


# --- gameplay constants ---------------------------------------------------

SCROLL_SPEED_PX_PER_SEC = 360.0     # forward scroll rate (visual + distance)
HERO_W = 64.0
HERO_H = 80.0
HERO_BOTTOM_FRAC = 0.16             # hero stays this fraction up from the road floor
LANE_GRAVITY_STRENGTH = 6.0         # per-second pull rate toward nearest lane
LANE_GRAVITY_RADIUS_PX = 80.0       # only engages within this distance of a lane center
N_STRIPES = 14                      # dashed centerline stripes
STRIPE_LENGTH = 36.0                # px


def lane_gravity_target(current_x: float, lane_centers: list[float], dt: float,
                        strength: float = LANE_GRAVITY_STRENGTH,
                        radius: float = LANE_GRAVITY_RADIUS_PX) -> float:
    """Soft-snap `current_x` toward the nearest lane center within `radius`.

    Frame-rate independent via `1 - exp(-strength * dt)`. With an empty
    `lane_centers` list (M4: gates land in M7), this is a no-op — that's
    intentional so the GameScreen can call it every frame regardless.
    """
    if not lane_centers:
        return current_x
    nearest = min(lane_centers, key=lambda lc: abs(lc - current_x))
    if abs(nearest - current_x) > radius:
        return current_x
    factor = 1.0 - math.exp(-strength * dt)
    return current_x + (nearest - current_x) * factor


# --- the gameplay screen --------------------------------------------------

class GameScreen(ui.StyledScreen):
    """Auto-scrolling level screen."""

    theme_world = 1

    def build(self):
        # Runtime state.
        self._update_event = None
        self._atlas = None
        self.hero: graphics.AtlasSprite | None = None
        self.distance = 0.0
        self._stripe_ys: list[float] = []
        # Drag tracking
        self._dragging = False
        self._drag_origin_touch_x = 0.0
        self._drag_origin_hero_x = 0.0
        self._hero_target_x = 0.0
        # Lane centers (M7 fills these per spawned gate pair).
        self.lane_centers: list[float] = []

        # The "stage" is the road surface area the hero runs in. It's narrower
        # than the screen so left/right margins read as background scenery.
        self.stage = Widget(
            size_hint=(0.66, 1.0),
            pos_hint={"center_x": 0.5, "y": 0},
        )
        self.root_layout.add_widget(self.stage)

        with self.stage.canvas.before:
            # Road surface — a darkened band.
            Color(0.08, 0.10, 0.16, 0.78)
            self._road = Rectangle()

        with self.stage.canvas:
            # Side rails.
            Color(1, 1, 1, 0.55)
            self._left_rail = Line(width=2.0)
            self._right_rail = Line(width=2.0)
            # Dashed centerline (N stripes that scroll).
            Color(1, 1, 1, 0.30)
            self._stripes = [Line(width=2.6) for _ in range(N_STRIPES)]

        self.stage.bind(pos=self._layout_stage, size=self._layout_stage)

        # Title strip at top
        self.title_label = Label(
            text="", font_size=sp(18), bold=True, color=(1, 0.88, 0.2, 1),
            halign="center", valign="middle",
            size_hint=(0.6, 0.06), pos_hint={"center_x": 0.5, "top": 0.99},
        )
        self.title_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.root_layout.add_widget(self.title_label)

        # HUD (distance + hero X)
        self.hud_label = Label(
            text="", font_size=sp(15), bold=True, color=(1, 1, 1, 0.92),
            halign="left", valign="middle", markup=False,
            size_hint=(0.45, 0.06), pos_hint={"x": 0.02, "top": 0.92},
        )
        self.hud_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.root_layout.add_widget(self.hud_label)

        # Debug overlay (FPS + frame time)
        self.debug = graphics.DebugOverlay(
            size_hint=(0.4, 0.05), pos_hint={"x": 0.02, "top": 0.86},
        )
        self.root_layout.add_widget(self.debug)

        # Back button (bottom right)
        self.back_btn = ui.StyledButton(
            text="Back", bg=[0.45, 0.45, 0.5, 1], font_size=sp(16),
            size_hint=(0.14, 0.08), pos_hint={"right": 0.98, "y": 0.03},
        )
        self.back_btn.bind(on_release=lambda *_: self._exit())
        self.root_layout.add_widget(self.back_btn)

    # --- layout ----------------------------------------------------------

    def _layout_stage(self, *_):
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        self._road.pos = (sx, sy)
        self._road.size = (sw, sh)
        self._left_rail.points = [sx, sy, sx, sy + sh]
        self._right_rail.points = [sx + sw, sy, sx + sw, sy + sh]
        # Initialize / resize stripe-Y array.
        if len(self._stripe_ys) != N_STRIPES or sh <= 0:
            spacing = sh / N_STRIPES if sh > 0 else 0.0
            self._stripe_ys = [sy + i * spacing for i in range(N_STRIPES)]
        self._paint_stripes()

    def _paint_stripes(self):
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        mid_x = sx + sw * 0.5
        half = STRIPE_LENGTH * 0.5
        for i, line in enumerate(self._stripes):
            y = self._stripe_ys[i]
            line.points = [mid_x, y - half, mid_x, y + half]

    # --- lifecycle -------------------------------------------------------

    def on_enter(self):
        running = ui.app()
        # Music + theme per-level for single-player; world 1 for multiplayer.
        if running.current_mode == "single" and running.current_level:
            world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
            theme = levels.get_world(world)
            self.bg.set_theme(theme)
            running.audio.play_level_music(world)
            self.title_label.text = "World {} - {}     Level {}".format(
                world, theme["name"], running.current_level)
        else:
            running.audio.play_level_music(1)
            self.title_label.text = "Multiplayer Versus     ({})".format(running.current_mode)

        # Load atlas lazily (first level entry only).
        if self._atlas is None:
            png_path, json_path = graphics.find_atlas("stress")
            self._atlas = graphics.SpriteAtlas(png_path, json_path)

        # Spawn the hero widget into the stage.
        if self.hero is None:
            self.hero = graphics.AtlasSprite(
                self._atlas, "runner_blue",
                size_hint=(None, None), size=(HERO_W, HERO_H),
            )
            self.stage.add_widget(self.hero)

        # Stage might be size 0 right after on_enter; do the actual reset on
        # the next frame so positions are real.
        Clock.schedule_once(self._reset, 0)

    def on_leave(self):
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        if self.hero is not None and self.hero.parent:
            self.hero.parent.remove_widget(self.hero)
        self.hero = None
        self._dragging = False

    def _reset(self, _dt):
        self.distance = 0.0
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        if self.hero is not None:
            hero_cx = sx + sw * 0.5
            self.hero.center_x = hero_cx
            self.hero.y = sy + sh * HERO_BOTTOM_FRAC
            self._hero_target_x = hero_cx
        if self._update_event is None:
            self._update_event = Clock.schedule_interval(self._update, 1 / 60.0)

    # --- per-frame update -------------------------------------------------

    def _update(self, dt):
        self.distance += SCROLL_SPEED_PX_PER_SEC * dt

        sx, sy = self.stage.pos
        sw, sh = self.stage.size

        # 1. Scroll the dashed centerline stripes downward (visual sense of
        #    moving forward in a top-down view).
        if sh > 0:
            drop = SCROLL_SPEED_PX_PER_SEC * dt
            for i in range(len(self._stripe_ys)):
                self._stripe_ys[i] -= drop
                while self._stripe_ys[i] < sy:
                    self._stripe_ys[i] += sh
            self._paint_stripes()

        # 2. Hero X: drag input + lane gravity. When the player isn't
        #    actively dragging, the hero's X relaxes toward the nearest
        #    lane center (empty list in M4 = pure free positioning).
        if self.hero is not None:
            target = self._hero_target_x
            if not self._dragging:
                target = lane_gravity_target(target, self.lane_centers, dt)
                self._hero_target_x = target
            min_x = sx + HERO_W * 0.5
            max_x = sx + sw - HERO_W * 0.5
            target = max(min_x, min(max_x, target))
            self._hero_target_x = target
            self.hero.center_x = target

            # Running bob — vertical sine driven by distance (so it looks
            # right even at varying frame rates).
            bob = math.sin(self.distance / 22.0) * 5.0
            self.hero.y = sy + sh * HERO_BOTTOM_FRAC + bob

        # 3. HUD + debug overlay.
        hero_cx = self.hero.center_x if self.hero is not None else 0.0
        self.hud_label.text = "Distance {:5.0f} m     Hero X {:.0f} px".format(
            self.distance, hero_cx,
        )
        self.debug.report_counts(distance=int(self.distance), lanes=len(self.lane_centers))

    # --- input ------------------------------------------------------------

    def on_touch_down(self, touch):
        # Let child widgets (Back button) consume the touch first.
        if super().on_touch_down(touch):
            return True
        # Drag starts when the touch lands in the stage and a hero exists.
        if self.hero is None or not self.stage.collide_point(*touch.pos):
            return False
        self._dragging = True
        self._drag_origin_touch_x = touch.x
        self._drag_origin_hero_x = self.hero.center_x
        self._hero_target_x = self.hero.center_x
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        if not self._dragging or self.hero is None:
            return False
        delta = touch.x - self._drag_origin_touch_x
        self._hero_target_x = self._drag_origin_hero_x + delta
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._dragging = False
            return True
        return super().on_touch_up(touch)

    # --- exit -------------------------------------------------------------

    def _exit(self):
        running = ui.app()
        if running.mp_net is not None:
            try:
                running.mp_net.send_leave()
            except Exception:
                pass
            running.mp_net.stop()
            running.mp_net = None
        running.go("menu")
