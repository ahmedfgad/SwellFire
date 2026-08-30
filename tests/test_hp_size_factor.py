"""test_hp_size_factor.py — HP-based enemy size factor.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_hp_size_factor.py"""
from swellfire import entities


def test_one_hp_is_no_growth():
    assert entities.hp_size_factor(1) == 1.0


def test_scales_with_hp():
    assert abs(entities.hp_size_factor(4) - 1.36) < 1e-9   # 1 + 0.12*3


def test_caps_at_1_6():
    assert entities.hp_size_factor(50) == 1.6
    assert entities.hp_size_factor(8) == min(1.6, 1.0 + 0.12 * 7)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL HP SIZE FACTOR TESTS PASSED")
