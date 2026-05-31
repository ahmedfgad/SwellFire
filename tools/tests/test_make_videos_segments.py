import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def test_fps_is_60():
    from tools import make_videos
    assert make_videos.FPS == 60


def test_segments_one_regular_level_per_world():
    from tools import make_videos
    segs = make_videos._segments()
    levels = [s[1] for s in segs]
    assert levels == [6, 16, 26, 36, 46, 56]
    # all non-boss (boss is level 10 of each world)
    assert all(lvl % 10 != 0 for lvl in levels)


def test_segments_carry_a_safety_frame_cap():
    from tools import make_videos
    for label, level, warmup, frames in make_videos._segments():
        # 45s of play + ~3s victory tail at 60fps -> generous cap.
        assert frames >= 2800
