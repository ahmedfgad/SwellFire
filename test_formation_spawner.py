"""test_formation_spawner.py — rank/column formation spawning.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py"""
import entities


class _FakeCtrl:
    def __init__(self):
        self.calls = []
    def spawn(self, x, y, w, h, frame, hp, speed, chase, enemy_type):
        self.calls.append(dict(x=x, y=y, w=w, h=h, frame=frame, hp=hp,
                               speed=speed, chase=chase, enemy_type=enemy_type))
        return len(self.calls) - 1


def _fs(seed=1):
    ctrl = _FakeCtrl()
    fs = entities.FormationSpawner(ctrl, seed=seed)
    fs.columns = 5
    fs.rank_interval_px = 100.0
    fs.enemy_hp = 2
    fs.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
    fs.reset_per_level(0.0)
    return fs, ctrl


def test_no_rank_before_interval():
    fs, ctrl = _fs()
    fs.update(50.0, 0.0, 0.0, 400.0, 1000.0)
    assert ctrl.calls == []


def test_one_rank_per_interval_crossed():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    assert len(ctrl.calls) == 5            # one rank = 5 columns
    fs.update(320.0, 0.0, 0.0, 400.0, 1000.0)
    assert len(ctrl.calls) == 15           # +2 ranks (200, 300)


def test_enemies_have_no_chase_and_spawn_at_top():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    ys = {c["y"] for c in ctrl.calls}
    assert all(c["chase"] == 0.0 for c in ctrl.calls)
    assert len(ys) == 1 and next(iter(ys)) > 1000.0   # one rank, above top edge


def test_columns_are_distinct_and_in_bounds():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    xs = sorted(c["x"] for c in ctrl.calls)
    assert len(set(xs)) == 5
    assert xs[0] > 0.0 and xs[-1] < 400.0


def test_hp_uses_curve_and_scale():
    fs, ctrl = _fs()
    fs.hp_scale = 1.0
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    assert ctrl.calls[0]["hp"] == 2        # grunt hp_mult 1.0 * enemy_hp 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL FORMATION SPAWNER TESTS PASSED")
