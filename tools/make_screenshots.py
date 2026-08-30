"""Capture the 8 Google Play phone screenshots (720x1280 portrait) via tools/capture.py.

Scenes (mirroring CoinTex's set): title, world map, level select, gameplay
(gates swelling the squad), boss fight, level-complete + stars, shop, guide.
Each is captured by running capture.py as a subprocess so every shot gets a
clean app boot. Run: `.venv/bin/python tools/make_screenshots.py`
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools import capture_run

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "marketing")
SIZE = "720x1280"   # portrait (the game is portrait: 540x960 logical)

# (filename, kind, value, warmup-frames, frames, win)
#   kind "screen" -> meta screen name; kind "level" -> level index (gameplay)
#   win=True (level mode) -> drive the squad to the distance goal so the real
#     "Level Complete!" + stars dialog fires, then capture that modal.
# Notes on the tricky shots:
#   05 boss: the boss level (10) wipes the small starting squad in ~1s of sim
#     time, so we grab early (warmup 25) while the squad is alive and the boss
#     fills the top of the screen with squad fire streaming up at it.
#   06 win: the autoplayer can't beat a full level unaided, so --win shoves the
#     distance to the goal once the squad has grown via gates (warmup 600),
#     producing a genuine 3-star Level Complete dialog with honest stats.
SHOTS = [
    ("01_menu.png",        "screen", "menu",        25,   30,   False),
    ("02_worldmap.png",    "screen", "worldmap",    25,   30,   False),
    ("03_levelselect.png", "screen", "levelselect", 25,   30,   False),
    ("04_gameplay.png",    "level",  "4",           220,  240,  False),  # gates + squad
    ("05_boss.png",        "level",  "10",          25,   40,   False),  # world-1 boss
    ("06_win_stars.png",   "level",  "1",           300,  1200, True),   # win + stars
    ("07_shop.png",        "screen", "shop",        25,   30,   False),
    ("08_guide.png",       "screen", "guide",       25,   30,   False),
]


def main():
    os.makedirs(MEDIA, exist_ok=True)
    for fname, kind, val, warmup, frames, win in SHOTS:
        out = os.path.join(MEDIA, fname)
        if kind == "screen":
            cap_args = ["--screen", val, "--shot", out, "--size", SIZE,
                        "--warmup", warmup, "--frames", frames]
        else:
            cap_args = ["--level", val, "--shot", out, "--size", SIZE,
                        "--warmup", warmup, "--frames", frames]
            if win:
                cap_args.append("--win")
        print("capturing", fname)
        subprocess.run(capture_run.capture_cmd(cap_args), cwd=ROOT,
                       env=capture_run.capture_env(), check=True, timeout=900)
    print("8 phone screenshots written to", MEDIA)


if __name__ == "__main__":
    main()
