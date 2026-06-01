"""test_weapons_balance.py — #18 weapon niches.
Run: venv/bin/python test_weapons_balance.py  (pure; no SDL needed)"""
import weapons


def _range(wid):
    w = weapons.get(wid)
    return w.projectile_speed * w.ttl


def test_range_ordering_gives_each_weapon_a_niche():
    # Sniper reaches the top, pistol pokes mid, rifle is medium, shotgun short.
    assert _range("sniper") > _range("pistol") > _range("rifle") > 0
    assert _range("shotgun") < _range("rifle")


def test_sniper_hits_hard():
    assert weapons.get("sniper").damage == 5


def test_shotgun_is_a_crowd_clearer():
    assert weapons.get("shotgun").projectiles_per_shot == 6


def test_rifle_keeps_high_fire_rate_but_loses_range():
    assert weapons.get("rifle").fire_rate == 7.0
    assert _range("rifle") < 980.0   # was 980; now medium


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON BALANCE TESTS PASSED")
