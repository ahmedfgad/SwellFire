import os, sys, subprocess, tempfile
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_screen_shot_menu():
    env = dict(os.environ, SDL_AUDIODRIVER="dummy")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "menu.png")
        r = subprocess.run([sys.executable, "tools/capture.py", "--screen", "menu",
                            "--shot", out, "--size", "1280x720", "--warmup", "20"],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        assert os.path.exists(out), r.stdout + r.stderr
        im = Image.open(out)
        assert im.size == (1280, 720)
        assert im.getextrema()[0][1] > 0  # non-blank


def test_level_sequence_writes_frames_and_audio():
    env = dict(os.environ, SDL_AUDIODRIVER="dummy")
    with tempfile.TemporaryDirectory() as d:
        outdir = os.path.join(d, "seg")
        aud = os.path.join(d, "seg.json")
        r = subprocess.run([sys.executable, "tools/capture.py", "--level", "2",
                            "--frames", "40", "--out", outdir, "--audio", aud,
                            "--size", "960x540", "--warmup", "10"],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=240)
        frames = sorted(os.listdir(outdir)) if os.path.isdir(outdir) else []
        assert len(frames) >= 35, (frames, r.stdout + r.stderr)
        assert os.path.exists(aud)
