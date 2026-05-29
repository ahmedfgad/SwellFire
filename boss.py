"""Boss waves for world-end levels (M10).

Each world's final level (`world_index == LEVELS_PER_WORLD`) is a boss
fight. The regular distance-goal flow is short-circuited and the win
condition becomes "deplete the boss's HP". The regular `EnemySpawner`
is disabled and the boss spawns minions through its attack patterns.

Components:
    * `Boss` — pure data: HP, position, AABB, alive flag.
    * `BossController` — runs the per-frame AI: lateral drift toward a
      slowly-changing target X, two alternating attack patterns
      (Volley and Stream), HP / damage / death.
    * `BossWidget` — an `AtlasSprite` reused at boss-scale (the
      `enemy_red` frame), plus a separate white overlay we pulse on hit
      and a "HP" bar drawn above the boss.

M14 swaps the atlas frame for a real boss sprite and may add a third
attack pattern (a horizontal sweep / charge); the controller already
holds a `pattern` index so adding more is a small change.
"""

from __future__ import annotations

import random

from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import graphics


# --- attack-pattern tags --------------------------------------------------

PATTERN_VOLLEY = 0   # spawn a fan of N enemies all at once
PATTERN_STREAM = 1   # spawn one enemy every `stream_interval` seconds for `stream_duration`


# --- data ----------------------------------------------------------------

class Boss:
    """Plain data for the boss fight — controller mutates these in place."""

    def __init__(self, max_hp: int, cx: float, cy: float,
                 width: float, height: float):
        self.max_hp = int(max_hp)
        self.hp = int(max_hp)
        self.cx = float(cx)
        self.cy = float(cy)
        self.width = float(width)
        self.height = float(height)
        self.target_cx = float(cx)
        self.alive = True
        self.flash_time = 0.0       # countdown on per-hit white tint
        self.pattern = PATTERN_VOLLEY
        self.pattern_timer = 0.0
        # Stream-pattern internal state.
        self._stream_timer = 0.0
        self._stream_left = 0
        # Phase 2 trigger: True once HP drops below 50 %. Phase 2 is the
        # "enraged" mode — faster pattern cadence, denser streams, and every
        # volley adds 1 tank. The HP bar tints darker red and the boss flash
        # ring fires on the transition so the player sees the shift.
        self.phase2 = False
        self.phase2_transition_pending = False

    def aabb(self) -> tuple[float, float, float, float]:
        hw = self.width * 0.5
        hh = self.height * 0.5
        return (self.cx - hw, self.cy - hh, self.cx + hw, self.cy + hh)


# --- controller ----------------------------------------------------------

class BossController:
    """Drives the boss's lateral motion + attack-pattern selection."""

    LATERAL_SPEED = 110.0            # px/sec drift
    PATTERN_DURATION = 3.0           # seconds before switching pattern (was 4.0)
    TARGET_REPICK_EVERY = 3.0        # seconds between drift target re-picks
    STREAM_INTERVAL = 0.15           # seconds between stream-pattern spawns (was 0.20)
    STREAM_COUNT = 12                # enemies emitted per stream wave (was 8)
    VOLLEY_COUNT = 11                # enemies emitted per volley (was 8)
    FLASH_DURATION = 0.12

    def __init__(self, boss: Boss, enemy_controller,
                 seed: int | None = None, minion_hp: int = 1):
        self.boss = boss
        self.enemy_controller = enemy_controller
        self.minion_hp = max(1, int(minion_hp))
        self._rng = random.Random(seed)
        self._target_timer = 0.0
        # Start with a volley so the player sees what the boss does immediately.
        self.boss.pattern = PATTERN_VOLLEY
        self.boss.pattern_timer = 0.0

    def update(self, dt: float, hero_cx: float, hero_cy: float,
               x_min: float, y_min: float, x_max: float, y_max: float) -> None:
        boss = self.boss
        if not boss.alive:
            return

        # Phase-2 transition: once below 50 % HP, enrage. Pattern cadence
        # tightens; volleys add a tank; target re-pick happens twice as fast.
        if not boss.phase2 and boss.hp * 2 <= boss.max_hp:
            boss.phase2 = True
            boss.phase2_transition_pending = True
            # Reset the pattern timer so the next action fires within ~1s.
            boss.pattern_timer = max(0.0, self.PATTERN_DURATION - 1.0)

        # Lateral drift toward target_cx; re-pick the target every
        # ~3-4 seconds within the road (faster in phase 2).
        repick_interval = (self.TARGET_REPICK_EVERY * 0.55
                           if boss.phase2 else self.TARGET_REPICK_EVERY)
        if self._target_timer >= repick_interval:
            self._target_timer = 0.0
            margin = boss.width * 0.5 + 20.0
            boss.target_cx = self._rng.uniform(x_min + margin, x_max - margin)
        dx = boss.target_cx - boss.cx
        if abs(dx) > 0.5:
            step = self.LATERAL_SPEED * dt
            if abs(dx) < step:
                boss.cx = boss.target_cx
            else:
                boss.cx += step if dx > 0 else -step

        # Flash decay on hit feedback.
        if boss.flash_time > 0.0:
            boss.flash_time = max(0.0, boss.flash_time - dt)

        # Pattern progression. Phase 2 shortens the per-pattern duration.
        pattern_duration = (self.PATTERN_DURATION * 0.65
                            if boss.phase2 else self.PATTERN_DURATION)
        boss.pattern_timer += dt
        if boss.pattern == PATTERN_VOLLEY and boss.pattern_timer >= pattern_duration:
            boss.pattern = PATTERN_STREAM
            boss.pattern_timer = 0.0
            stream_count = (self.STREAM_COUNT + 4) if boss.phase2 else self.STREAM_COUNT
            boss._stream_left = stream_count
            boss._stream_timer = 0.0
        elif boss.pattern == PATTERN_STREAM and boss.pattern_timer >= pattern_duration:
            boss.pattern = PATTERN_VOLLEY
            boss.pattern_timer = 0.0
            self._volley(hero_cx, x_min, y_max)

        # Pattern firing.
        if boss.pattern == PATTERN_VOLLEY and boss.pattern_timer == 0.0:
            # The volley already fired on entry above; this branch is a
            # no-op until the timer accumulates again.
            pass
        elif boss.pattern == PATTERN_STREAM and boss._stream_left > 0:
            boss._stream_timer += dt
            stream_interval = (self.STREAM_INTERVAL * 0.55
                               if boss.phase2 else self.STREAM_INTERVAL)
            while boss._stream_timer >= stream_interval and boss._stream_left > 0:
                boss._stream_timer -= stream_interval
                self._stream_one(hero_cx, x_min, x_max, y_max)
                boss._stream_left -= 1

        # The very first frame after construction — fire the opening volley.
        # We piggy-back on `boss.pattern_timer == 0.0` for the very first call
        # so the boss isn't silent for `PATTERN_DURATION` at the start of the
        # fight.
        # (Handled by spawning an opening volley right after BossController
        # construction in the caller; see `BossController.opening_volley`.)

    def opening_volley(self, hero_cx: float, x_min: float, y_max: float) -> None:
        """Fire one volley immediately so the player sees the threat at start."""
        self._volley(hero_cx, x_min, y_max)

    # --- attack patterns -------------------------------------------------

    def _volley(self, hero_cx: float, x_min: float, y_max: float) -> None:
        """Fan of N enemies spawned at the top of the play area.

        Phase 2 adds one tank per volley so the squad can't just hose grunts.
        """
        # Import here to avoid a circular import (entities imports graphics
        # which doesn't import boss; boss doesn't normally need entities
        # constants at module load time).
        import entities as ent
        boss = self.boss
        for _ in range(self.VOLLEY_COUNT):
            x = self._rng.uniform(x_min + 30.0,
                                  x_min + (self.boss.cx - x_min) * 2 - 30.0)
            self.enemy_controller.spawn(
                x, y_max + 20.0, 44.0, 44.0, "enemy_red",
                hp=self.minion_hp, speed=240.0, chase=self._rng.uniform(40.0, 110.0),
                enemy_type=ent.TYPE_GRUNT,
            )
        if boss.phase2:
            tank_arch = ent.ARCHETYPES[ent.TYPE_TANK]
            tank_size = float(tank_arch["size"])
            tank_x = self._rng.uniform(x_min + tank_size,
                                       x_min + (self.boss.cx - x_min) * 2 - tank_size)
            self.enemy_controller.spawn(
                tank_x, y_max + 20.0, tank_size, tank_size, tank_arch["frame"],
                hp=int(max(1, self.minion_hp * tank_arch["hp_mult"])),
                speed=240.0 * tank_arch["speed_mult"],
                chase=self._rng.uniform(40.0, 90.0) * tank_arch["chase_mult"],
                enemy_type=ent.TYPE_TANK,
            )

    def _stream_one(self, hero_cx: float, x_min: float, x_max: float,
                    y_max: float) -> None:
        """Single enemy spawned near the boss aimed roughly at hero."""
        import entities as ent
        offset = self._rng.uniform(-self.boss.width * 0.45, self.boss.width * 0.45)
        x = max(x_min + 30.0, min(x_max - 30.0, self.boss.cx + offset))
        self.enemy_controller.spawn(
            x, self.boss.cy - self.boss.height * 0.5 - 20.0, 44.0, 44.0, "enemy_red",
            hp=self.minion_hp, speed=300.0, chase=self._rng.uniform(110.0, 180.0),
            enemy_type=ent.TYPE_GRUNT,
        )

    # --- damage ---------------------------------------------------------

    def take_damage(self, amount: int) -> bool:
        """Apply damage and start the hit flash. Returns True if the boss died."""
        if not self.boss.alive:
            return False
        self.boss.hp -= int(amount)
        self.boss.flash_time = self.FLASH_DURATION
        if self.boss.hp <= 0:
            self.boss.hp = 0
            self.boss.alive = False
            return True
        return False


# --- widgets -------------------------------------------------------------

class BossWidget(Widget):
    """The boss's visual: scaled enemy_red sprite + white flash overlay."""

    def __init__(self, boss: Boss, atlas: graphics.SpriteAtlas,
                 sprite_path: str | None = None, **kwargs):
        """Boss visual.

        ``sprite_path`` (M14) — optional per-PNG override that bypasses
        the atlas's ``enemy_red`` frame so the boss can use a larger,
        more detailed sprite than the 64-px atlas frame. Falls back to
        the atlas frame when not provided (legacy path).
        """
        super().__init__(**kwargs)
        self.boss = boss
        with self.canvas:
            Color(1, 1, 1, 1)
            if sprite_path is not None:
                self._rect = Rectangle(texture=graphics.load_texture(sprite_path))
            else:
                u0, v0, u1, v1 = atlas.frame("enemy_red")
                self._rect = Rectangle(
                    texture=atlas.texture,
                    tex_coords=(u0, v0, u1, v0, u1, v1, u0, v1),
                )
            self._flash_color = Color(1, 1, 1, 0)
            self._flash_rect = Rectangle()
        self.bind(pos=self._sync, size=self._sync)
        self.size = (boss.width, boss.height)
        self._sync()

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._flash_rect.pos = self.pos
        self._flash_rect.size = self.size

    def update_from_boss(self) -> None:
        self.center_x = self.boss.cx
        self.center_y = self.boss.cy
        # Map flash_time → alpha (full at FLASH_DURATION, 0 at 0).
        if self.boss.flash_time > 0.0:
            self._flash_color.a = min(0.75, self.boss.flash_time * 6.0)
        else:
            self._flash_color.a = 0.0


class BossHPBar(Widget):
    """Boss HP bar — drawn near the top of the stage."""

    LABEL_HEIGHT_PCT = 0.55

    def __init__(self, boss: Boss, **kwargs):
        super().__init__(**kwargs)
        self.boss = boss
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            self._bg = RoundedRectangle(radius=[dp(4)])
            self._fill_color = Color(0.90, 0.30, 0.30, 0.95)
            self._fill = RoundedRectangle(radius=[dp(4)])
        self.label = Label(
            text="BOSS", font_size=sp(13), bold=True, color=(1, 1, 1, 0.95),
            halign="center", valign="middle",
        )
        self.add_widget(self.label)
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *_):
        x, y = self.pos
        w, h = self.size
        self._bg.pos = (x, y)
        self._bg.size = (w, h)
        self.label.pos = (x, y)
        self.label.size = (w, h)
        self.label.text_size = (w, h)
        self._sync_fill()

    def _sync_fill(self) -> None:
        x, y = self.pos
        w, h = self.size
        if self.boss.max_hp <= 0:
            ratio = 0.0
        else:
            ratio = max(0.0, min(1.0, self.boss.hp / self.boss.max_hp))
        self._fill.pos = (x, y)
        self._fill.size = (w * ratio, h)
        # Shift fill color from green → yellow → red as HP drops.
        self._fill_color.rgb = (
            min(1.0, 1.0 - ratio * 0.2 + 0.2),     # red component grows
            max(0.20, ratio * 0.85),                # green drops
            0.30,
        )

    def update_from_boss(self) -> None:
        self._sync_fill()
        self.label.text = "BOSS  {} / {}".format(self.boss.hp, self.boss.max_hp)


# --- helper: projectile-vs-boss broad-phase ------------------------------

def resolve_projectile_vs_boss(projectile_controller, boss_controller,
                                on_hit) -> int:
    """AABB check: each projectile vs the boss. Returns total damage dealt."""
    boss = boss_controller.boss
    if not boss.alive:
        return 0
    bx0, by0, bx1, by1 = boss.aabb()
    pool = projectile_controller.pool
    active = pool.active
    cx = pool.cx
    cy = pool.cy
    damage = projectile_controller.damage
    total = 0
    for i in range(pool.capacity):
        if not active[i]:
            continue
        if bx0 <= cx[i] <= bx1 and by0 <= cy[i] <= by1:
            hit_amount = int(damage[i])
            total += hit_amount
            died = boss_controller.take_damage(hit_amount)
            pool.release(i)
            projectile_controller.recycled_total += 1
            on_hit(cx[i], cy[i], died)
            if died:
                break    # everything after is moot
    return total
