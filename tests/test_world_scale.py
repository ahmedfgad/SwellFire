"""Density-scaling regression test (iOS small-sprites / gate-overflow fix).

The game world is dimensioned in raw pixels tuned at density 1.0. On a
high-density (Retina) surface every world-px size/speed/distance must scale by
``graphics.world_scale()`` so the world stays density-independent — sprites fill
the screen and gate equations fit their box — while remaining a *no-op at
density 1.0* (desktop unchanged).

Run headless (no GL / no window needed):
    SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_world_scale.py
"""
from __future__ import annotations

import math
import random

from swellfire import graphics
from swellfire import entities
from swellfire import gates
from swellfire import weapons


class FakePool:
    """Minimal stand-in for graphics.EntityPool (no GL/atlas needed).

    Records every spawn so tests can assert the width/height/velocity that
    reached the pool, which is where the scaled magnitudes land.
    """

    def __init__(self, capacity: int = 64):
        self.capacity = capacity
        self.active = [False] * capacity
        self.active_count = 0
        self.cx = [0.0] * capacity
        self.cy = [0.0] * capacity
        self.vx = [0.0] * capacity
        self.vy = [0.0] * capacity
        self.hw = [0.0] * capacity
        self.hh = [0.0] * capacity
        self.calls: list[dict] = []

    def spawn(self, x, y, vx, vy, w, h, frame):
        for i in range(self.capacity):
            if not self.active[i]:
                self.active[i] = True
                self.active_count += 1
                self.cx[i] = x
                self.cy[i] = y
                self.vx[i] = vx
                self.vy[i] = vy
                self.hw[i] = w * 0.5
                self.hh[i] = h * 0.5
                self.calls.append(dict(x=x, y=y, vx=vx, vy=vy, w=w, h=h,
                                       frame=frame))
                return i
        return -1

    def release(self, i):
        if self.active[i]:
            self.active[i] = False
            self.active_count -= 1


class RecordingGateController:
    """Captures the (x, y, w, h, op, value, label) specs GateSpawner emits."""

    def __init__(self):
        self.specs: list[tuple] = []

    def spawn_pair(self, spec_a, spec_b):
        self.specs.append(spec_a)
        self.specs.append(spec_b)


APPROX = 1e-6


def approx(a, b):
    return abs(a - b) == 0 or abs(a - b) <= APPROX * max(1.0, abs(a), abs(b))


def _spawn_one_enemy(scale):
    graphics.set_world_scale(scale)
    pool = FakePool()
    ctrl = entities.EnemyController(pool)
    spawner = entities.EnemySpawner(ctrl, atlas=None, seed=1)
    spawner.enemy_speed = 200.0
    spawner.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
    spawner.intro_delay = 0.0
    # Spawn directly (bypass the time gate) into a wide play area.
    spawner._spawn_one(0.0, 0.0, 4000.0, 4000.0)
    assert pool.calls, "enemy did not spawn"
    return pool.calls[-1]


def test_enemy_size_and_speed_scale():
    base = _spawn_one_enemy(1.0)
    big = _spawn_one_enemy(3.0)
    assert approx(base["w"], 64.0), base["w"]                 # grunt logical size
    assert approx(big["w"], 64.0 * 3.0), big["w"]             # scaled sprite
    # vy is -speed (enemies travel down); magnitude must scale.
    assert approx(abs(base["vy"]), 200.0), base["vy"]
    assert approx(abs(big["vy"]), 200.0 * 3.0), big["vy"]


def test_particle_burst_scales():
    for scale in (1.0, 3.0):
        graphics.set_world_scale(scale)
        pool = FakePool()
        pc = entities.ParticleController(pool)
        pc.burst(0.0, 0.0, count=3, speed=240.0, ttl=0.3, size=8.0,
                 frame="spark", rng=random.Random(2))
        sizes = {c["w"] for c in pool.calls}
        assert sizes == {8.0 * scale}, (scale, sizes)
        # speed is randomized in [0.45*speed, speed]; bound must scale.
        vmax = max(math.hypot(c["vx"], c["vy"]) for c in pool.calls)
        assert vmax <= 240.0 * scale + 1e-6, (scale, vmax)
        assert vmax > 240.0 * scale * 0.4, (scale, vmax)


def test_pickup_coin_scales():
    for scale in (1.0, 3.0):
        graphics.set_world_scale(scale)
        pool = FakePool()
        pc = entities.PickupController(pool)
        spawner = entities.PickupSpawner(pc, seed=7)
        spawner.reset_per_level()
        spawner.DOUBLE_COIN_CHANCE = 0.0  # force plain coin
        # distance threshold is in the (scaled) distance domain.
        spawner.tick(distance=10_000.0 * scale, x_min=0.0, x_max=2000.0,
                     y_top=1000.0, scroll_speed=360.0 * scale)
        assert pool.calls, (scale, "no pickup spawned")
        assert approx(pool.calls[-1]["w"], 26.0 * scale), pool.calls[-1]["w"]


def test_projectile_fire_scales():
    for scale in (1.0, 3.0):
        graphics.set_world_scale(scale)
        pool = FakePool(capacity=8)
        pc = entities.ProjectileController(pool)
        wpn = weapons.get_weapon("rifle") if hasattr(weapons, "get_weapon") \
            else weapons.WEAPONS["rifle"]
        entities.fire_from_positions(
            [(0.0, 0.0)], target_x=0.0, target_y=1000.0,
            weapon=wpn, projectile_controller=pc, rng=random.Random(3))
        assert pool.calls, (scale, "no projectile")
        c = pool.calls[-1]
        assert approx(c["w"], wpn.projectile_size * scale), (scale, c["w"])
        speed = math.hypot(c["vx"], c["vy"])
        assert approx(speed, wpn.projectile_speed * scale), (scale, speed)


def test_squad_runner_and_formation_scale():
    for scale in (1.0, 3.0):
        graphics.set_world_scale(scale)
        pool = FakePool(capacity=32)
        sq = entities.SquadController(pool)
        sq.sync_to_count(4)
        assert approx(pool.hw[0] * 2.0, 28.0 * scale), pool.hw[0]
        sq.update_formation(hero_cx=1000.0, hero_cy=1000.0)
        # Front row sits FORMATION_START_OFFSET below the hero; that gap scales.
        front_gap = 1000.0 - pool.cy[0]
        assert approx(front_gap, 48.0 * scale), (scale, front_gap)


def test_gate_box_height_scales():
    heights = {}
    for scale in (1.0, 3.0):
        graphics.set_world_scale(scale)
        rec = RecordingGateController()
        spawner = gates.GateSpawner(rec, seed=11)
        spawner.reset_per_level()
        # tick spawns once distance passes the first threshold (scaled domain).
        spawner.tick(distance=100_000.0 * scale, x_min=0.0, x_max=1080.0,
                     y_top=2000.0)
        assert rec.specs, (scale, "no gate pair spawned")
        # spec = (x, y, w, h, op, value, label)
        heights[scale] = rec.specs[0][3]
    assert approx(heights[1.0], 112.0), heights[1.0]
    assert approx(heights[3.0], 112.0 * 3.0), heights[3.0]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures.append((t.__name__, e))
            print(f"FAIL {t.__name__}: {e!r}")
    graphics.set_world_scale(None)
    if failures:
        print(f"\n{len(failures)} FAILED / {len(tests)}")
        raise SystemExit(1)
    print(f"\nALL {len(tests)} PASSED")


if __name__ == "__main__":
    main()
