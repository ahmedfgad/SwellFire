"""test_combat_sfx_files.py — the new combat cues exist + are registered.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_combat_sfx_files.py"""
import os
from swellfire import audio


def test_cues_registered():
    assert audio.SFX_FILES.get("smash") == "smash.wav"
    assert audio.SFX_FILES.get("enemy_hit") == "enemy_hit.wav"


def test_wav_files_exist():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for fn in ("smash.wav", "enemy_hit.wav"):
        path = os.path.join(here, "assets", "sfx", fn)
        assert os.path.exists(path) and os.path.getsize(path) > 0, path


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COMBAT SFX FILE TESTS PASSED")
