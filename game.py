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
import random

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line
from kivy.metrics import sp, dp
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import entities
import gates
import graphics
import levels
import ui
import weapons


# --- gameplay constants ---------------------------------------------------

SCROLL_SPEED_PX_PER_SEC = 360.0     # forward scroll rate (visual + distance)
HERO_W = 64.0
HERO_H = 80.0
HERO_BOTTOM_FRAC = 0.16             # hero stays this fraction up from the road floor
LANE_GRAVITY_STRENGTH = 6.0         # per-second pull rate toward nearest lane
LANE_GRAVITY_RADIUS_PX = 80.0       # only engages within this distance of a lane center
N_STRIPES = 14                      # dashed centerline stripes
STRIPE_LENGTH = 36.0                # px
ENEMY_POOL_CAPACITY = 200           # M5: 50 typical, stress to 200
PROJECTILE_POOL_CAPACITY = 500      # M8: squad of 100 at high fire rate
PARTICLE_POOL_CAPACITY = 500        # M8: kills + gate pickups + attrition bursts
GRID_CELL_PX = 100.0                # spatial-grid cell size (broad-phase)
MUZZLE_OFFSET_Y = HERO_H * 0.55     # spawn projectiles roughly from the gun
HERO_FRAME_NAME = "runner_blue"
DEFAULT_WEAPON_ID = "pistol"
MAX_SQUAD = 100                     # cap for squad_count; squad pool sized to MAX_SQUAD-1
ATTRITION_ZONE_HALF_W = 170.0       # half-width of the squad-contact zone (px)
ATTRITION_FRONT_OFFSET = HERO_H * 0.35   # how far above hero's center the squad's "front line" sits


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
        # Enemy systems (M5).
        self.enemy_pool: graphics.EntityPool | None = None
        self.enemy_controller: entities.EnemyController | None = None
        self.enemy_spawner: entities.EnemySpawner | None = None
        self.enemy_renderer: graphics.BatchedRenderer | None = None
        # Projectile / particle / shooting systems (M6).
        self.projectile_pool: graphics.EntityPool | None = None
        self.projectile_controller: entities.ProjectileController | None = None
        self.projectile_renderer: graphics.BatchedRenderer | None = None
        self.particle_pool: graphics.EntityPool | None = None
        self.particle_controller: entities.ParticleController | None = None
        self.particle_renderer: graphics.BatchedRenderer | None = None
        self.grid = entities.SpatialGrid(GRID_CELL_PX)
        self.current_weapon_id = DEFAULT_WEAPON_ID
        self._fire_cooldown = 0.0
        self._fire_rng = random.Random()
        self.kills_total = 0
        # Gates + squad (M7 + M8).
        self.gate_layer: Widget | None = None
        self.gate_controller: gates.GateController | None = None
        self.gate_spawner: gates.GateSpawner | None = None
        self.squad_count = 1
        self.squad_pool: graphics.EntityPool | None = None
        self.squad_controller: entities.SquadController | None = None
        self.squad_renderer: graphics.BatchedRenderer | None = None
        self.attrition_total = 0
        # Keyboard binding handle so on_leave can detach cleanly.
        self._key_handler = None

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

        # Pools + renderers, in draw order: enemy (back) → projectile → particle → hero (front).
        if self.enemy_pool is None:
            self.enemy_pool = graphics.EntityPool(ENEMY_POOL_CAPACITY, self._atlas)
            self.enemy_controller = entities.EnemyController(self.enemy_pool)
            self.enemy_spawner = entities.EnemySpawner(self.enemy_controller, self._atlas)
            self.enemy_renderer = graphics.BatchedRenderer(
                self.enemy_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.enemy_renderer)

        if self.projectile_pool is None:
            self.projectile_pool = graphics.EntityPool(PROJECTILE_POOL_CAPACITY, self._atlas)
            self.projectile_controller = entities.ProjectileController(self.projectile_pool)
            self.projectile_renderer = graphics.BatchedRenderer(
                self.projectile_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.projectile_renderer)

        if self.particle_pool is None:
            self.particle_pool = graphics.EntityPool(PARTICLE_POOL_CAPACITY, self._atlas)
            self.particle_controller = entities.ParticleController(self.particle_pool)
            self.particle_renderer = graphics.BatchedRenderer(
                self.particle_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.particle_renderer)

        # Gate layer lives under the hero so the hero appears "passing through".
        if self.gate_layer is None:
            self.gate_layer = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
            self.stage.add_widget(self.gate_layer)
            self.gate_controller = gates.GateController(self.gate_layer)
            self.gate_spawner = gates.GateSpawner(self.gate_controller)

        # Squad follower pool (M8). Capacity = MAX_SQUAD - 1 since the hero is its own widget.
        if self.squad_pool is None:
            self.squad_pool = graphics.EntityPool(MAX_SQUAD - 1, self._atlas)
            self.squad_controller = entities.SquadController(self.squad_pool)
            self.squad_renderer = graphics.BatchedRenderer(
                self.squad_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.squad_renderer)

        if self.hero is None:
            self.hero = graphics.AtlasSprite(
                self._atlas, HERO_FRAME_NAME,
                size_hint=(None, None), size=(HERO_W, HERO_H),
            )
            self.stage.add_widget(self.hero)

        # Keyboard input for weapon swap (1..4 select; W cycles).
        if self._key_handler is None:
            self._key_handler = self._on_key
            Window.bind(on_key_down=self._key_handler)

        # Reset shooting + squad state.
        self.current_weapon_id = DEFAULT_WEAPON_ID
        self._fire_cooldown = 0.0
        self.kills_total = 0
        self.squad_count = 1
        self.attrition_total = 0
        if self.squad_controller is not None:
            self.squad_controller.sync_to_count(0)   # hero alone at level start
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_spawner is not None:
            # Reset the spawner so a fresh level starts past its first interval.
            self.gate_spawner._next_distance = 400.0  # noqa: SLF001 — first-spawn distance
        self.lane_centers = []

        # Stage might be size 0 right after on_enter; do the actual reset on
        # the next frame so positions are real.
        Clock.schedule_once(self._reset, 0)

    def on_leave(self):
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        if self._key_handler is not None:
            Window.unbind(on_key_down=self._key_handler)
            self._key_handler = None
        for renderer in (self.enemy_renderer, self.projectile_renderer,
                         self.particle_renderer, self.squad_renderer):
            if renderer is not None and renderer.parent:
                renderer.parent.remove_widget(renderer)
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_layer is not None and self.gate_layer.parent:
            self.gate_layer.parent.remove_widget(self.gate_layer)
        if self.hero is not None and self.hero.parent:
            self.hero.parent.remove_widget(self.hero)
        self.enemy_pool = None
        self.enemy_controller = None
        self.enemy_spawner = None
        self.enemy_renderer = None
        self.projectile_pool = None
        self.projectile_controller = None
        self.projectile_renderer = None
        self.particle_pool = None
        self.particle_controller = None
        self.particle_renderer = None
        self.squad_pool = None
        self.squad_controller = None
        self.squad_renderer = None
        self.gate_layer = None
        self.gate_controller = None
        self.gate_spawner = None
        self.lane_centers = []
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

        # 3. Enemies: spawner ticks → enemies updated.
        x_min = sx
        y_min = sy
        x_max = sx + sw
        y_max = sy + sh
        if (self.enemy_controller is not None
                and self.enemy_spawner is not None
                and self.hero is not None):
            self.enemy_spawner.tick(dt, x_min, y_min, x_max, y_max)
            self.enemy_controller.update(dt, self.hero.center_x,
                                         x_min, y_min, x_max, y_max)

        # 3b. Gates: spawner emits a new pair when distance passes the next
        # interval; controller scrolls all gates + checks pass-through.
        if (self.gate_controller is not None
                and self.gate_spawner is not None
                and self.hero is not None):
            self.gate_spawner.tick(self.distance, x_min, x_max, y_max)
            self.gate_controller.update(
                dt, SCROLL_SPEED_PX_PER_SEC,
                self.hero.center_x, self.hero.center_y,
                self._on_apply_gate,
            )
            # Lane gravity follows the active pair's gates.
            self.lane_centers = self.gate_controller.active_lane_centers(
                self.hero.center_y,
            )

        # 4. Squad: sync pool to squad_count, position followers in formation.
        if (self.squad_controller is not None
                and self.hero is not None):
            self.squad_controller.sync_to_count(self.squad_count - 1)
            self.squad_controller.update_formation(
                self.hero.center_x, self.hero.center_y,
            )

        # 5. Auto-fire: cooldown → fire_from_positions(hero + squad) → collision → particles.
        if (self.hero is not None
                and self.projectile_controller is not None
                and self.particle_controller is not None
                and self.enemy_controller is not None
                and self.squad_pool is not None):
            weapon = weapons.get(self.current_weapon_id)
            self._fire_cooldown -= dt
            if self._fire_cooldown <= 0.0:
                target = entities.find_nearest_enemy(
                    self.hero.center_x, self.hero.center_y, self.enemy_controller,
                )
                if target >= 0:
                    ep = self.enemy_pool
                    target_x = ep.cx[target]
                    target_y = ep.cy[target]
                    # Shooter positions: hero muzzle + every active follower's muzzle.
                    positions = [(self.hero.center_x, self.hero.center_y + MUZZLE_OFFSET_Y)]
                    sp = self.squad_pool
                    sc = self.squad_controller
                    for i in range(sp.capacity):
                        if sp.active[i]:
                            positions.append((sp.cx[i], sp.cy[i] + sc.MUZZLE_OFFSET_Y))
                    entities.fire_from_positions(
                        positions, target_x, target_y, weapon,
                        self.projectile_controller, self._fire_rng,
                    )
                    self._fire_cooldown = 1.0 / weapon.fire_rate

            self.projectile_controller.update(dt, x_min, y_min, x_max, y_max)

            # Projectile vs enemy collisions; each kill bursts particles.
            def _on_kill(hit_x, hit_y, _pc=self.particle_controller, _rng=self._fire_rng):
                _pc.burst(hit_x, hit_y, count=6, speed=240.0, ttl=0.35,
                          size=10.0, frame="particle", rng=_rng)
            kills = entities.resolve_projectile_collisions(
                self.projectile_controller, self.enemy_controller, self.grid, _on_kill,
            )
            self.kills_total += kills

            # Squad attrition: enemies that pierce the squad's front line cost one runner each.
            def _on_loss(hit_x, hit_y, _self=self, _rng=self._fire_rng):
                _self.squad_count = max(1, _self.squad_count - 1)
                _self.attrition_total += 1
                if _self.particle_controller is not None:
                    _self.particle_controller.burst(
                        hit_x, hit_y, count=8, speed=220.0, ttl=0.4,
                        size=10.0, frame="particle", rng=_rng,
                    )
                running = ui.app()
                running.audio.play_sfx("damage")
            entities.resolve_squad_attrition(
                self.enemy_controller,
                self.hero.center_x, self.hero.center_y,
                ATTRITION_ZONE_HALF_W,
                self.hero.center_y + ATTRITION_FRONT_OFFSET,
                _on_loss,
            )

            self.particle_controller.update(dt)

        # 6. Mesh rebuilds (one canvas write per renderer per frame).
        if self.enemy_renderer is not None:
            self.enemy_renderer.rebuild()
        if self.projectile_renderer is not None:
            self.projectile_renderer.rebuild()
        if self.particle_renderer is not None:
            self.particle_renderer.rebuild()
        if self.squad_renderer is not None:
            self.squad_renderer.rebuild()

        # 7. HUD + debug overlay.
        hero_cx = self.hero.center_x if self.hero is not None else 0.0
        enemy_count = self.enemy_pool.active_count if self.enemy_pool is not None else 0
        weapon_name = weapons.get(self.current_weapon_id).name
        self.hud_label.text = ("Distance {:5.0f} m     Squad {}     "
                               "Weapon: {}     Kills {}").format(
            self.distance, self.squad_count, weapon_name, self.kills_total,
        )
        gates_passed = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed = self.gate_controller.missed_total if self.gate_controller else 0
        proj_active = self.projectile_pool.active_count if self.projectile_pool else 0
        part_active = self.particle_pool.active_count if self.particle_pool else 0
        squad_active = self.squad_pool.active_count if self.squad_pool else 0
        self.debug.report_counts(
            dist=int(self.distance),
            enemies=enemy_count, kills=self.kills_total,
            gates=gates_passed, missed=gates_missed,
            squad=squad_active + 1, lost=self.attrition_total,
            projectiles=proj_active, particles=part_active,
        )

    # --- gate effect application -----------------------------------------

    def _on_apply_gate(self, gate) -> None:
        """Apply a passed gate's effect: mutate squad_count or swap weapon."""
        if gate.op == gates.OP_MUL:
            self.squad_count = min(MAX_SQUAD, max(1, self.squad_count * int(gate.value)))
        elif gate.op == gates.OP_ADD:
            self.squad_count = min(MAX_SQUAD, self.squad_count + int(gate.value))
        elif gate.op == gates.OP_SUB:
            self.squad_count = max(1, self.squad_count - int(gate.value))
        elif gate.op == gates.OP_WEAPON:
            if gate.value in weapons.WEAPONS:
                self.current_weapon_id = gate.value
                self._fire_cooldown = 0.0
        # Audio + particle burst at the hero so the pickup reads.
        running = ui.app()
        running.audio.play_sfx("gate_pickup")
        if self.particle_controller is not None and self.hero is not None:
            self.particle_controller.burst(
                self.hero.center_x, self.hero.center_y + HERO_H * 0.3,
                count=10, speed=260.0, ttl=0.45, size=12.0,
                frame="particle", rng=self._fire_rng,
            )

    # --- weapon switching keyboard ---------------------------------------

    def _on_key(self, _window, _key, _scancode, codepoint, _modifier):
        if not codepoint:
            return False
        if codepoint == "w":
            self.current_weapon_id = weapons.next_id(self.current_weapon_id)
            self._fire_cooldown = 0.0
            return True
        if codepoint in ("1", "2", "3", "4"):
            new_id = weapons.by_index(int(codepoint) - 1)
            if new_id is not None:
                self.current_weapon_id = new_id
                self._fire_cooldown = 0.0
                return True
        return False

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
