import os, sys, subprocess

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

# Boot the app in a subprocess (needs a display); after build(), assert the
# app.icon points at icon.png. We use a tiny harness that builds and exits.
HARNESS = r'''
import os, sys
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.argv = ["main"]
import main
app = main.SwellfireApp()
app.build()
assert app.icon and app.icon.endswith("icon.png"), app.icon
print("ICON_OK", app.icon)
'''


def test_build_sets_window_icon():
    env = dict(os.environ, SDL_AUDIODRIVER="dummy")
    r = subprocess.run([sys.executable, "-c", HARNESS], cwd=os.path.abspath(ROOT),
                       env=env, capture_output=True, text=True, timeout=120)
    assert "ICON_OK" in r.stdout, r.stdout + r.stderr
