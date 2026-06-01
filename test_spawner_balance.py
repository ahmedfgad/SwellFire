"""test_spawner_balance.py — spawner hp_scale, HP-size, top-half spawn, poof.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_spawner_balance.py

_spawn_one does not touch self.atlas, so a fake controller + atlas=None work."""
import entities


class _FakeCtrl:
    """Records spawn() calls; returns an incrementing index."""
    def __init__(self):
        self.calls = []
        self._n = 0

    def spawn(self, x, y, w, h, frame, hp, speed, chase, enemy_type):
        self.calls.append(dict(x=x, y=y, w=w, h=h, frame=frame, hp=hp,
                               speed=speed, chase=chase, enemy_type=enemy_type))
        self._n += 1
        return self._n - 1


def _spawner(seed=1):
    ctrl = _FakeCtrl()
    sp = entities.EnemySpawner(ctrl, atlas=None, seed=seed)
    sp.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
    return sp, ctrl


def test_hp_scale_multiplies_spawned_hp():
    sp, ctrl = _spawner()
    sp.enemy_hp = 2
    sp.hp_scale = 1.75              # tier-4 power-scaling
    sp._spawn_one(0.0, 0.0, 400.0, 1000.0)
    # round(2 * 1.0 * 1.75) == round(3.5) == 4
    assert ctrl.calls[-1]["hp"] == 4


def test_default_hp_scale_is_one():
    sp, ctrl = _spawner()
    sp.enemy_hp = 2
    sp._spawn_one(0.0, 0.0, 400.0, 1000.0)
    assert ctrl.calls[-1]["hp"] == 2


def test_tougher_enemy_is_bigger():
    sp, ctrl = _spawner()
    sp.enemy_hp = 1
    sp._spawn_one(0.0, 0.0, 400.0, 1000.0)
    small = ctrl.calls[-1]["w"]
    sp.enemy_hp = 4
    sp._spawn_one(0.0, 0.0, 400.0, 1000.0)
    big = ctrl.calls[-1]["w"]
    assert big > small


def test_spawn_y_is_in_top_half():
    sp, ctrl = _spawner(seed=7)
    sp.enemy_hp = 1
    y_min, y_max = 0.0, 1000.0
    sp._spawn_one(0.0, y_min, 400.0, y_max)
    y = ctrl.calls[-1]["y"]
    mid = y_min + 0.5 * (y_max - y_min)
    assert y >= mid                      # never below the top half
    assert y <= y_max + sp._above_top_px()  # never above the spawn ceiling


def test_poof_fires_only_for_onscreen_spawns():
    sp, ctrl = _spawner(seed=3)
    sp.enemy_hp = 1
    poofs = []
    sp.spawn_poof = lambda x, y: poofs.append((x, y))
    sp._spawn_one(0.0, 0.0, 400.0, 1000.0)
    y = ctrl.calls[-1]["y"]
    if y < 1000.0:                       # spawned on-screen
        assert poofs, "on-screen spawn should poof"
    else:
        assert not poofs, "off-screen spawn should not poof"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL SPAWNER BALANCE TESTS PASSED")
