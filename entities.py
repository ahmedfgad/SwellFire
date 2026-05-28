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

import math
import random

import graphics


# --- FSM tags -------------------------------------------------------------

STATE_DEAD = 0
STATE_WALKING = 1
STATE_DYING = 2     # reserved for multi-frame death anim (M11)


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


# --- projectile controller -----------------------------------------------

class ProjectileController:
    """Pool of in-flight projectiles with damage and TTL.

    Velocity is set at spawn time (no homing). Off-screen or TTL-expired
    projectiles recycle. Collision is M6's `resolve_projectile_collisions`,
    which calls back into this controller to release on hit.
    """

    def __init__(self, pool: graphics.EntityPool):
        self.pool = pool
        cap = pool.capacity
        self.damage = [0] * cap
        self.ttl = [0.0] * cap
        self.spawned_total = 0
        self.recycled_total = 0

    def spawn(self, x: float, y: float, vx: float, vy: float,
              w: float, h: float, frame: str,
              damage: int, ttl: float) -> int:
        idx = self.pool.spawn(x, y, vx, vy, w, h, frame)
        if idx >= 0:
            self.damage[idx] = damage
            self.ttl[idx] = ttl
            self.spawned_total += 1
        return idx

    def update(self, dt: float,
               x_min: float, y_min: float, x_max: float, y_max: float) -> None:
        pool = self.pool
        active = pool.active
        cx = pool.cx
        cy = pool.cy
        vx = pool.vx
        vy = pool.vy
        ttl = self.ttl
        margin = 60.0
        for i in range(pool.capacity):
            if not active[i]:
                continue
            cx[i] += vx[i] * dt
            cy[i] += vy[i] * dt
            ttl[i] -= dt
            if (ttl[i] <= 0.0
                    or cx[i] < x_min - margin or cx[i] > x_max + margin
                    or cy[i] < y_min - margin or cy[i] > y_max + margin):
                pool.release(i)
                self.recycled_total += 1


# --- particle controller -------------------------------------------------

class ParticleController:
    """Pool of short-lived particles with drag.

    `burst(x, y, count, ...)` spawns a small cloud at impact points. The
    update loop applies a simple per-axis drag so particles slow visibly
    before fading out.
    """

    DRAG_PER_SEC = 2.4   # exponential decay rate of velocity

    def __init__(self, pool: graphics.EntityPool):
        self.pool = pool
        cap = pool.capacity
        self.ttl = [0.0] * cap
        self.spawned_total = 0
        self.recycled_total = 0

    def burst(self, x: float, y: float, count: int, speed: float, ttl: float,
              size: float, frame: str, rng: random.Random) -> None:
        two_pi = 6.28318530718
        for _ in range(count):
            angle = rng.uniform(0.0, two_pi)
            v = rng.uniform(speed * 0.45, speed)
            vx = math.cos(angle) * v
            vy = math.sin(angle) * v
            idx = self.pool.spawn(x, y, vx, vy, size, size, frame)
            if idx >= 0:
                self.ttl[idx] = ttl
                self.spawned_total += 1
            else:
                break  # pool full

    def update(self, dt: float) -> None:
        pool = self.pool
        active = pool.active
        cx = pool.cx
        cy = pool.cy
        vx = pool.vx
        vy = pool.vy
        ttl = self.ttl
        drag = math.exp(-self.DRAG_PER_SEC * dt)
        for i in range(pool.capacity):
            if not active[i]:
                continue
            cx[i] += vx[i] * dt
            cy[i] += vy[i] * dt
            vx[i] *= drag
            vy[i] *= drag
            ttl[i] -= dt
            if ttl[i] <= 0.0:
                pool.release(i)
                self.recycled_total += 1


# --- spatial grid (broad-phase) ------------------------------------------

class SpatialGrid:
    """Uniform-grid broad-phase for projectile-vs-enemy collision.

    `clear()` empties every bucket; `insert_pool(pool)` indexes every active
    slot's center cell; `query(x, y, radius)` returns indices in cells that
    the (x, y, radius) circle overlaps. Buckets live in a dict so empty
    cells cost nothing, which matters when the playfield is sparse.
    """

    def __init__(self, cell_size: float):
        self.cell_size = float(cell_size)
        self._buckets: dict[tuple[int, int], list[int]] = {}

    def clear(self) -> None:
        self._buckets.clear()

    def insert_pool(self, pool: graphics.EntityPool) -> None:
        cell = self.cell_size
        active = pool.active
        cx = pool.cx
        cy = pool.cy
        buckets = self._buckets
        for i in range(pool.capacity):
            if not active[i]:
                continue
            key = (int(cx[i] // cell), int(cy[i] // cell))
            bucket = buckets.get(key)
            if bucket is None:
                buckets[key] = [i]
            else:
                bucket.append(i)

    def query(self, x: float, y: float, radius: float) -> list[int]:
        cell = self.cell_size
        col0 = int((x - radius) // cell)
        col1 = int((x + radius) // cell)
        row0 = int((y - radius) // cell)
        row1 = int((y + radius) // cell)
        buckets = self._buckets
        result: list[int] = []
        for col in range(col0, col1 + 1):
            for row in range(row0, row1 + 1):
                bucket = buckets.get((col, row))
                if bucket is not None:
                    result.extend(bucket)
        return result


# --- shooting ------------------------------------------------------------

def find_nearest_enemy(hero_cx: float, hero_cy: float,
                       enemy_controller: EnemyController) -> int:
    """Linear scan for the closest *living* enemy above the hero.

    Returns the slot index, or -1 if there's nothing to shoot. O(N) per
    shot is fine — at 8 shots/sec * 200 enemies that's 1600 ops/sec, well
    below anything that would show up on a profile.
    """
    pool = enemy_controller.pool
    active = pool.active
    cx = pool.cx
    cy = pool.cy
    best_idx = -1
    best_d2 = float("inf")
    for i in range(pool.capacity):
        if not active[i]:
            continue
        # Only target enemies the hero hasn't passed.
        if cy[i] < hero_cy:
            continue
        dx = cx[i] - hero_cx
        dy = cy[i] - hero_cy
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best_idx = i
    return best_idx


def fire_weapon(hero_cx: float, hero_cy: float, muzzle_offset_y: float,
                weapon, projectile_controller: ProjectileController,
                enemy_controller: EnemyController,
                rng: random.Random) -> int:
    """Spawn the projectiles for one shot. Returns number actually spawned.

    Picks a direction by snapping to the nearest living enemy; with no
    target, fires straight up. `projectiles_per_shot` and `spread_deg`
    on the weapon translate to a randomized half-cone in 2D.
    """
    target = find_nearest_enemy(hero_cx, hero_cy, enemy_controller)
    if target >= 0:
        ep = enemy_controller.pool
        dx = ep.cx[target] - hero_cx
        dy = ep.cy[target] - hero_cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= 0:
            aim_x, aim_y = 0.0, 1.0
        else:
            aim_x, aim_y = dx / dist, dy / dist
    else:
        # No target — straight up so the player still sees feedback.
        aim_x, aim_y = 0.0, 1.0

    muzzle_y = hero_cy + muzzle_offset_y
    spread = math.radians(weapon.spread_deg)
    speed = weapon.projectile_speed
    size = weapon.projectile_size
    spawned = 0
    for _ in range(weapon.projectiles_per_shot):
        a = rng.uniform(-spread, spread)
        cos_a = math.cos(a)
        sin_a = math.sin(a)
        # Rotate aim by `a` radians.
        vx = (aim_x * cos_a - aim_y * sin_a) * speed
        vy = (aim_x * sin_a + aim_y * cos_a) * speed
        idx = projectile_controller.spawn(
            hero_cx, muzzle_y, vx, vy, size, size,
            weapon.frame, weapon.damage, weapon.ttl,
        )
        if idx >= 0:
            spawned += 1
    return spawned


def resolve_projectile_collisions(
    projectile_controller: ProjectileController,
    enemy_controller: EnemyController,
    grid: SpatialGrid,
    on_kill,
) -> int:
    """Detect projectile<->enemy hits via the spatial grid.

    Indexes enemies into the grid once per call, then per-projectile
    queries the grid for candidate enemies and runs a narrow-phase
    circle-circle check. On a kill, calls `on_kill(hit_x, hit_y)` so
    the caller can spawn a particle burst. Returns number of kills.
    """
    grid.clear()
    grid.insert_pool(enemy_controller.pool)

    pp = projectile_controller.pool
    ep = enemy_controller.pool
    p_active = pp.active
    e_active = ep.active
    p_cx = pp.cx
    p_cy = pp.cy
    p_hw = pp.hw
    e_cx = ep.cx
    e_cy = ep.cy
    e_hw = ep.hw
    p_damage = projectile_controller.damage
    e_hp = enemy_controller.hp

    kills = 0
    enemy_max_radius = 30.0
    for pi in range(pp.capacity):
        if not p_active[pi]:
            continue
        px = p_cx[pi]
        py = p_cy[pi]
        pr = p_hw[pi]
        candidates = grid.query(px, py, pr + enemy_max_radius)
        for ei in candidates:
            if not e_active[ei]:
                continue
            dx = px - e_cx[ei]
            dy = py - e_cy[ei]
            r = pr + e_hw[ei]
            if dx * dx + dy * dy < r * r:
                e_hp[ei] -= p_damage[pi]
                pp.release(pi)
                projectile_controller.recycled_total += 1
                if e_hp[ei] <= 0:
                    hit_x = e_cx[ei]
                    hit_y = e_cy[ei]
                    ep.release(ei)
                    enemy_controller.recycled_total += 1
                    on_kill(hit_x, hit_y)
                    kills += 1
                break   # projectile consumed
    return kills
