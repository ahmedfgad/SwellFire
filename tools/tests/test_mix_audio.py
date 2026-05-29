import os, sys, json, wave, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tools import mix_audio

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SFX_DIR = os.path.join(ROOT, "assets", "sfx")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")


def test_mix_duration_matches_request(tmp_path):
    evjson = tmp_path / "ev.json"
    evjson.write_text(json.dumps({"fps": 60, "events": [
        [0.0, "music", "world:1"],
        [0.5, "sfx", "gate_pickup"],
        [1.0, "sfx", "explosion"],
    ]}))
    out = tmp_path / "mix.wav"
    mix_audio.build_mix(str(evjson), duration_sec=3.0, out_path=str(out),
                        music_dir=MUSIC_DIR, sfx_dir=SFX_DIR)
    assert out.exists()
    with wave.open(str(out)) as w:
        secs = w.getnframes() / w.getframerate()
        assert abs(secs - 3.0) < 0.05


def test_shoot_is_rate_limited():
    # 100 shoot events in 1s should be throttled to far fewer overlays.
    ev = [[i * 0.01, "sfx", "shoot"] for i in range(100)]
    kept = mix_audio.rate_limit_events(ev, min_gap={"shoot": 0.12})
    shoots = [e for e in kept if e[2] == "shoot"]
    assert len(shoots) <= 10
