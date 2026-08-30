"""test_aim_beam.py — the aim line is a fading multi-segment beam.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_aim_beam.py"""
from swellfire import graphics


def test_beam_has_segments_and_fades_toward_reticle():
    r = graphics.AimReticle()
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    assert len(r._segs) == graphics.AimReticle.SEGMENTS == 5
    a_squad = r._seg_colors[0].rgba[3]
    a_reticle = r._seg_colors[-1].rgba[3]
    assert a_squad > a_reticle   # brightest at the squad, fades to the reticle


def test_lock_turns_beam_red():
    r = graphics.AimReticle()
    r.set_locked(True)
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    rr, gg, bb, aa = r._seg_colors[0].rgba
    assert rr > 0.9 and bb < 0.5
    r.set_locked(False)
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    assert r._seg_colors[0].rgba[2] > 0.8   # back to cyan (blue high)


def test_show_hide_run():
    r = graphics.AimReticle()
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    r.show()
    r.hide()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AIM BEAM TESTS PASSED")
