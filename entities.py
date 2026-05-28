"""Gameplay-entity pools and controllers.

M5 lands:
    * `EnemyController` — per-enemy AI/state arrays sized to one `EntityPool`,
      plus the chase-FSM step.
    * `EnemySpawner` — periodic spawner that drops new enemies in from above
      the play area at a tunable rate.

Later milestones extend this module with `ProjectilePool`/`RunnerPool`
(M6, M8), the spatial-grid broad-phase (M6), and the boss controller (M10).
The plan keeps everything in this file so the game loop reads as a sequence
of stable function calls on one module.
"""

from __future__ import annotations

import random

import graphics


# --- FSM tags -------------------------------------------------------------

STATE_DEAD = 0
STATE_WALKING = 1
# Reserved for M6 (projectile hits flash the enemy briefly before recycle):
STATE_DYING = 2


# --- enemy controller ----------------------------------------------------

class EnemyController:
    """Per-slot AI state on top of a shared `graphics.EntityPool`.

    The `EntityPool` owns the transform arrays the renderer reads; this
    controller owns the AI arrays (state, hp, downward speed, lateral
    chase strength). Splitting them like this lets `BatchedRenderer.rebuild`
    stay tight — it never has to skip over AI fields it doesn't need.
    """

    def __init__(self, pool: graphics.EntityPool):
        self.pool = pool
        cap = pool.capacity
        self.state = bytearray(cap)       # one of STATE_*
        self.hp = [0] * cap                # current HP
        self.speed = [0.0] * cap           # px/sec downward
        self.chase = [0.0] * cap           # max lateral px/sec toward hero
        self.spawned_total = 0
        self.recycled_total = 0

    def spawn(self, x: float, y: float, w: float, h: float,
              frame_name: str, hp: int, speed: float, chase: float) -> int:
        # vy is negative because y grows upward in Kivy and enemies travel
        # toward the player at the bottom.
        idx = self.pool.spawn(x, y, 0.0, -speed, w, h, frame_name)
        if idx >= 0:
            self.state[idx] = STATE_WALKING
            self.hp[idx] = hp
            self.speed[idx] = speed
            self.chase[idx] = chase
            self.spawned_total += 1
        return idx

    def update(self, dt: float, hero_cx: float,
               x_min: float, y_min: float, x_max: float, y_max: float) -> None:
        """One per-frame step: lateral home toward hero, descend, recycle.

        The chase step is a simple proportional controller, clamped to each
        enemy's `chase` strength. Per-enemy variation in `chase` (set by
        the spawner) is what makes a wave feel like a wave rather than a
        synchronized grid — some enemies veer toward the hero, others
        plod straight down.
        """
        pool = self.pool
        active = pool.active
        cx = pool.cx
        cy = pool.cy
        vx = pool.vx
        vy = pool.vy
        hw = pool.hw
        hh = pool.hh
        chase = self.chase
        speed = self.speed
        state = self.state

        despawn_y = y_min - 60.0   # past the floor; small buffer

        for i in range(pool.capacity):
            if not active[i]:
                continue

            # Proportional steering toward hero X with strength cap.
            dx = hero_cx - cx[i]
            limit = chase[i]
            # 0.04 sec of pursuit ≈ frame-rate-independent feel.
            desired_vx = dx / 0.04
            if desired_vx > limit:
                desired_vx = limit
            elif desired_vx < -limit:
                desired_vx = -limit
            vx[i] = desired_vx
            vy[i] = -speed[i]

            cx[i] += vx[i] * dt
            cy[i] += vy[i] * dt

            # Clamp lateral so enemies hug the rails when they overshoot.
            if cx[i] - hw[i] < x_min:
                cx[i] = x_min + hw[i]
            elif cx[i] + hw[i] > x_max:
                cx[i] = x_max - hw[i]

            # Off-screen at bottom → free the slot.
            if cy[i] < despawn_y:
                state[i] = STATE_DEAD
                pool.release(i)
                self.recycled_total += 1


# --- enemy spawner --------------------------------------------------------

class EnemySpawner:
    """Drops enemies in from above the play area at a steady rate.

    The spawner accumulates time and emits as many enemies as the elapsed
    interval allows on each tick. Setting `interval` to a very small value
    (e.g. via a debug command) fills the pool quickly — that's how the
    M5 stress run gets to 200 concurrent enemies.
    """

    DEFAULT_INTERVAL = 0.08      # seconds between spawns (~12 per sec)

    def __init__(self, controller: EnemyController,
                 atlas: graphics.SpriteAtlas, seed: int | None = None):
        self.controller = controller
        self.atlas = atlas
        self._rng = random.Random(seed)
        self.timer = 0.0
        self.interval = self.DEFAULT_INTERVAL
        # Visual + behaviour defaults (M9 will scale these per-level).
        self.enemy_w = 44.0
        self.enemy_h = 44.0
        self.enemy_speed = 220.0          # px/sec straight down
        self.chase_strength_min = 30.0    # weak chasers
        self.chase_strength_max = 90.0    # strong chasers (still subtler than the hero)
        self.frame_name = "enemy_red"
        self.spawn_above_top = 30.0

    def tick(self, dt: float, x_min: float, y_min: float,
             x_max: float, y_max: float) -> int:
        """Spawn as many enemies as the accumulated time allows.

        Returns the number spawned this tick (useful for tests).
        """
        if self.interval <= 0:
            return 0
        spawned = 0
        self.timer += dt
        while self.timer >= self.interval:
            self.timer -= self.interval
            if self._spawn_one(x_min, y_min, x_max, y_max) >= 0:
                spawned += 1
            else:
                # Pool is full — drop this spawn rather than busy-looping.
                self.timer = 0.0
                break
        return spawned

    def _spawn_one(self, x_min: float, y_min: float,
                   x_max: float, y_max: float) -> int:
        rng = self._rng
        x = rng.uniform(x_min + self.enemy_w * 0.5, x_max - self.enemy_w * 0.5)
        y = y_max + self.spawn_above_top
        chase = rng.uniform(self.chase_strength_min, self.chase_strength_max)
        return self.controller.spawn(
            x, y, self.enemy_w, self.enemy_h, self.frame_name,
            hp=1, speed=self.enemy_speed, chase=chase,
        )
