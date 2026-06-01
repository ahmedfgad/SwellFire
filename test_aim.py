"""test_aim.py — pure-math checks for manual aim. Run:
    venv/bin/python test_aim.py
No display / SDL needed (aim.py imports only math)."""
import math

import aim


def approx(a, b, eps=1e-6):
    return abs(a - b) <= eps


def test_update_aim_lead_eases_toward_target():
    # Half-way ease in one step when ease*dt == 0.5.
    assert approx(aim.update_aim_lead(0.0, 100.0, dt=0.5, ease=1.0), 50.0)


def test_update_aim_lead_clamps_overshoot():
    # ease*dt > 1 must not overshoot past the target.
    assert approx(aim.update_aim_lead(0.0, 100.0, dt=1.0, ease=10.0), 100.0)


def test_aim_angle_zero_offset_is_straight_up():
    assert approx(aim.aim_angle(0.0, 220.0, math.radians(35)), 0.0)


def test_aim_angle_saturates_at_max():
    full = 220.0
    mx = math.radians(35)
    assert approx(aim.aim_angle(full, full, mx), mx)
    assert approx(aim.aim_angle(2 * full, full, mx), mx)      # clamped
    assert approx(aim.aim_angle(-2 * full, full, mx), -mx)    # clamped negative


def test_aim_angle_linear_in_between():
    full = 200.0
    mx = math.radians(40)
    assert approx(aim.aim_angle(100.0, full, mx), mx * 0.5)


def test_reticle_point_straight_up():
    rx, ry = aim.reticle_point(50.0, 10.0, 0.0, 300.0)
    assert approx(rx, 50.0) and approx(ry, 310.0)


def test_reticle_point_tilts_right_for_positive_angle():
    rx, ry = aim.reticle_point(0.0, 0.0, math.radians(90), 300.0)
    # 90deg off vertical => straight right: rx=+300, ry=0
    assert approx(rx, 300.0) and approx(ry, 0.0, eps=1e-4)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AIM TESTS PASSED")
