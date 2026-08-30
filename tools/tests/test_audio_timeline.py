import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from swellfire import audio


def test_timeline_off_by_default():
    am = audio.AudioManager("")          # no asset dir -> no real sounds
    am.play_sfx("shoot")
    assert am.capture_log is None        # not recording


def test_timeline_records_sfx_and_music_with_sim_clock():
    am = audio.AudioManager("")
    t = {"now": 0.0}
    am.start_capture_log(clock=lambda: t["now"])
    am.play_sfx("shoot")
    t["now"] = 1.25
    am.play_level_music(3)
    t["now"] = 2.0
    am.play_sfx("explosion")
    log = am.capture_log
    assert log[0] == (0.0, "sfx", "shoot")
    assert log[1] == (1.25, "music", "world:3")
    assert log[2] == (2.0, "sfx", "explosion")
