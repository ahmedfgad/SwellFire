import os, sys, subprocess

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

HARNESS = r'''
import os, sys
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.argv = ["main"]
import numpy as np
from kivy.clock import Clock
from kivy.core.window import Window
import main
from tools.capture_core import grab_frame

app = main.SwellfireApp()

def shoot(_dt):
    app.go("menu")
    # Force the logical render size. On some SDL2/Xwayland sessions the window
    # ignores the Config width/height and opens at SDL's 800x600 default; the
    # capture harness needs a deterministic frame size, so we pin it here.
    Window.size = (960, 540)
    def cap(_dt2):
        arr = grab_frame(Window)
        print("SHAPE", arr.shape)
        print("NONBLANK", int(arr.max()))
        app.stop()
    Clock.schedule_once(cap, 0.6)

Clock.schedule_once(shoot, 0.5)
app.run()
'''


def test_grab_frame_nonblank_correct_size():
    env = dict(os.environ, SDL_AUDIODRIVER="dummy")
    r = subprocess.run([sys.executable, "-c", HARNESS], cwd=os.path.abspath(ROOT),
                       env=env, capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    assert "SHAPE (540, 960, 3)" in out or "SHAPE (1080, 1920, 3)" in out, out
    # max pixel value > 0 means the menu actually rendered
    nb = [l for l in out.splitlines() if l.startswith("NONBLANK")]
    assert nb and int(nb[0].split()[1]) > 0, out
