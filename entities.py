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


# --- Enemy archetypes ----------------------------------------------------
#
# Each archetype shares the same chase FSM but has distinct stats and an
# on-death effect (handled in game.py since it touches the squad).
#
#   grunt     — the standard chaser. 1-3 HP per level, normal size/speed.
#   tank      — slow, large, 8x base HP. Forces focused fire; small squads
#               can't burn it down quickly without sub-linear-fire wasting
#               shots on grunts behind it.
#   bomber    — yellow (projectile frame), 2x HP, faster, EXPLODES on death
#               and triggers attrition on squad members within radius.
#               Punishes letting them die at the front line.
#   splitter  — 4x HP, medium-slow, on death splits into 3 grunts at the
#               kill location. Punishes overkill and clumping.
#   swarmer   — small, fast, 1 HP. Spawns in clusters of 4 — high-volume
#               peripheral threat that bypasses focused fire.

TYPE_GRUNT = 0
TYPE_TANK = 1
TYPE_BOMBER = 2
TYPE_SPLITTER = 3
TYPE_SWARMER = 4

TYPE_NAMES = {
    "grunt": TYPE_GRUNT,
    "tank": TYPE_TANK,
    "bomber": TYPE_BOMBER,
    "splitter": TYPE_SPLITTER,
    "swarmer": TYPE_SWARMER,
}

# Per-archetype stats. `base_hp` is multiplied by the level's `enemy_hp`
# baseline so worlds still ramp HP within an archetype.
ARCHETYPES: dict[int, dict] = {
    TYPE_GRUNT: dict(
        frame="enemy_red", size=44.0,
        hp_mult=1.0, speed_mult=1.0, chase_mult=1.0,
        spawn_count=1, label="grunt",
    ),
    TYPE_TANK: dict(
        frame="enemy_red", size=72.0,
        hp_mult=8.0, speed_mult=0.55, chase_mult=0.50,
        spawn_count=1, label="tank",
    ),
    TYPE_BOMBER: dict(
        frame="projectile", size=50.0,
        hp_mult=2.0, speed_mult=1.15, chase_mult=1.0,
        spawn_count=1, label="bomber",
    ),
    TYPE_SPLITTER: dict(
        frame="enemy_red", size=60.0,
        hp_mult=4.0, speed_mult=0.85, chase_mult=0.7,
        spawn_count=1, label="splitter",
    ),
    TYPE_SWARMER: dict(
        frame="enemy_red", size=28.0,
        hp_mult=1.0, speed_mult=1.30, chase_mult=1.20,
        spawn_count=4, label="swarmer",
    ),
}


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
        self.type = bytearray(cap)        # one of TYPE_* (archetype tag)
        self.hp = [0] * cap                # current HP
        self.speed = [0.0] * cap           # px/sec downward
        self.chase = [0.0] * cap           # max lateral px/sec toward hero
        self.spawned_total = 0
        self.recycled_total = 0

    def spawn(self, x: float, y: float, w: float, h: float,
              frame_name: str, hp: int, speed: float, chase: float,
              enemy_type: int = TYPE_GRUNT) -> int:
        # vy is negative because y grows upward in Kivy and enemies travel
        # toward the player at the bottom.
        idx = self.pool.spawn(x, y, 0.0, -speed, w, h, frame_name)
        if idx >= 0:
            self.state[idx] = STATE_WALKING
            self.type[idx] = enemy_type
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
        # Per-archetype defaults; level config overwrites these on level entry.
        self.enemy_speed = 220.0          # base px/sec straight down (grunt)
        self.enemy_hp = 1                 # base HP per enemy
        self.chase_strength_min = 30.0
        self.chase_strength_max = 90.0
        self.spawn_above_top = 30.0
        # Archetype mix: list of (type_int, weight). Default is all grunts.
        # game.GameScreen._apply_level_config overrides with the per-level mix.
        self.spawn_table: list[tuple[int, float]] = [(TYPE_GRUNT, 1.0)]

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
        """Pick an archetype from `spawn_table`, then spawn 1+ enemies of that
        type (some archetypes like swarmer spawn a cluster per pick)."""
        rng = self._rng
        # Weighted-random archetype pick.
        total = sum(w for _, w in self.spawn_table) or 1.0
        r = rng.uniform(0.0, total)
        cum = 0.0
        enemy_type = TYPE_GRUNT
        for t, w in self.spawn_table:
            cum += w
            if r <= cum:
                enemy_type = t
                break
        arch = ARCHETYPES[enemy_type]
        size = float(arch["size"])
        hp = max(1, int(round(self.enemy_hp * arch["hp_mult"])))
        speed = self.enemy_speed * arch["speed_mult"]
        chase_lo = self.chase_strength_min * arch["chase_mult"]
        chase_hi = self.chase_strength_max * arch["chase_mult"]
        frame = arch["frame"]

        count = int(arch["spawn_count"])
        last_idx = -1
        # Cluster spawn (swarmers): tile horizontally near the chosen X with
        # a tight spread so they read as one wave.
        anchor_x = rng.uniform(x_min + size * 0.5 + 40.0,
                               x_max - size * 0.5 - 40.0)
        for k in range(count):
            offset = (k - (count - 1) / 2.0) * (size * 0.95)
            x = max(x_min + size * 0.5,
                    min(x_max - size * 0.5, anchor_x + offset))
            chase = rng.uniform(chase_lo, chase_hi)
            last_idx = self.controller.spawn(
                x, y_max + self.spawn_above_top,
                size, size, frame,
                hp=hp, speed=speed, chase=chase, enemy_type=enemy_type,
            )
        return last_idx


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

    def spawn_one(self, x: float, y: float, vx: float, vy: float,
                  size: float, ttl: float, frame: str) -> int:
        """Single directional particle. Used for muzzle flashes and
        gun-smoke trails where the direction matters."""
        idx = self.pool.spawn(x, y, vx, vy, size, size, frame)
        if idx >= 0:
            self.ttl[idx] = ttl
            self.spawned_total += 1
        return idx

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
    """Pick the most urgent enemy above the hero (threat-weighted).

    Score = vertical_distance + lateral_distance * 0.30. The vertical
    component dominates so the squad always engages the closest-to-the-
    front-line target — a small squad spends its limited firepower on
    the imminent threat instead of grunts drifting at the top of the
    road, and a big squad (after sub-linear-fire cap) wastes fewer shots
    on already-doomed back-line enemies.

    O(N) per shot is fine — at 8 shots/sec * 200 enemies that's 1600
    ops/sec, below anything that would show up on a profile.
    """
    pool = enemy_controller.pool
    active = pool.active
    cx = pool.cx
    cy = pool.cy
    best_idx = -1
    best_score = float("inf")
    for i in range(pool.capacity):
        if not active[i]:
            continue
        # Only target enemies the hero hasn't passed.
        if cy[i] < hero_cy:
            continue
        front = cy[i] - hero_cy            # vertical distance (smaller = more urgent)
        lateral = abs(cx[i] - hero_cx)
        score = front + lateral * 0.30
        if score < best_score:
            best_score = score
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


# --- squad (M8) ----------------------------------------------------------

class SquadController:
    """Mesh-batched squad of follower runners trailing behind the hero.

    The pool size mirrors `squad_count - 1` (the hero is its own widget;
    everything in the pool is a follower). The formation is a tight grid
    centered horizontally on the hero, growing backward (lower Y) one row
    per `SPACING_Y`. Columns ramp roughly as `sqrt(count) * 1.2` so the
    blob reads as wider-than-deep, which looks right for a Stickman-style
    crowd from a top-down view.
    """

    FRAME_NAME = "runner_blue"
    RUNNER_W = 32.0
    RUNNER_H = 40.0
    SPACING_X = 34.0
    SPACING_Y = 28.0
    MAX_COLS = 10
    MUZZLE_OFFSET_Y = RUNNER_H * 0.45

    def __init__(self, pool: graphics.EntityPool):
        self.pool = pool

    def sync_to_count(self, follower_count: int) -> None:
        follower_count = max(0, min(self.pool.capacity, int(follower_count)))
        pool = self.pool
        # Spawn slots up to target.
        while pool.active_count < follower_count:
            idx = pool.spawn(0.0, 0.0, 0.0, 0.0,
                             self.RUNNER_W, self.RUNNER_H, self.FRAME_NAME)
            if idx < 0:
                break
        # Release surplus slots, from highest index down so we don't keep
        # re-scanning the same range.
        if pool.active_count > follower_count:
            need_to_release = pool.active_count - follower_count
            for i in range(pool.capacity - 1, -1, -1):
                if need_to_release <= 0:
                    break
                if pool.active[i]:
                    pool.release(i)
                    need_to_release -= 1

    def update_formation(self, hero_cx: float, hero_cy: float) -> None:
        """Lay active follower slots out in a grid trailing behind hero."""
        pool = self.pool
        active = pool.active
        n = pool.active_count
        if n == 0:
            return
        cols = min(self.MAX_COLS, max(1, int(math.sqrt(n) * 1.2 + 0.5)))
        row_width = (cols - 1) * self.SPACING_X
        spacing_x = self.SPACING_X
        spacing_y = self.SPACING_Y
        cx = pool.cx
        cy = pool.cy
        slot = 0
        for i in range(pool.capacity):
            if not active[i]:
                continue
            col = slot % cols
            row = slot // cols
            cx[i] = hero_cx + col * spacing_x - row_width * 0.5
            cy[i] = hero_cy - (row + 1) * spacing_y
            slot += 1


def fire_from_positions(positions, target_x: float, target_y: float,
                        weapon, projectile_controller: ProjectileController,
                        rng: random.Random) -> int:
    """Spawn one projectile per shooter position, all aimed at one target.

    Shooter positions are `(x, y)` tuples — typically the hero's muzzle plus
    every active squad-runner's muzzle. Weapon spread applies per-shot so the
    swarm doesn't read as a single laser. Returns number actually spawned
    (the projectile pool may be saturated).
    """
    speed = weapon.projectile_speed
    size = weapon.projectile_size
    spread = math.radians(weapon.spread_deg)
    spawned = 0
    for (sx, sy) in positions:
        dx = target_x - sx
        dy = target_y - sy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= 0.0:
            aim_x, aim_y = 0.0, 1.0
        else:
            aim_x = dx / dist
            aim_y = dy / dist
        a = rng.uniform(-spread, spread)
        cos_a = math.cos(a)
        sin_a = math.sin(a)
        vx = (aim_x * cos_a - aim_y * sin_a) * speed
        vy = (aim_x * sin_a + aim_y * cos_a) * speed
        idx = projectile_controller.spawn(
            sx, sy, vx, vy, size, size,
            weapon.frame, weapon.damage, weapon.ttl,
        )
        if idx >= 0:
            spawned += 1
        else:
            break       # pool saturated; stop trying
    return spawned


def resolve_squad_attrition(
    enemy_controller: EnemyController,
    hero_cx: float, hero_cy: float,
    zone_half_w: float, front_y: float,
    on_loss,
) -> int:
    """Detect enemies that reach the squad front line; one squad member lost per hit.

    `on_loss(hit_x, hit_y)` is called once per attrition event so the
    caller can spawn a particle burst and decrement `squad_count`. The
    offending enemy is recycled by this function.
    """
    pool = enemy_controller.pool
    active = pool.active
    cx = pool.cx
    cy = pool.cy
    losses = 0
    for i in range(pool.capacity):
        if not active[i]:
            continue
        if cy[i] < front_y and abs(cx[i] - hero_cx) < zone_half_w:
            on_loss(cx[i], cy[i])
            pool.release(i)
            enemy_controller.recycled_total += 1
            losses += 1
    return losses


def resolve_projectile_collisions(
    projectile_controller: ProjectileController,
    enemy_controller: EnemyController,
    grid: SpatialGrid,
    on_kill,
) -> int:
    """Detect projectile<->enemy hits via the spatial grid.

    Indexes enemies into the grid once per call, then per-projectile
    queries the grid for candidate enemies and runs a narrow-phase
    circle-circle check. On a kill, calls `on_kill(hit_x, hit_y, type)`
    so the caller can spawn the right particles + archetype-specific
    effects (bomber AOE, splitter spawn). Returns number of kills.
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

    e_type = enemy_controller.type
    kills = 0
    # Bumped from 30 to 40 to cover the larger tank/splitter hit boxes.
    enemy_max_radius = 40.0
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
                    enemy_type = int(e_type[ei])
                    ep.release(ei)
                    enemy_controller.recycled_total += 1
                    on_kill(hit_x, hit_y, enemy_type)
                    kills += 1
                break   # projectile consumed
    return kills
