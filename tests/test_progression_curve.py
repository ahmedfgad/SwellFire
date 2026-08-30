"""test_progression_curve.py — softened late-world difficulty.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_progression_curve.py"""
from swellfire import levels


def test_enemy_hp_4_is_world6_only():
    assert levels.get_level(40)["enemy_hp"] <= 3     # ~W4 (t~0.66)
    assert levels.get_level(60)["enemy_hp"] == 4     # last


def test_density_high_end_eased():
    c = levels.get_level(60)
    assert c["formation_columns"] == 6
    assert abs(c["rank_interval_end"] - 260.0) < 1e-6


def test_boss_hp_eased():
    assert levels.get_level(60)["boss_hp"] == int(round(2200.0))


def test_pressure_factor_rescues_weak_and_challenges_strong_squads():
    weak = levels.formation_pressure_factor(levels.TYPE_DYNAMIC, 5, 20)
    even = levels.formation_pressure_factor(levels.TYPE_DYNAMIC, 20, 20)
    strong = levels.formation_pressure_factor(levels.TYPE_DYNAMIC, 80, 20)
    assert 1.0 < weak <= 2.00
    assert even == 1.0
    assert 0.90 <= strong < 1.0


def test_level_type_controls_pressure_strength():
    static = levels.formation_pressure_factor(levels.TYPE_STATIC, 80, 20)
    hybrid = levels.formation_pressure_factor(levels.TYPE_HYBRID, 80, 20)
    dynamic = levels.formation_pressure_factor(levels.TYPE_DYNAMIC, 80, 20)
    assert 1.0 > static > hybrid > dynamic
    assert levels.formation_pressure_factor(levels.TYPE_BOSS, 80, 20) == 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROGRESSION CURVE TESTS PASSED")
