"""Make a vertical (1080x1920) Short / Reel for SwellFire.

SwellFire is already portrait, so no reframing is needed: take the Swellfire
title, a few punchy gameplay snippets across worlds, and the Vilvik outro, and
concatenate. Reuses the promo's per-world segments. Run after the promo build:
  venv/bin/python tools/make_swellfire_short.py
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()

VIDEOS = os.path.join(ROOT, "swellfire_media", "videos")
BUILD = os.path.join(VIDEOS, ".promo_build")
WORK = os.path.join(VIDEOS, ".short_work")
OUTPUT = os.path.join(VIDEOS, "swellfire_short_9x16.mp4")

TITLE = os.path.join(VIDEOS, "swellfire_title_1080x1920.mp4")
OUTRO = os.path.join(VIDEOS, "vilvik_outro_1920p.mp4")
W, H, FPS, CRF = 1080, 1920, 60, 18

# (source, start, dur) — title, gameplay snippets from varied worlds, outro.
SLICES = [
    (TITLE, 0.3, 3.0),
    (os.path.join(BUILD, "seg1.mp4"), 8.0, 6.0),    # Meadow
    (os.path.join(BUILD, "seg2.mp4"), 22.0, 6.5),   # Desert
    (os.path.join(BUILD, "seg3.mp4"), 35.0, 7.0),   # Industrial (big squad + losses)
    (OUTRO, 0.0, 4.5),
]


def trim(src, start, dur, out):
    subprocess.run([FF, "-y", "-ss", "%.3f" % start, "-i", src, "-t", "%.3f" % dur,
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                           "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=%d" % FPS,
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", str(CRF), "-preset", "fast",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def concat(clips, out):
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    n = len(clips)
    fc = "".join("[%d:v][%d:a]" % (i, i) for i in range(n)) + \
        "concat=n=%d:v=1:a=1[v][a]" % n
    subprocess.run([FF, "-y", *inputs, "-filter_complex", fc, "-map", "[v]",
                    "-map", "[a]", "-c:v", "libx264", "-profile:v", "high",
                    "-pix_fmt", "yuv420p", "-crf", str(CRF), "-preset", "medium",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", out], check=True)


def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    clips = []
    for i, (src, start, dur) in enumerate(SLICES):
        if not os.path.exists(src):
            sys.exit("missing source: " + src)
        c = os.path.join(WORK, "s%02d.mp4" % i)
        trim(src, start, dur, c)
        clips.append(c)
        print("trimmed", os.path.basename(src), "(%.1fs)" % dur, flush=True)
    concat(clips, OUTPUT)
    shutil.rmtree(WORK, ignore_errors=True)
    print("DONE ->", OUTPUT, flush=True)


if __name__ == "__main__":
    main()
