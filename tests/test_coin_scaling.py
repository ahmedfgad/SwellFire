"""test_coin_scaling.py — coin income scales by world.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_coin_scaling.py"""
from swellfire import game


def test_factor_endpoints():
    assert abs(game.coin_world_factor(1) - 1.0) < 1e-9
    assert abs(game.coin_world_factor(6) - 3.0) < 1e-9


def test_factor_monotonic():
    fs = [game.coin_world_factor(w) for w in range(1, 7)]
    assert all(fs[i] < fs[i + 1] for i in range(5))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COIN SCALING TESTS PASSED")
