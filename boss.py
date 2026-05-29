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
    * `BossWidget` — the boss sprite (a per-world PNG, atlas frame as
      fallback), plus a white overlay we pulse on hit and a desaturated
      "stone" overlay that creeps down the body as HP drops (the
      monster-health indicator — there is no separate HP bar).

M14 swaps the atlas frame for a real boss sprite and may add a third
attack pattern (a horizontal sweep / charge); the controller already
holds a `pattern` index so adding more is a small change.
"""

from __future__ import annotations

import random

from kivy.animation import Animation
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty
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
    """The boss's visual: a sprite that breathes, bobs, glows, recoils on
    hit, and flashes in its own silhouette (not a white box).

    Animated knobs (all visual-only — collision uses ``Boss.aabb`` from the
    data, never the widget size):
        ``pulse``  — slow breathing scale (looping idle)
        ``bob``    — gentle vertical idle drift (looping)
        ``recoil`` — transient squash punched on each hit
    """

    pulse = NumericProperty(1.0)
    bob = NumericProperty(0.0)
    recoil = NumericProperty(1.0)

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
        # Resolve the sprite texture (+ tex_coords for the atlas fallback) so
        # the hit flash can reuse them and flash only the monster's pixels.
        if sprite_path is not None:
            tex = graphics.load_texture(sprite_path)
            tex_coords = None
        else:
            tex = atlas.texture
            u0, v0, u1, v1 = atlas.frame("enemy_red")
            tex_coords = (u0, v0, u1, v0, u1, v1, u0, v1)
        # Desaturated "stone" twin of the sprite — overdraws the depleted
        # top slice of the body as HP drops (the monster-health indicator;
        # replaces the old top HP bar). Degrades gracefully to "no effect"
        # if the twin is missing (e.g. a world whose base PNG is absent).
        self._hp_ratio = 1.0
        self._stone_rect = None
        self._stone_full = None
        self._seam_rect = None
        stone_tex = None
        if sprite_path is not None:
            try:
                stone_tex = graphics.load_texture(
                    sprite_path.replace(".png", "_stone.png"))
            except Exception:
                stone_tex = None
        with self.canvas:
            # The sprite. Its own Color tints reddish in phase 2.
            self._sprite_color = Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=tex)
            # Stone overlay — drawn ABOVE the living sprite (so it replaces
            # the dead pixels) but BELOW the hit flash (so a hit still
            # whitens the whole silhouette). A bright "petrification seam"
            # rides the health line on top of it so the descending boundary
            # is easy to see even when only a thin slice has turned to stone.
            if stone_tex is not None:
                self._stone_color = Color(1, 1, 1, 1)  # twin is already grey
                self._stone_rect = Rectangle(texture=stone_tex)
                self._stone_full = tuple(stone_tex.tex_coords)
                self._seam_color = Color(1.0, 0.86, 0.42, 0.0)
                self._seam_rect = Rectangle(texture=stone_tex)
            # Hit flash — SAME texture so only the silhouette flashes white,
            # not a full rectangle.
            self._flash_color = Color(1, 1, 1, 0)
            self._flash_rect = Rectangle(texture=tex)
            if tex_coords is not None:
                self._rect.tex_coords = tex_coords
                self._flash_rect.tex_coords = tex_coords
        self.bind(pos=self._sync, size=self._sync,
                  pulse=self._sync, bob=self._sync, recoil=self._sync)
        self.size = (boss.width, boss.height)
        self._sync()
        self._start_idle()

    def _start_idle(self) -> None:
        """Looping breathing + bob, and a shimmer on the petrification seam."""
        body = (Animation(pulse=1.05, bob=dp(7), duration=1.0, t="in_out_sine")
                + Animation(pulse=0.97, bob=-dp(7), duration=1.0, t="in_out_sine"))
        body.repeat = True
        body.start(self)
        if self._seam_rect is not None:
            # The seam's alpha shimmers; it only actually shows once a slice
            # of the body has petrified (see _sync, which zeroes its size at
            # full health).
            seam = (Animation(a=0.95, duration=0.5, t="in_out_sine")
                    + Animation(a=0.55, duration=0.5, t="in_out_sine"))
            seam.repeat = True
            seam.start(self._seam_color)

    def _sync(self, *_):
        cx, cy = self.center
        s = self.pulse * self.recoil
        w = self.width * s
        h = self.height * s
        x = cx - w * 0.5
        y = cy - h * 0.5 + self.bob
        self._rect.pos = (x, y)
        self._rect.size = (w, h)
        self._flash_rect.pos = (x, y)
        self._flash_rect.size = (w, h)
        if self._stone_rect is not None:
            # Stone covers the depleted TOP slice — from the head down to the
            # health line at fraction `r`. The living body shows below it.
            r = max(0.0, min(1.0, self._hp_ratio))
            dead = 1.0 - r
            self._stone_rect.pos = (x, y + h * r)
            self._stone_rect.size = (w, h * dead)
            # Sample the matching top slice of the texture. Interpolate along
            # the quad's own corner v-coords so this is correct regardless of
            # whether the texture is vertically flipped: the slice's bottom
            # edge sits at fraction `r` between the displayed bottom and top.
            u_bl, v_bl, u_br, v_br, u_tr, v_tr, u_tl, v_tl = self._stone_full
            v_bl_s = v_bl + (v_tl - v_bl) * r
            v_br_s = v_br + (v_tr - v_br) * r
            self._stone_rect.tex_coords = (
                u_bl, v_bl_s, u_br, v_br_s, u_tr, v_tr, u_tl, v_tl)
            # Bright seam: a thin textured band straddling the health line.
            # Using the stone texture keeps it inside the silhouette (the
            # alpha masks the transparent corners). Hidden at full health.
            if self._seam_rect is not None:
                if dead <= 0.005:
                    self._seam_rect.size = (0, 0)
                else:
                    band = max(dp(4), h * 0.05)
                    hf = (band * 0.5) / h
                    f_lo = max(0.0, r - hf)
                    f_hi = min(1.0, r + hf)
                    self._seam_rect.pos = (x, y + h * f_lo)
                    self._seam_rect.size = (w, h * (f_hi - f_lo))
                    vL_lo = v_bl + (v_tl - v_bl) * f_lo
                    vL_hi = v_bl + (v_tl - v_bl) * f_hi
                    vR_lo = v_br + (v_tr - v_br) * f_lo
                    vR_hi = v_br + (v_tr - v_br) * f_hi
                    self._seam_rect.tex_coords = (
                        u_bl, vL_lo, u_br, vR_lo, u_br, vR_hi, u_bl, vL_hi)

    def on_hit(self) -> None:
        """Quick squash punch on each damage tick — makes the boss feel like
        it's reacting to fire. Combined with the silhouette flash + the
        particle burst/shake fired from the game loop."""
        Animation.cancel_all(self, "recoil")
        (Animation(recoil=0.88, duration=0.05)
         + Animation(recoil=1.0, duration=0.16, t="out_back")).start(self)

    def stop(self) -> None:
        """Cancel looping animations when the boss is torn down."""
        Animation.cancel_all(self, "pulse", "bob", "recoil")
        if self._seam_rect is not None:
            Animation.cancel_all(self._seam_color, "a")

    def update_from_boss(self) -> None:
        self.center_x = self.boss.cx
        self.center_y = self.boss.cy
        # Health → how much of the body has turned to stone (top-down).
        self._hp_ratio = (self.boss.hp / self.boss.max_hp
                          if self.boss.max_hp > 0 else 0.0)
        if self._stone_rect is not None:
            self._sync()
        # Map flash_time → alpha (full at FLASH_DURATION, 0 at 0).
        if self.boss.flash_time > 0.0:
            self._flash_color.a = min(0.75, self.boss.flash_time * 6.0)
        else:
            self._flash_color.a = 0.0
        # Phase 2 "enrage": redden the living part of the sprite.
        if self.boss.phase2:
            self._sprite_color.rgb = (1.0, 0.62, 0.58)
        else:
            self._sprite_color.rgb = (1.0, 1.0, 1.0)


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
