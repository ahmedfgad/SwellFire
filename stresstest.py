"""M3 rendering POC — bounce 500 atlas-textured sprites in a single Mesh.

Reached from Settings > Rendering Test (debug). Exists to prove the hybrid
Mesh + Widgets renderer can sustain the entity count gameplay needs before
M4+ start spawning real enemies / projectiles / runners.

How it tests what:
    - One `graphics.SpriteAtlas` is loaded from assets/atlases/stress.{png,json}.
    - 500 entities are spawned into an `EntityPool` with random positions /
      velocities / frame ids.
    - Each frame, positions update, world-edge bouncing applies, and
      `BatchedRenderer.rebuild()` repacks the vertex array and pushes it
      to the single `Mesh` instruction.
    - `DebugOverlay` reports FPS + active entity count at 5 Hz.

Pass criteria (see plan M3):
    * Linux desktop:   >= 60 FPS sustained with 500 active entities.
    * Mid-range Android (debug build):   >= 45 FPS, target 60.
"""

from __future__ import annotations

import random

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import sp, dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

import graphics
import ui


DEFAULT_ENTITY_COUNT = 500
SPRITE_SIZE_PX = 24
FRAME_NAMES = ("runner_blue", "enemy_red", "projectile", "particle")


class StressTestScreen(ui.StyledScreen):
    """Stress-test arena that drives BatchedRenderer at 60 Hz."""
    theme_world = 6     # cosmos palette so the debug overlay reads cleanly

    def build(self):
        # The bouncing entities live in the centre area. Top-left holds the
        # debug overlay, bottom-left the Back button.
        self.entity_count = DEFAULT_ENTITY_COUNT
        self._update_event = None
        self._atlas = None
        self._pool = None
        self._renderer = None

        # Stage area is a child Widget so we can size the bouncing region to
        # the screen (minus the HUD strip at the bottom) without coupling to
        # the StyledScreen's root_layout.
        self.stage = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        # A dim overlay over the gradient so the debug HUD has contrast.
        with self.stage.canvas.before:
            Color(0, 0, 0, 0.45)
            self._dim = Rectangle()
        self.stage.bind(pos=self._sync_dim, size=self._sync_dim)
        self.root_layout.add_widget(self.stage)

        # Title strip (small) so the screen reads as "this is the test", not
        # a black hole.
        self.title_label = Label(
            text="Rendering stress test", font_size=sp(20), bold=True,
            color=(1, 1, 1, 0.92),
            size_hint=(1, 0.08), pos_hint={"top": 1, "x": 0},
        )
        self.root_layout.add_widget(self.title_label)

        # Debug overlay (top-left).
        self.overlay = graphics.DebugOverlay(
            size_hint=(0.45, 0.07),
            pos_hint={"x": 0.01, "top": 0.91},
        )
        self.root_layout.add_widget(self.overlay)

        # Back button.
        self.back_btn = ui.StyledButton(
            text="Back", bg=[0.45, 0.45, 0.5, 1], font_size=sp(16),
            size_hint=(0.16, 0.08), pos_hint={"x": 0.02, "y": 0.03},
        )
        self.back_btn.bind(on_release=lambda *_: ui.app().go("settings"))
        self.root_layout.add_widget(self.back_btn)

    def _sync_dim(self, *_):
        self._dim.pos = self.stage.pos
        self._dim.size = self.stage.size

    # --- lifecycle --------------------------------------------------------

    def on_enter(self):
        # Audio: keep menu music going (the test is for visuals).
        running = ui.app()
        running.audio.play_menu_music()

        # Load atlas once.
        if self._atlas is None:
            png_path, json_path = graphics.find_atlas("stress")
            self._atlas = graphics.SpriteAtlas(png_path, json_path)

        # Build the pool + renderer.
        self._pool = graphics.EntityPool(self.entity_count, self._atlas)
        self._renderer = graphics.BatchedRenderer(
            self._pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )
        self.stage.add_widget(self._renderer)

        # Spawn after the stage has a non-zero size. Kivy resizes on the
        # next frame, so schedule the spawn one tick out.
        Clock.schedule_once(self._spawn_entities, 0)

    def on_leave(self):
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        # Drop the renderer + pool so leaving and re-entering starts fresh
        # (and so the bouncing entities don't survive a navigation away).
        if self._renderer is not None and self._renderer.parent:
            self._renderer.parent.remove_widget(self._renderer)
        self._renderer = None
        self._pool = None
        self.overlay.report_counts()

    # --- world setup ------------------------------------------------------

    def _spawn_entities(self, _dt):
        pool = self._pool
        renderer = self._renderer
        if pool is None or renderer is None:
            return
        w_px = max(64.0, float(renderer.width))
        h_px = max(64.0, float(renderer.height))
        x_offset = float(renderer.x)
        y_offset = float(renderer.y)
        size = float(SPRITE_SIZE_PX)
        # Speed range: ~50..200 px/sec so the screen looks alive.
        for _ in range(self.entity_count):
            cx = x_offset + random.uniform(size, w_px - size)
            cy = y_offset + random.uniform(size, h_px - size)
            angle = random.uniform(0, 6.28318)
            speed = random.uniform(50.0, 200.0)
            vx = speed * random.choice((-1, 1)) * abs(0.6 + 0.4 * random.random())
            vy = speed * random.choice((-1, 1)) * abs(0.6 + 0.4 * random.random())
            pool.spawn(cx, cy, vx, vy, size, size, random.choice(FRAME_NAMES))

        # First render so the screen isn't empty for one frame.
        renderer.rebuild()
        self.overlay.report_counts(entities=pool.active_count)
        # Start the 60 Hz update loop.
        if self._update_event is None:
            self._update_event = Clock.schedule_interval(self._update, 1 / 60.0)

    # --- per-frame update ------------------------------------------------

    def _update(self, dt):
        pool = self._pool
        renderer = self._renderer
        if pool is None or renderer is None:
            return

        cx = pool.cx
        cy = pool.cy
        vx = pool.vx
        vy = pool.vy
        hw = pool.hw
        hh = pool.hh
        active = pool.active

        x_min = float(renderer.x)
        y_min = float(renderer.y)
        x_max = x_min + float(renderer.width)
        y_max = y_min + float(renderer.height)

        for i in range(pool.capacity):
            if not active[i]:
                continue
            new_x = cx[i] + vx[i] * dt
            new_y = cy[i] + vy[i] * dt
            # Bounce off walls; clamp so a long dt doesn't push past the wall.
            if new_x - hw[i] < x_min:
                new_x = x_min + hw[i]
                vx[i] = -vx[i]
            elif new_x + hw[i] > x_max:
                new_x = x_max - hw[i]
                vx[i] = -vx[i]
            if new_y - hh[i] < y_min:
                new_y = y_min + hh[i]
                vy[i] = -vy[i]
            elif new_y + hh[i] > y_max:
                new_y = y_max - hh[i]
                vy[i] = -vy[i]
            cx[i] = new_x
            cy[i] = new_y

        renderer.rebuild()
        self.overlay.report_counts(entities=pool.active_count)
