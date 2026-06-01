"""test_progression_curve.py — softened late-world difficulty.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_progression_curve.py"""
import levels


def test_enemy_hp_4_is_world6_only():
    assert levels.get_level(40)["enemy_hp"] <= 3     # ~W4 (t~0.66)
    assert levels.get_level(60)["enemy_hp"] == 4     # last


def test_density_high_end_eased():
    c = levels.get_level(60)
    assert c["formation_columns"] == 8               # was 9
    assert abs(c["rank_interval_end"] - 75.0) < 1e-6  # was 60


def test_boss_hp_eased():
    assert levels.get_level(60)["boss_hp"] == int(round(2200.0))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROGRESSION CURVE TESTS PASSED")
