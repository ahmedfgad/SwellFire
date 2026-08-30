"""Capture App Store-ready iPhone 6.9-inch and iPad 13-inch screenshots.

These are real deterministic game renders, not stretched copies of the Google
Play images. Run from the repository root after installing requirements-media:

    python tools/make_app_store_screenshots.py
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools import capture_run
from tools.make_screenshots import SHOTS


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "marketing", "app_store")

# Apple accepts these exact portrait dimensions for their current largest
# iPhone and iPad screenshot groups. One complete set per device class is enough
# for App Store Connect to scale to smaller displays.
# Retina density keeps dp/sp layout equivalent to the physical Apple device;
# Xvfb otherwise reports density 1 and treats every output pixel as one dp.
DEVICE_SETS = (
    ("iphone_6_9", "1284x2778", 3),
    ("ipad_13", "2064x2752", 2),
)


def main() -> None:
    for directory, size, density in DEVICE_SETS:
        output_dir = os.path.join(MEDIA, directory)
        os.makedirs(output_dir, exist_ok=True)
        for filename, kind, value, warmup, frames, win in SHOTS:
            output = os.path.join(output_dir, filename)
            if kind == "screen":
                args = ["--screen", value, "--shot", output, "--size", size,
                        "--warmup", warmup, "--frames", frames]
            else:
                args = ["--level", value, "--shot", output, "--size", size,
                        "--warmup", warmup, "--frames", frames]
                if win:
                    args.append("--win")
                if filename == "05_boss.png":
                    args.append("--static-shot")
            print(f"capturing {directory}/{filename} at {size}")
            subprocess.run(
                capture_run.capture_cmd(args),
                cwd=ROOT,
                env=capture_run.capture_env(density=density),
                check=True,
                timeout=1200,
            )
    print(f"App Store screenshots written to {MEDIA}")


if __name__ == "__main__":
    main()
