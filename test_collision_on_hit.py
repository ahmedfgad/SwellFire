"""test_collision_on_hit.py — on_hit fires for non-lethal contacts only.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py"""
import entities


class _Pool:
    def __init__(self, n):
        self.capacity = n
        self.active = [True] * n
        self.cx = [0.0] * n
        self.cy = [0.0] * n
        self.hw = [10.0] * n
        self.released = []
    def release(self, i):
        self.active[i] = False
        self.released.append(i)


class _PC:   # projectile controller stand-in
    def __init__(self, n, damage):
        self.pool = _Pool(n)
        self.damage = [damage] * n
        self.owner = bytearray(n)
        self.recycled_total = 0


class _EC:   # enemy controller stand-in
    def __init__(self, hps):
        n = len(hps)
        self.pool = _Pool(n)
        self.hp = list(hps)
        self.type = [0] * n           # all grunts (TYPE_GRUNT)
        self.recycled_total = 0


class _Grid:
    def clear(self): pass
    def insert_pool(self, pool): self._pool = pool
    def query(self, x, y, r):
        return [i for i in range(self._pool.capacity) if self._pool.active[i]]


def _run(enemy_hp, damage):
    pc = _PC(1, damage)
    ec = _EC([enemy_hp])
    kills, hits = [], []
    entities.resolve_projectile_collisions(
        pc, ec, _Grid(),
        on_kill=lambda hx, hy, t, o: kills.append(t),
        on_hit=lambda hx, hy, t, o: hits.append(t),
    )
    return kills, hits


def test_non_lethal_hit_fires_on_hit_only():
    kills, hits = _run(enemy_hp=2, damage=1)   # survives
    assert kills == [] and hits == [0]


def test_lethal_hit_fires_on_kill_only():
    kills, hits = _run(enemy_hp=1, damage=1)   # dies
    assert kills == [0] and hits == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COLLISION ON_HIT TESTS PASSED")
