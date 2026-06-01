"""test_boss_targeting.py — find_nearest_threat band logic.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py"""
import entities


class _Pool:
    def __init__(self, xs, ys, act):
        self.cx = list(xs)
        self.cy = list(ys)
        self.active = list(act)
        self.capacity = len(xs)


class _Ctrl:
    def __init__(self, pool):
        self.pool = pool


def test_no_enemy_in_band_returns_minus1():
    # one enemy, but it's 500 above; band is 300 => out of band.
    ctrl = _Ctrl(_Pool([100.0], [500.0], [True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == -1


def test_enemy_in_band_is_returned():
    ctrl = _Ctrl(_Pool([100.0], [200.0], [True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == 0


def test_picks_closest_in_band():
    # idx0 at front 250, idx1 at front 80 => idx1 wins.
    ctrl = _Ctrl(_Pool([100.0, 130.0], [250.0, 80.0], [True, True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == 1


def test_ignores_inactive_and_behind():
    # idx0 inactive, idx1 behind the hero (below) => none qualify.
    ctrl = _Ctrl(_Pool([100.0, 100.0], [50.0, -10.0], [False, True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == -1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL BOSS TARGETING TESTS PASSED")
