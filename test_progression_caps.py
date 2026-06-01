"""test_progression_caps.py — world-gated tier/squad caps.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_progression_caps.py"""
import state
import levels
import weapons


def _s(highest_unlocked, coins=100000):
    s = state.GameState("/tmp/sf_prog_{}".format(highest_unlocked))
    s.data["highest_unlocked"] = highest_unlocked
    s.data["coins_balance"] = coins
    s.data["weapon_tiers"] = {}
    s.data["squad_bonus"] = 0
    return s


def test_levels_per_world_constant_matches():
    assert state._LEVELS_PER_WORLD == levels.LEVELS_PER_WORLD


def test_max_world_reached():
    assert _s(1).max_world_reached == 1
    assert _s(11).max_world_reached == 2
    assert _s(31).max_world_reached == 4
    assert _s(60).max_world_reached == 6


def test_max_tier_for_world():
    s = _s(1)
    assert s.max_tier_for_world(1) == 1
    assert s.max_tier_for_world(4) == 4
    assert s.max_tier_for_world(6) == 6
    assert s.max_tier_for_world(9) == weapons.MAX_TIER


def test_upgrade_blocked_above_world_cap():
    s = _s(1)
    assert s.upgrade_weapon_tier("rifle", 2, 1) is False
    assert s.coins_balance == 100000


def test_upgrade_allowed_at_or_below_cap():
    s = _s(11)
    assert s.upgrade_weapon_tier("rifle", 2, 400) is True
    assert s.get_weapon_tier("rifle") == 2
    assert s.upgrade_weapon_tier("rifle", 3, 1000) is False


def test_max_squad_bonus_for_world():
    s = _s(1)
    assert s.max_squad_bonus_for_world(1) == 0
    assert s.max_squad_bonus_for_world(2) == 1
    assert s.max_squad_bonus_for_world(6) == 5


def test_squad_bonus_blocked_above_cap():
    s = _s(1)
    assert s.purchase_squad_bonus(1, 50) is False
    s2 = _s(31)
    assert s2.purchase_squad_bonus(3, 50) is True
    assert s2.purchase_squad_bonus(4, 50) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROGRESSION CAP TESTS PASSED")
