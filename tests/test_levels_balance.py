"""test_levels_balance.py — #11/#12 difficulty curve.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_levels_balance.py"""
from swellfire import levels


def test_enemy_hp_curve_is_tougher_early():
    # index 1 (t=0) gentle; W2-L1 (index 11, t~0.17) now 2 HP; late = 4.
    assert levels.get_level(1)["enemy_hp"] == 1
    assert levels.get_level(11)["enemy_hp"] == 2     # W2-L1
    assert levels.get_level(21)["enemy_hp"] == 2     # W3-L1 (t~0.34)
    assert levels.get_level(30)["enemy_hp"] == 3     # mid (t~0.49)
    assert levels.get_level(60)["enemy_hp"] == 4     # last


def test_early_spawn_is_denser():
    # L1 spawn interval lowered from 0.18 to 0.15 (more enemies/sec early).
    assert abs(levels.get_level(1)["enemy_spawn_interval"] - 0.15) < 1e-6


def test_tanks_appear_in_world_3():
    names = [n for n, _ in levels._allowed_enemy_types(3)]
    assert "tank" in names
    # W1/W2 stay grunt-only.
    assert "tank" not in [n for n, _ in levels._allowed_enemy_types(2)]


def test_sniper_unlocks_in_world_3_with_tanks():
    assert "sniper" in levels.get_level(21)["allowed_weapons"]   # W3-L1
    assert "sniper" not in levels.get_level(11)["allowed_weapons"]  # W2-L1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL LEVELS BALANCE TESTS PASSED")
