"""test_reward_boosters.py — refresh-not-rob timer math for timed boosters.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py"""
import boosters


def test_inactive_sets_full_scaled_duration():
    # not active (current <= now): new end = now + base*scale
    assert boosters.refreshed_until(0.0, 10.0, 3.0, 1) == 13.0
    assert boosters.refreshed_until(0.0, 10.0, 3.0, 2) == 16.0


def test_active_extends_when_new_is_longer():
    # active until 20, now 10, base 3, scale 4 -> now+12=22 > 20 -> 22
    assert boosters.refreshed_until(20.0, 10.0, 3.0, 4) == 22.0


def test_active_never_shortens():
    # active until 20, now 10, base 3, scale 1 -> now+3=13 < 20 -> keep 20
    assert boosters.refreshed_until(20.0, 10.0, 3.0, 1) == 20.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL REWARD BOOSTER TESTS PASSED")
