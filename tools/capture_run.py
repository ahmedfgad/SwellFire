"""Launch tools/capture.py in a portrait-friendly virtual display.

The game is portrait (540x960 logical), and this dev machine's real (Xwayland)
screen is shorter than the portrait window — SDL can't create the window on it
(resize/poll errors). When `xvfb-run` is available we run capture.py under a
tall virtual X screen, which both fixes window creation AND yields full-res,
unclipped frames (so screenshots/videos can be true 1080x1920). Falls back to
the real display when Xvfb is absent.
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Virtual screen big enough for App Store's 2064x2752 iPad capture with margin.
_XVFB_SCREEN = "2304x3072x24"


def have_xvfb():
    return shutil.which("xvfb-run") is not None


def capture_cmd(args):
    """Full argv to run `tools/capture.py <args>`, wrapped in xvfb-run if present."""
    base = [sys.executable, "tools/capture.py"] + [str(a) for a in args]
    if have_xvfb():
        return ["xvfb-run", "-a", "-s", "-screen 0 " + _XVFB_SCREEN] + base
    return base


def capture_env(density=None):
    """Isolated capture env with optional mobile display density."""
    env = dict(os.environ)
    capture_home = tempfile.mkdtemp(prefix="swellfire-capture-")
    env["XDG_DATA_HOME"] = capture_home
    env["XDG_CONFIG_HOME"] = capture_home
    env["KIVY_HOME"] = os.path.join(capture_home, "kivy")
    if density is not None:
        env["KIVY_METRICS_DENSITY"] = str(density)
    env["SDL_AUDIODRIVER"] = "dummy"
    if have_xvfb():
        env["SDL_VIDEODRIVER"] = "x11"
    return env
