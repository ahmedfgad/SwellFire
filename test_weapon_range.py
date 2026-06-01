"""test_weapon_range.py — per-weapon kill-zone fraction.
Run: venv/bin/python test_weapon_range.py  (pure)"""
import weapons


def test_every_weapon_has_a_range_frac():
    for wid in ("pistol", "rifle", "shotgun", "sniper"):
        rf = weapons.get(wid).range_frac
        assert 0.0 < rf <= 0.7, (wid, rf)


def test_range_frac_ordering_matches_niches():
    rf = lambda w: weapons.get(w).range_frac
    assert rf("sniper") > rf("rifle") >= rf("pistol") > rf("shotgun")
    assert rf("sniper") <= 0.7   # still capped below the top of the lane


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON RANGE TESTS PASSED")
