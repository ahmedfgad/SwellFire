"""test_weapon_tiers.py — extended weapon tiers 1-6.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_weapon_tiers.py"""
import weapons


def test_max_tier_is_6():
    assert weapons.MAX_TIER == 6


def test_damage_mult_covers_all_tiers_and_increases():
    m = weapons.TIER_DAMAGE_MULT
    assert m[0] is None
    vals = m[1:7]
    assert len(vals) == 6
    assert all(vals[i] < vals[i + 1] for i in range(5))   # strictly increasing


def test_tier_damage_at_top():
    rifle = weapons.get("rifle")   # damage 1
    assert weapons.tier_damage(rifle, 6) == max(1, round(1 * weapons.TIER_DAMAGE_MULT[6]))
    assert weapons.tier_damage(rifle, 99) == weapons.tier_damage(rifle, 6)   # clamps


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON TIER TESTS PASSED")
