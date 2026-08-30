"""test_projectile_killline.py — projectiles stop at the kill line.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_projectile_killline.py"""
from swellfire import entities


class _FakePool:
    def __init__(self, n):
        self.capacity = n
        self.active = [True] * n
        self.cx = [0.0] * n
        self.cy = [0.0] * n
        self.vx = [0.0] * n
        self.vy = [0.0] * n
        self.released = []
    def release(self, i):
        self.active[i] = False
        self.released.append(i)


def _pc(cys):
    pool = _FakePool(len(cys))
    pc = entities.ProjectileController(pool)
    for i, cy in enumerate(cys):
        pool.cy[i] = cy
        pc.ttl[i] = 1.0           # alive (so ttl<=0 doesn't release)
    return pc, pool


def test_projectile_past_kill_line_is_released():
    pc, pool = _pc([600.0, 400.0])
    pc.kill_line_y = 500.0
    pc.update(0.0, -1e6, -1e6, 1e6, 1e6)   # dt=0, huge bounds
    assert not pool.active[0]               # 600 > 500 -> released
    assert pool.active[1]                   # 400 < 500 -> kept


def test_none_kill_line_keeps_everything():
    pc, pool = _pc([600.0, 400.0])
    pc.kill_line_y = None
    pc.update(0.0, -1e6, -1e6, 1e6, 1e6)
    assert pool.active[0] and pool.active[1]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROJECTILE KILLLINE TESTS PASSED")
