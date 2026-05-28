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

import boss as boss_module
import boosters
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
PICKUP_POOL_CAPACITY = 40           # in-level coin + double-coin spawns
PICKUP_COLLECT_RADIUS = 56.0        # px; hero auto-collects pickups within this
# Sub-linear firepower cap: above this many active shooters in the squad,
# only a rotating subset fires each shot. Keeps a 100-runner squad from
# trivializing late-world levels at 700 bullets/sec while still letting
# big squads absorb attrition. The cap value is tuned against the late-world
# enemy density — 22 keeps roughly 150 bullets/sec which lets W6 levels
# stay challenging at any squad size.
MAX_SHOOTERS_PER_SHOT = 22
GRID_CELL_PX = 100.0                # spatial-grid cell size (broad-phase)
MUZZLE_OFFSET_Y = HERO_H * 0.55     # spawn projectiles roughly from the gun
HERO_FRAME_NAME = "runner_blue"
DEFAULT_WEAPON_ID = "pistol"
MAX_SQUAD = 100                     # cap for squad_count; squad pool sized to MAX_SQUAD-1
ATTRITION_ZONE_HALF_W = 170.0       # half-width of the squad-contact zone (px)
ATTRITION_FRONT_OFFSET = HERO_H * 0.35   # how far above hero's center the squad's "front line" sits
MAX_GRENADES = 9                    # in-run cap; HUD shows current count
GRENADE_RADIUS = 520.0              # px; detonation kills every enemy within this
                                    # (sized to cover the full stage in front of the hero)
# Fractional coin rewards per archetype kill — accumulated via a remainder
# counter so common grunts contribute meaningfully over many kills without
# trivializing the shop. A run of ~70 grunt kills now pays ~21 coins
# (was 70). Tank kills still feel valuable.
COIN_PARTIAL_REWARD = {
    entities.TYPE_GRUNT:    0.30,
    entities.TYPE_SWARMER:  0.30,
    entities.TYPE_BOMBER:   0.70,
    entities.TYPE_SPLITTER: 0.60,
    entities.TYPE_TANK:     1.50,
}
# Gate pickup + level-end bonuses also reduced — coins now come primarily
# from in-level pickups (see pickup_controller).
COIN_REWARD_GATE = 1
COIN_BONUS_LEVEL_COMPLETE = 20
COIN_BONUS_PER_STAR = 10


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
        # In-level pickup system (coins + double-coin power-up).
        self.pickup_pool: graphics.EntityPool | None = None
        self.pickup_controller: entities.PickupController | None = None
        self.pickup_spawner: entities.PickupSpawner | None = None
        self.pickup_renderer: graphics.BatchedRenderer | None = None
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
        # Level config + result handling (M9).
        self.level_config: dict | None = None
        self.distance_goal = 0.0
        self._level_ended = False
        # Touch-HUD buttons (M11.5 follow-up). Initialized in build().
        self.grenade_btn = None
        self.shield_btn = None
        # Boss systems (M10).
        self.boss: boss_module.Boss | None = None
        self.boss_controller: boss_module.BossController | None = None
        self.boss_widget: boss_module.BossWidget | None = None
        self.boss_hp_bar: boss_module.BossHPBar | None = None
        # Booster inventory (M11.5). HUD-visible counters; keyboard shortcuts:
        #   G  — throw a grenade (clears nearby enemies, damages boss)
        #   S  — activate a shield (brief attrition immunity)
        self.grenade_count = 0
        self.shield_count = 0
        self.shield_active_until = 0.0     # game-time seconds; <= now = inactive
        # Screen shake (M11). The shake offset is applied to root_layout.pos
        # so the whole gameplay frame (stage + HUD) judders together.
        self.shake_intensity = 0.0
        self.shake_x = 0.0
        self.shake_y = 0.0
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

        # Bottom-left touch HUD: grenade + shield buttons. Visible during
        # gameplay; tap to fire/activate. Counts update every frame; greyed
        # out when the player has none.
        self.grenade_btn = ui.StyledButton(
            text="G 0", bg=[0.20, 0.80, 0.95, 1], font_size=sp(18),
            size_hint=(0.10, 0.10),
            pos_hint={"x": 0.02, "y": 0.03},
        )
        self.grenade_btn.bind(on_release=lambda *_: self._detonate_grenade())
        self.root_layout.add_widget(self.grenade_btn)

        self.shield_btn = ui.StyledButton(
            text="S 0", bg=[0.50, 0.85, 1.00, 1], font_size=sp(18),
            size_hint=(0.10, 0.10),
            pos_hint={"x": 0.14, "y": 0.03},
        )
        self.shield_btn.bind(on_release=lambda *_: self._activate_shield())
        self.root_layout.add_widget(self.shield_btn)

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
            cfg_preview = levels.get_level(running.current_level)
            if cfg_preview and cfg_preview.get("boss"):
                running.audio.play_boss_music()
            else:
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

        # Pickups (coins + double-coin) — own pool so they draw between
        # projectiles and gates, and so the renderer stays simple.
        if self.pickup_pool is None:
            self.pickup_pool = graphics.EntityPool(PICKUP_POOL_CAPACITY, self._atlas)
            self.pickup_controller = entities.PickupController(self.pickup_pool)
            self.pickup_spawner = entities.PickupSpawner(self.pickup_controller)
            self.pickup_renderer = graphics.BatchedRenderer(
                self.pickup_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.pickup_renderer)

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
        self._level_ended = False
        # Carry over the per-save booster balances into the run; level-end
        # writes back what's left so they persist between runs.
        #
        # The "free starter grenade" used to live here, but it produced a
        # stockpile (5-7 grenades) that made grenades feel like a regular
        # item rather than a rare panic button. The safety it provided is
        # now covered by the pity-gate floor (gates.GateSpawner) so the
        # player can recover from missed pairs without a freebie.
        running_app = ui.app()
        if running_app and running_app.state:
            self.grenade_count = running_app.state.get_booster_balance("grenade")
            self.shield_count = running_app.state.get_booster_balance("shield")
        else:
            self.grenade_count = 0
            self.shield_count = 0
        self.shield_active_until = 0.0
        self._run_time = 0.0
        # Coins earned during the run (kill remainder + gate pickup + in-level
        # coin pickups). Persisted to state.coins_balance in _end_level so a
        # partial run still pays the player for whatever they collected.
        self._coins_earned = 0
        self._coin_remainder = 0.0      # fractional remainder for kill rewards
        self.double_coin_until = 0.0    # in-run timer; coin rewards 2× while active
        if self.squad_controller is not None:
            self.squad_controller.sync_to_count(0)   # hero alone at level start
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_spawner is not None:
            # Reset the spawner so a fresh level starts past its first interval.
            self.gate_spawner._next_distance = 200.0  # noqa: SLF001 — first-spawn distance
        if self.pickup_spawner is not None:
            self.pickup_spawner.reset_per_level()
        self.lane_centers = []

        # Apply the per-level config now that pools + spawners exist.
        self._apply_level_config()

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
                         self.particle_renderer, self.squad_renderer,
                         self.pickup_renderer):
            if renderer is not None and renderer.parent:
                renderer.parent.remove_widget(renderer)
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_layer is not None and self.gate_layer.parent:
            self.gate_layer.parent.remove_widget(self.gate_layer)
        self._teardown_boss()
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
        self.pickup_pool = None
        self.pickup_controller = None
        self.pickup_spawner = None
        self.pickup_renderer = None
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
        # Reset shake so a fresh level doesn't inherit the previous one's kick.
        self.shake_intensity = 0.0
        self.shake_x = 0.0
        self.shake_y = 0.0
        self.root_layout.pos = (0, 0)
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        if self.hero is not None:
            hero_cx = sx + sw * 0.5
            self.hero.center_x = hero_cx
            self.hero.y = sy + sh * HERO_BOTTOM_FRAC
            self._hero_target_x = hero_cx
        if self._update_event is None:
            self._update_event = Clock.schedule_interval(self._update, 1 / 60.0)

    def _apply_level_config(self) -> None:
        """Look up the per-level config and push it to the spawners.

        Boss levels (M10) disable the regular enemy + gate spawners — the
        boss controller handles all enemy spawning, and the player gets a
        head-start squad/weapon so the fight isn't pistol+1.
        """
        running = ui.app()
        cfg = levels.get_level(running.current_level) if running.current_level else None
        # Multiplayer (versus) doesn't go through the level table; use a
        # gentle baseline so the screen still runs end-to-end.
        if cfg is None:
            cfg = levels.get_level(1)
        self.level_config = cfg
        self.distance_goal = float(cfg["distance_goal"])
        is_boss = bool(cfg.get("boss"))

        if self.enemy_spawner is not None:
            if is_boss:
                # Boss controls all spawning during the fight.
                self.enemy_spawner.interval = 0.0
            else:
                self.enemy_spawner.interval = cfg["enemy_spawn_interval"]
            self.enemy_spawner.enemy_speed = cfg["enemy_speed"]
            self.enemy_spawner.enemy_hp = cfg["enemy_hp"]
            self.enemy_spawner.chase_strength_min = cfg["enemy_chase_min"]
            self.enemy_spawner.chase_strength_max = cfg["enemy_chase_max"]
            # Per-world enemy archetype mix. Boss levels keep the default
            # grunt-only table since the boss controller hard-codes its
            # minions.
            if is_boss:
                self.enemy_spawner.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
                # Boss controls all spawning — no intro delay needed; the
                # opening volley is the threat the player sees immediately.
                self.enemy_spawner.intro_delay = 0.0
            else:
                self.enemy_spawner.spawn_table = [
                    (entities.TYPE_NAMES[name], weight)
                    for name, weight in cfg["allowed_enemy_types"]
                ]
                # World-scaling intro delay: higher worlds get more breathing
                # room because their base spawn rate and enemy speed would
                # otherwise overwhelm the starting squad before the player
                # can react to the first gate. Verified by the difficulty
                # sim against passive (must still fail) and greedy (must
                # survive long enough to pick gates).
                world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
                self.enemy_spawner.intro_delay = 1.5 + 0.5 * (world - 1)
            self.enemy_spawner.reset_per_level()

        if self.gate_spawner is not None:
            if is_boss:
                # Boss levels keep gates available but sparser: ~5 pairs over
                # the whole fight, so the player has rescue options without
                # the gate-stream trivializing the fight.
                self.gate_spawner.interval_px = 1500.0
                self.gate_spawner.max_grenade_gates = 1
            else:
                self.gate_spawner.interval_px = cfg["gate_interval_px"]
                self.gate_spawner.max_grenade_gates = int(cfg.get("max_grenade_gates", 0))
            self.gate_spawner.allowed_ops = list(cfg["allowed_ops"])
            self.gate_spawner.allowed_weapons = list(cfg["allowed_weapons"])
            self.gate_spawner.reset_per_level()

        # Boss spawn / teardown.
        self._teardown_boss()
        if is_boss:
            self._spawn_boss(cfg)
            # Head-start squad + weapon so the fight has weight.
            self.squad_count = int(cfg.get("starting_squad", 1))
            self.current_weapon_id = cfg.get("starting_weapon", DEFAULT_WEAPON_ID)
            self._fire_cooldown = 0.0
        else:
            # Non-boss levels also get a (smaller) starting squad now —
            # `levels.starting_squad` scales 1→6 across W1→W6 so the player
            # can survive the intro before reaching the first gate. Plus
            # the persistent shop bonus (state.squad_bonus) so a player
            # who invested coins gets a tangible boost.
            base = int(cfg.get("starting_squad", 1))
            running_app = ui.app()
            bonus = running_app.state.squad_bonus if (running_app and running_app.state) else 0
            self.squad_count = max(1, base + bonus)
            # Starting weapon: use the player's highest-tier purchased weapon
            # (state.starting_weapon — "pistol" by default). The shop
            # upgrades this for every non-boss level once bought.
            if running_app and running_app.state:
                self.current_weapon_id = running_app.state.starting_weapon

    def _spawn_boss(self, cfg: dict) -> None:
        if self._atlas is None or self.stage is None:
            return
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        boss_w = 160.0
        boss_h = 160.0
        boss_cx = sx + sw * 0.5
        boss_cy = sy + sh * 0.82
        self.boss = boss_module.Boss(
            max_hp=int(cfg.get("boss_hp", 100)),
            cx=boss_cx, cy=boss_cy,
            width=boss_w, height=boss_h,
        )
        self.boss_widget = boss_module.BossWidget(
            self.boss, self._atlas,
            size_hint=(None, None), size=(boss_w, boss_h),
        )
        self.stage.add_widget(self.boss_widget)
        self.boss_hp_bar = boss_module.BossHPBar(
            self.boss,
            size_hint=(0.6, None), height=dp(22),
            pos_hint={"center_x": 0.5, "top": 0.99},
        )
        self.root_layout.add_widget(self.boss_hp_bar)
        # Controller after widgets so an opening volley can render this frame.
        self.boss_controller = boss_module.BossController(
            self.boss, self.enemy_controller,
            minion_hp=int(cfg.get("boss_minion_hp", 1)),
        )
        # Fire one volley now so the player sees an immediate threat.
        self.boss_controller.opening_volley(
            self.hero.center_x if self.hero else boss_cx,
            sx, sy + sh,
        )

    def _teardown_boss(self) -> None:
        if self.boss_widget is not None and self.boss_widget.parent:
            self.boss_widget.parent.remove_widget(self.boss_widget)
        if self.boss_hp_bar is not None and self.boss_hp_bar.parent:
            self.boss_hp_bar.parent.remove_widget(self.boss_hp_bar)
        self.boss = None
        self.boss_widget = None
        self.boss_hp_bar = None
        self.boss_controller = None

    # --- per-frame update -------------------------------------------------

    # --- M11 polish helpers ----------------------------------------------

    SHAKE_DECAY_PER_SEC = 9.0
    SHAKE_CAP = 18.0

    def _add_shake(self, amount: float) -> None:
        """Bump the shake intensity. Capped so several events in one frame
        don't compound into a window-shattering shake."""
        self.shake_intensity = min(self.SHAKE_CAP,
                                   self.shake_intensity + float(amount))

    def _step_shake(self, dt: float) -> None:
        """Decay shake; pick a random offset within the current intensity."""
        if self.shake_intensity <= 0.05:
            self.shake_intensity = 0.0
            self.shake_x = 0.0
            self.shake_y = 0.0
        else:
            self.shake_x = self._fire_rng.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = self._fire_rng.uniform(-self.shake_intensity, self.shake_intensity)
            # Exponential decay so it feels like a kick rather than a tremor.
            import math as _math
            self.shake_intensity *= _math.exp(-self.SHAKE_DECAY_PER_SEC * dt)
        # Translate the entire screen contents.
        self.root_layout.pos = (self.shake_x, self.shake_y)

    def _spawn_muzzle_polish(self, sx: float, sy: float) -> None:
        """Stationary bright flash + one slow upward smoke wisp."""
        pc = self.particle_controller
        if pc is None:
            return
        # Bright yellow flash — large + brief so it reads as a pop.
        pc.spawn_one(sx, sy, 0.0, 0.0, 22.0, 0.07, "particle")
        # Smoke wisp drifting up.
        smoke_vx = self._fire_rng.uniform(-25.0, 25.0)
        smoke_vy = self._fire_rng.uniform(45.0, 95.0)
        pc.spawn_one(sx, sy + 6.0, smoke_vx, smoke_vy, 10.0, 0.55, "particle")

    def _spawn_death_polish(self, hit_x: float, hit_y: float) -> None:
        """Yellow sparks + red body fragments on enemy death."""
        pc = self.particle_controller
        if pc is None:
            return
        rng = self._fire_rng
        # Hit sparks (yellow).
        pc.burst(hit_x, hit_y, count=4, speed=240.0, ttl=0.32,
                 size=10.0, frame="particle", rng=rng)
        # Body fragments (red shards reusing the enemy_red atlas frame).
        # Smaller + slower than the sparks so they feel like meat, not sparkle.
        pc.burst(hit_x, hit_y, count=5, speed=160.0, ttl=0.48,
                 size=14.0, frame="enemy_red", rng=rng)

    # --- archetype on-death effects --------------------------------------

    BOMBER_AOE_RADIUS = 95.0       # px; squad members in this circle attrited
    BOMBER_MAX_LOSSES = 3          # cap squad losses per bomber explosion

    def _bomber_explode(self, x: float, y: float) -> None:
        """Bomber AOE: extra particle ring + attrition for nearby squad.

        Models the bomber as a melee-style threat: kill it early or pay
        when it pops at the squad's front line.
        """
        if self.particle_controller is not None:
            self.particle_controller.burst(
                x, y, count=14, speed=380.0, ttl=0.45,
                size=14.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                x, y, count=10, speed=260.0, ttl=0.55,
                size=16.0, frame="enemy_red", rng=self._fire_rng,
            )
        self._add_shake(2.2)
        # Squad members in radius take one hit each (capped). Shield blocks.
        if self.shield_active_until > self._run_time:
            return
        if self.squad_pool is None:
            return
        sp = self.squad_pool
        r2 = self.BOMBER_AOE_RADIUS * self.BOMBER_AOE_RADIUS
        losses = 0
        for i in range(sp.capacity):
            if losses >= self.BOMBER_MAX_LOSSES:
                break
            if not sp.active[i]:
                continue
            dx = sp.cx[i] - x
            dy = sp.cy[i] - y
            if dx * dx + dy * dy <= r2:
                losses += 1
        # Also catch the hero if close.
        hero_caught = False
        if self.hero is not None:
            dx = self.hero.center_x - x
            dy = self.hero.center_y - y
            if dx * dx + dy * dy <= r2:
                hero_caught = True
        total_losses = losses + (1 if hero_caught else 0)
        if total_losses == 0:
            return
        self.squad_count = max(0, self.squad_count - total_losses)
        self.attrition_total += total_losses
        if self.hero is not None:
            self.hero.flash(duration=0.30,
                            color=(1.0, 0.25, 0.25, 0.78))
        ui.app().audio.play_sfx("damage")
        if self.squad_count <= 0:
            self._end_level(won=False)

    def _on_pickup_collect(self, ptype: int, x: float, y: float) -> None:
        """Hero touched a coin or double-coin pickup. Coins go straight to
        the run total (with 2× active if the double-coin timer is up);
        the double-coin pickup starts/refreshes that timer."""
        if ptype == entities.PICKUP_COIN:
            coins = entities.PickupController.COIN_PER_PICKUP
            if self.double_coin_until > self._run_time:
                coins *= 2
            self._coins_earned += coins
            if self.particle_controller is not None:
                self.particle_controller.burst(
                    x, y, count=10, speed=320.0, ttl=0.40,
                    size=10.0, frame="particle", rng=self._fire_rng,
                )
            ui.app().audio.play_sfx("coin")
        else:    # PICKUP_DOUBLE_COIN
            duration = entities.PickupController.DOUBLE_COIN_DURATION_SEC
            self.double_coin_until = self._run_time + duration
            if self.particle_controller is not None:
                self.particle_controller.burst(
                    x, y, count=20, speed=400.0, ttl=0.55,
                    size=14.0, frame="particle", rng=self._fire_rng,
                )
                self.particle_controller.burst(
                    x, y, count=12, speed=240.0, ttl=0.70,
                    size=18.0, frame="projectile", rng=self._fire_rng,
                )
            ui.app().audio.play_sfx("gate_pickup")
            self._add_shake(2.0)

    def _splitter_split(self, x: float, y: float) -> None:
        """Splitter on-death: spawn 3 grunts at the kill location with
        outward velocity. Punishes overkill — if a wave of splitters all
        die at the front line, the squad eats 9 fresh grunts immediately.
        """
        if self.enemy_controller is None:
            return
        # Lower base hp so split grunts don't feel like infinite respawns.
        speed = self.enemy_spawner.enemy_speed if self.enemy_spawner else 220.0
        for k in (-1, 0, 1):
            self.enemy_controller.spawn(
                x + k * 35.0, y, 36.0, 36.0, "enemy_red",
                hp=1, speed=speed,
                chase=self._fire_rng.uniform(50.0, 110.0),
                enemy_type=entities.TYPE_GRUNT,
            )

    def _update(self, dt):
        if self._level_ended:
            return
        # Shake first so the offset applies to everything else this frame.
        self._step_shake(dt)
        self._run_time += dt
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

        # 3. Enemies: spawner interval can be modulated by level type
        #    (static / hybrid / dynamic), then spawner ticks + enemies update.
        x_min = sx
        y_min = sy
        x_max = sx + sw
        y_max = sy + sh
        if (self.enemy_controller is not None
                and self.enemy_spawner is not None
                and self.hero is not None
                and self.level_config is not None
                and not self.level_config.get("boss")):
            base_interval = self.level_config["enemy_spawn_interval"]
            lvl_type = self.level_config.get("type", "static")
            if lvl_type == "static":
                type_mult = 1.10
            elif lvl_type == "hybrid":
                # Alternating spikes every ~3 s — half the level the spawn
                # pressure ratchets up so the player can't autopilot.
                phase = (self.distance / SCROLL_SPEED_PX_PER_SEC) / 3.0
                spike = (int(phase) % 2 == 1)
                type_mult = 0.70 if spike else 1.0
            else:   # dynamic
                type_mult = 0.65
            # In-level ramp: start very gentle (2.5× interval = 40 % of base
            # spawn rate) and end at 0.55× (relentless). The aggressive
            # initial floor lets a small starting squad survive long enough
            # to engage the first few gates before the level ramps up.
            if self.distance_goal > 0:
                progress = min(1.0, self.distance / self.distance_goal)
            else:
                progress = 0.0
            ramp = max(0.55, 2.50 - 2.00 * progress)
            self.enemy_spawner.interval = base_interval * type_mult * ramp

        if (self.enemy_controller is not None
                and self.enemy_spawner is not None
                and self.hero is not None):
            self.enemy_spawner.tick(dt, x_min, y_min, x_max, y_max)
            self.enemy_controller.update(dt, self.hero.center_x,
                                         x_min, y_min, x_max, y_max)

        # 3a. Pickups: spawner drops coin / double-coin items; controller
        # scrolls them with the world. Hero auto-collects on overlap.
        if (self.pickup_controller is not None
                and self.pickup_spawner is not None
                and self.hero is not None
                and self.level_config is not None
                and not self.level_config.get("boss")):
            self.pickup_spawner.tick(
                self.distance, x_min, x_max, y_max,
                SCROLL_SPEED_PX_PER_SEC,
            )
            self.pickup_controller.update(dt, y_min)
            entities.resolve_pickup_collection(
                self.pickup_controller,
                self.hero.center_x, self.hero.center_y,
                PICKUP_COLLECT_RADIUS,
                self._on_pickup_collect,
            )

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
                on_miss=self._on_miss_gate,
            )
            # Lane gravity follows the active pair's gates.
            self.lane_centers = self.gate_controller.active_lane_centers(
                self.hero.center_y,
            )

        # 3c. Boss (M10): drift + attack patterns. Boss spawns minions through
        # `enemy_controller`; everything else (squad fire, attrition, particles)
        # works on those minions unchanged.
        if (self.boss_controller is not None
                and self.boss is not None
                and self.hero is not None):
            self.boss_controller.update(
                dt, self.hero.center_x, self.hero.center_y,
                x_min, y_min, x_max, y_max,
            )
            # Phase-2 transition fanfare: a one-shot ring of red particles
            # at the boss center + a shake so the player sees it happened.
            if self.boss.phase2_transition_pending:
                self.boss.phase2_transition_pending = False
                if self.particle_controller is not None:
                    self.particle_controller.burst(
                        self.boss.cx, self.boss.cy, count=22, speed=420.0,
                        ttl=0.55, size=15.0, frame="enemy_red",
                        rng=self._fire_rng,
                    )
                self._add_shake(6.0)
                ui.app().audio.play_sfx("hit")

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
                    hero_muzzle = (self.hero.center_x, self.hero.center_y + MUZZLE_OFFSET_Y)
                    positions = [hero_muzzle]
                    sp = self.squad_pool
                    sc = self.squad_controller
                    for i in range(sp.capacity):
                        if sp.active[i]:
                            positions.append((sp.cx[i], sp.cy[i] + sc.MUZZLE_OFFSET_Y))
                    # Sub-linear firepower cap. Above MAX_SHOOTERS_PER_SHOT,
                    # randomly sample so every squad member rotates in over
                    # time (every shot picks a different subset). Squad
                    # redundancy stays meaningful for absorbing attrition but
                    # firepower plateaus — late-world levels with dense
                    # enemies are no longer trivialized by a 100-runner squad.
                    if len(positions) > MAX_SHOOTERS_PER_SHOT:
                        positions = self._fire_rng.sample(positions, MAX_SHOOTERS_PER_SHOT)
                    # Apply weapon-tier damage multiplier from the player's
                    # shop purchases (state.get_weapon_tier). Tier 1 (default)
                    # = 1.0×; tier 4 = 3.0×.
                    running_app = ui.app()
                    tier = (running_app.state.get_weapon_tier(self.current_weapon_id)
                            if running_app and running_app.state else 1)
                    effective_damage = weapons.tier_damage(weapon, tier)
                    entities.fire_from_positions(
                        positions, target_x, target_y, weapon,
                        self.projectile_controller, self._fire_rng,
                        damage_override=effective_damage,
                    )
                    self._fire_cooldown = 1.0 / weapon.fire_rate
                    # M11 polish: muzzle flash + gun smoke at the hero's muzzle,
                    # plus a tiny recoil shake.
                    self._spawn_muzzle_polish(*hero_muzzle)
                    self._add_shake(0.6)

            self.projectile_controller.update(dt, x_min, y_min, x_max, y_max)

            # Projectile vs enemy collisions. on_kill receives the archetype
            # tag so we can trigger the on-death effect (bomber AOE, splitter
            # split) on top of the standard particle burst.
            def _on_kill(hit_x, hit_y, enemy_type, _self=self):
                _self._spawn_death_polish(hit_x, hit_y)
                _self._add_shake(0.35)
                # Fractional coin reward — accumulated in a remainder, with
                # the integer portion paid on each frame the accumulator
                # exceeds 1. Doubles when the 2× pickup is active.
                reward = COIN_PARTIAL_REWARD.get(enemy_type, 0.30)
                if _self.double_coin_until > _self._run_time:
                    reward *= 2.0
                _self._coin_remainder += reward
                while _self._coin_remainder >= 1.0:
                    _self._coins_earned += 1
                    _self._coin_remainder -= 1.0
                if enemy_type == entities.TYPE_BOMBER:
                    _self._bomber_explode(hit_x, hit_y)
                elif enemy_type == entities.TYPE_SPLITTER:
                    _self._splitter_split(hit_x, hit_y)
            kills = entities.resolve_projectile_collisions(
                self.projectile_controller, self.enemy_controller, self.grid, _on_kill,
            )
            self.kills_total += kills

            # Projectile vs boss (M10): AABB-only — boss is one big entity.
            if self.boss_controller is not None and self.boss is not None and self.boss.alive:
                def _on_boss_hit(hit_x, hit_y, died,
                                 _pc=self.particle_controller, _rng=self._fire_rng,
                                 _self=self):
                    _pc.burst(hit_x, hit_y, count=4, speed=200.0, ttl=0.30,
                              size=10.0, frame="particle", rng=_rng)
                    # M11: bigger shake when the boss is reeling.
                    _self._add_shake(0.9)
                    if died:
                        # Big celebratory burst at the boss center on kill.
                        if _self.boss is not None:
                            _pc.burst(_self.boss.cx, _self.boss.cy,
                                      count=30, speed=380.0, ttl=0.65,
                                      size=14.0, frame="particle", rng=_rng)
                            _pc.burst(_self.boss.cx, _self.boss.cy,
                                      count=18, speed=260.0, ttl=0.80,
                                      size=18.0, frame="enemy_red", rng=_rng)
                        _self._add_shake(_self.SHAKE_CAP)  # max kick on boss death
                        _self._end_level(won=True)
                boss_module.resolve_projectile_vs_boss(
                    self.projectile_controller, self.boss_controller, _on_boss_hit,
                )

            # Squad attrition: enemies that pierce the squad's front line cost one runner each.
            # When squad_count hits 0 the hero falls and the level fails.
            def _on_loss(hit_x, hit_y, _self=self, _rng=self._fire_rng):
                if _self._level_ended or _self.squad_count <= 0:
                    return
                # Shield blocks attrition. The enemy is still killed (it
                # bounced off the shield) — feels like deflection, not a freebie.
                if _self.shield_active_until > _self._run_time:
                    if _self.particle_controller is not None:
                        _self.particle_controller.burst(
                            hit_x, hit_y, count=8, speed=300.0, ttl=0.30,
                            size=12.0, frame="particle", rng=_rng,
                        )
                    _self._add_shake(0.6)
                    return
                _self.squad_count -= 1
                _self.attrition_total += 1
                if _self.particle_controller is not None:
                    # Yellow sparks (impact).
                    _self.particle_controller.burst(
                        hit_x, hit_y, count=6, speed=240.0, ttl=0.4,
                        size=10.0, frame="particle", rng=_rng,
                    )
                    # Red splatter (body fragments) so attrition reads
                    # unambiguously as a hit on the squad.
                    _self.particle_controller.burst(
                        hit_x, hit_y, count=6, speed=180.0, ttl=0.55,
                        size=14.0, frame="enemy_red", rng=_rng,
                    )
                # Hero flashes red so the player can't miss the hit.
                if _self.hero is not None:
                    _self.hero.flash(
                        duration=0.30,
                        color=(1.0, 0.25, 0.25, 0.78),
                    )
                # M11: medium shake on attrition; bigger if it was the final hit.
                _self._add_shake(2.5 if _self.squad_count > 0 else 9.0)
                running = ui.app()
                running.audio.play_sfx("damage")
                if _self.squad_count <= 0:
                    _self._end_level(won=False)
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
        if self.pickup_renderer is not None:
            self.pickup_renderer.rebuild()
        # 6b. Boss widget + HP bar follow the underlying data each frame.
        if self.boss_widget is not None:
            self.boss_widget.update_from_boss()
        if self.boss_hp_bar is not None:
            self.boss_hp_bar.update_from_boss()
        # 6c. Hero hit-flash decay.
        if self.hero is not None:
            self.hero.tick_flash(dt)

        # 6c. Distance goal reached → level complete (skipped on boss levels —
        #     boss death drives the win condition there).
        is_boss_level = bool(self.level_config and self.level_config.get("boss"))
        if (not self._level_ended
                and not is_boss_level
                and self.distance_goal > 0
                and self.distance >= self.distance_goal):
            self._end_level(won=True)
            return

        # 7. HUD + debug overlay.
        hero_cx = self.hero.center_x if self.hero is not None else 0.0
        enemy_count = self.enemy_pool.active_count if self.enemy_pool is not None else 0
        weapon_name = weapons.get(self.current_weapon_id).name
        progress = "{:.0f} / {:.0f}".format(self.distance, self.distance_goal) \
            if self.distance_goal > 0 else "{:.0f}".format(self.distance)
        # Sync the on-screen booster buttons (count + dimmed when empty).
        if self.grenade_btn is not None:
            self.grenade_btn.text = "G\n{}".format(self.grenade_count)
            self.grenade_btn.disabled = self.grenade_count <= 0
            self.grenade_btn.bg = (
                [0.20, 0.80, 0.95, 1] if self.grenade_count > 0
                else [0.30, 0.30, 0.35, 1]
            )
        if self.shield_btn is not None:
            if self.shield_active_until > self._run_time:
                remaining = self.shield_active_until - self._run_time
                self.shield_btn.text = "S ACT\n{:.1f}s".format(remaining)
                self.shield_btn.bg = [1.0, 0.85, 0.30, 1]
                self.shield_btn.disabled = True
            else:
                self.shield_btn.text = "S\n{}".format(self.shield_count)
                self.shield_btn.disabled = self.shield_count <= 0
                self.shield_btn.bg = (
                    [0.50, 0.85, 1.00, 1] if self.shield_count > 0
                    else [0.30, 0.30, 0.35, 1]
                )
        # Double-coin pickup timer chip in the HUD if active.
        if self.double_coin_until > self._run_time:
            remaining = self.double_coin_until - self._run_time
            dc_chip = "  [2× COINS {:.1f}s]".format(remaining)
        else:
            dc_chip = ""
        self.hud_label.text = ("Distance {}     Squad {}     "
                               "Weapon: {}     Kills {}{}").format(
            progress, self.squad_count, weapon_name, self.kills_total, dc_chip,
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

    def _on_miss_gate(self) -> None:
        """Called once per gate pair the player let scroll past untouched.

        Drives the pity-gate floor on the spawner side — two consecutive
        misses guarantee at least one safe (MUL / ADD) option in the next
        pair so the player can recover.
        """
        if self.gate_spawner is not None:
            self.gate_spawner.consecutive_misses += 1

    def _on_apply_gate(self, gate) -> None:
        """Apply a passed gate's effect: mutate squad_count or swap weapon."""
        if self._level_ended:
            return
        # Player picked a gate → reset the pity-counter, earn small coin reward
        # (with 2× when the pickup is active).
        if self.gate_spawner is not None:
            self.gate_spawner.consecutive_misses = 0
        gate_reward = COIN_REWARD_GATE
        if self.double_coin_until > self._run_time:
            gate_reward *= 2
        self._coins_earned += gate_reward
        if gate.op == gates.OP_MUL:
            self.squad_count = min(MAX_SQUAD, max(1, self.squad_count * int(gate.value)))
        elif gate.op == gates.OP_ADD:
            self.squad_count = min(MAX_SQUAD, self.squad_count + int(gate.value))
        elif gate.op == gates.OP_SUB:
            # SUB can take the squad to zero — game over if that happens.
            self.squad_count = max(0, self.squad_count - int(gate.value))
        elif gate.op == gates.OP_DIV:
            # Divide squad by value (integer floor). At squad=1 ÷2 → 0 = death,
            # so DIV gates only appear from W3 where the player has grown.
            divisor = max(1, int(gate.value))
            self.squad_count = max(0, self.squad_count // divisor)
        elif gate.op == gates.OP_WEAPON:
            if gate.value in weapons.WEAPONS:
                self.current_weapon_id = gate.value
                self._fire_cooldown = 0.0
        elif gate.op == gates.OP_GRENADE:
            self.grenade_count = min(MAX_GRENADES,
                                     self.grenade_count + int(gate.value))
        # Audio + particle burst at the hero so the pickup reads.
        running = ui.app()
        running.audio.play_sfx("gate_pickup")
        if self.particle_controller is not None and self.hero is not None:
            self.particle_controller.burst(
                self.hero.center_x, self.hero.center_y + HERO_H * 0.3,
                count=10, speed=260.0, ttl=0.45, size=12.0,
                frame="particle", rng=self._fire_rng,
            )
        if self.squad_count <= 0:
            self._end_level(won=False)

    def _end_level(self, won: bool) -> None:
        """Cancel the update loop, persist progress, then show banner + dialog.

        The dialog used to open the instant the win/lose condition fired,
        which felt abrupt. M11.5 splits the flow: persist + show a centered
        banner immediately, then open the existing LevelResultDialog after
        a short fade so the moment of resolution reads.
        """
        if self._level_ended:
            return
        self._level_ended = True
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

        running = ui.app()
        final_squad = max(0, self.squad_count)
        gates_applied = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed = self.gate_controller.missed_total if self.gate_controller else 0
        score = levels.score_for(self.kills_total, final_squad, gates_applied, gates_missed)
        level_index = running.current_level
        level_cfg = self.level_config or levels.get_level(level_index) or levels.get_level(1)
        stars = levels.stars_for(level_cfg, won, final_squad)

        # End-of-level coin bonus: 20 for completing + 10 per star (was 50/30
        # before — kills + gates now contribute less so the shop progresses
        # at the right rate when combined with in-level coin pickups).
        if won:
            self._coins_earned += COIN_BONUS_LEVEL_COMPLETE + COIN_BONUS_PER_STAR * stars

        # Persist for single-player levels. Multiplayer never touches the save.
        if running.current_mode == "single" and level_index:
            running.state.record_result(level_index, score, stars,
                                        distance=int(self.distance))
            if self._coins_earned > 0:
                running.state.add_coins(self._coins_earned)
            # Persist leftover booster balances. No more free-grenade baseline
            # — anything the player has at level end is what they earned or
            # carried into the level.
            g_delta = self.grenade_count - running.state.get_booster_balance("grenade")
            if g_delta != 0:
                running.state.add_booster("grenade", g_delta)
            s_delta = self.shield_count - running.state.get_booster_balance("shield")
            if s_delta != 0:
                running.state.add_booster("shield", s_delta)
            if won:
                running.state.unlock_up_to(level_index + 1)
                running.audio.play_sfx("level_complete")
            else:
                running.audio.play_sfx("death")
        else:
            running.audio.play_sfx("level_complete" if won else "death")

        # Show the banner immediately; dialog opens after a short pause.
        self._show_end_banner(won)
        Clock.schedule_once(
            lambda dt: self._open_result_dialog(won, stars, score, level_cfg, level_index),
            1.0,
        )

    def _show_end_banner(self, won: bool) -> None:
        """Centered, fading-in banner shown the moment the level ends."""
        from kivy.animation import Animation
        text = "VICTORY!" if won else "DEFEATED"
        color = (1.0, 0.88, 0.2, 0.0) if won else (0.95, 0.40, 0.40, 0.0)
        banner = Label(
            text=text, font_size=sp(64), bold=True, color=color,
            size_hint=(0.9, 0.3),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
        )
        self.root_layout.add_widget(banner)
        self._end_banner = banner
        target = (color[0], color[1], color[2], 1.0)
        Animation(color=target, duration=0.45, t="out_quad").start(banner)

    def _open_result_dialog(self, won: bool, stars: int, score: int,
                            level_cfg, level_index) -> None:
        # Dismiss the banner before the modal opens so we don't stack.
        if hasattr(self, "_end_banner") and self._end_banner is not None:
            if self._end_banner.parent is not None:
                self._end_banner.parent.remove_widget(self._end_banner)
            self._end_banner = None

        running = ui.app()
        next_index = (level_index + 1) if (
            level_index and level_index < levels.TOTAL_LEVELS) else None
        if won and next_index is not None:
            def go_next():
                running.start_level(next_index)
            on_next = go_next
        else:
            on_next = None

        level_label = ""
        if level_cfg:
            level_label = "World {} - {}    Level {}".format(
                level_cfg["world"],
                levels.get_world(level_cfg["world"])["name"],
                level_cfg["world_index"],
            )

        def on_retry():
            if level_index:
                running.start_level(level_index)
            else:
                running.go("menu")

        def on_menu():
            running.go("menu")

        dialog = ui.LevelResultDialog(
            won=won, stars=stars, score=score, level_label=level_label,
            on_next=on_next, on_retry=on_retry, on_menu=on_menu,
        )
        dialog.open()

    # --- weapon + grenade keyboard ----------------------------------------

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
        if codepoint == "g":
            self._detonate_grenade()
            return True
        if codepoint == "s":
            self._activate_shield()
            return True
        return False

    def _activate_shield(self) -> None:
        if self.shield_count <= 0 or self._level_ended:
            return
        # Don't waste a shield if one is already up.
        if self.shield_active_until > self._run_time:
            return
        self.shield_count -= 1
        self.shield_active_until = self._run_time + boosters.SHIELD_DURATION_SEC
        ui.app().audio.play_sfx("gate_pickup")
        if self.hero is not None:
            # Tint the hero blue for the shield duration via the AtlasSprite flash.
            self.hero.flash(
                duration=boosters.SHIELD_DURATION_SEC,
                color=(0.30, 0.70, 1.0, 0.55),
            )
        self._add_shake(1.5)

    def _detonate_grenade(self) -> None:
        """Burn one grenade: kill every enemy within GRENADE_RADIUS of the hero."""
        if self.grenade_count <= 0 or self.hero is None or self.enemy_controller is None:
            return
        self.grenade_count -= 1
        hero_cx = self.hero.center_x
        hero_cy = self.hero.center_y
        r2 = GRENADE_RADIUS * GRENADE_RADIUS
        ep = self.enemy_pool
        active = ep.active
        cx = ep.cx
        cy = ep.cy
        kills = 0
        for i in range(ep.capacity):
            if not active[i]:
                continue
            dx = cx[i] - hero_cx
            dy = cy[i] - hero_cy
            if dx * dx + dy * dy <= r2:
                # Lift the existing death polish so the explosion reads consistent
                # with regular projectile kills, plus an outer ring.
                self._spawn_death_polish(cx[i], cy[i])
                ep.release(i)
                self.enemy_controller.recycled_total += 1
                kills += 1
        # Boss takes one grenade's worth of damage if it's within radius.
        if self.boss_controller is not None and self.boss is not None and self.boss.alive:
            dx = self.boss.cx - hero_cx
            dy = self.boss.cy - hero_cy
            if dx * dx + dy * dy <= r2 * 1.6 * 1.6:
                died = self.boss_controller.take_damage(20)
                if died and not self._level_ended:
                    self._end_level(won=True)
        # Big visual + audio.
        self.kills_total += kills
        if self.particle_controller is not None:
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=24, speed=440.0, ttl=0.55,
                size=14.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=14, speed=280.0, ttl=0.70,
                size=18.0, frame="enemy_red", rng=self._fire_rng,
            )
        self._add_shake(8.0)
        ui.app().audio.play_sfx("hit")

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
            running.go("multiplayer")
            return
        if running.current_mode == "single":
            running.go("levelselect")
        else:
            running.go("menu")
