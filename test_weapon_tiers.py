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
    expected = max(round(rifle.damage * weapons.TIER_DAMAGE_MULT[6]),
                   rifle.damage + weapons.TIER_DAMAGE_FLOOR_BONUS[6])
    assert weapons.tier_damage(rifle, 6) == expected
    assert weapons.tier_damage(rifle, 99) == weapons.tier_damage(rifle, 6)   # clamps


def test_every_paid_tier_increases_effective_damage():
    for weapon in weapons.WEAPONS.values():
        damage = [weapons.tier_damage(weapon, tier)
                  for tier in range(1, weapons.MAX_TIER + 1)]
        assert all(a < b for a, b in zip(damage, damage[1:])), (weapon.id, damage)
    assert [weapons.tier_damage(weapons.get("rifle"), tier)
            for tier in range(1, weapons.MAX_TIER + 1)] == [1, 2, 3, 4, 6, 8]


def test_combat_power_reflects_tier_and_projectile_count():
    rifle = weapons.get("rifle")
    shotgun = weapons.get("shotgun")
    assert weapons.combat_power(rifle, 6) > weapons.combat_power(shotgun, 1)
    assert weapons.combat_power(rifle, 2) > weapons.combat_power(rifle, 1)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON TIER TESTS PASSED")
