"""Render portrait (1080x1920) Vilvik intro/outro bumpers reliably.

Reuses the Vilvik bumper visuals + audio from the moved package
(/home/ahmed-gad/projects/vilvik/vilvik_brand) but renders frames with the
thread-pool + per-worker-profile method used by make_swellfire_title (the
package's ProcessPool renderer produces blank frames in this environment).
Output: marketing/videos/vilvik_<intro|outro>_1920p.mp4
"""

import os
import queue
import shutil
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = "/home/ahmed-gad/projects/vilvik/vilvik_brand"
sys.path.insert(0, PKG)
import make_vilvik_cards as V  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CHS = V.CHS
W, H, FPS = 1080, 1920, 60
OUTDIR = os.path.join(ROOT, "marketing", "videos")


def render_frames(html_text, work):
    os.makedirs(work, exist_ok=True)
    html = os.path.join(work, "card.html")
    open(html, "w").write(html_text)
    frames = os.path.join(work, "frames")
    os.makedirs(frames, exist_ok=True)
    n = int(round(V.CARD_SECONDS * FPS))
    pool = queue.Queue()
    for k in range(6):
        p = os.path.join(work, "prof_%d" % k)
        os.makedirs(p, exist_ok=True)
        pool.put(p)

    def one(i):
        prof = pool.get()
        try:
            subprocess.run([CHS, "--no-sandbox", "--user-data-dir=" + prof,
                            "--no-first-run", "--no-default-browser-check",
                            "--hide-scrollbars", "--disable-gpu",
                            "--window-size=%d,%d" % (W, H),
                            "--force-device-scale-factor=1",
                            "--virtual-time-budget=700",
                            "--run-all-compositor-stages-before-draw",
                            "--screenshot=" + os.path.join(frames, "f_%05d.png" % i),
                            "file://%s?t=%.3f" % (html, (i / FPS) * 1000.0)],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60)
        finally:
            pool.put(prof)
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one, range(n)))
    return frames


def encode(frames, wav, out):
    subprocess.run([FFMPEG, "-y", "-framerate", str(FPS),
                    "-i", os.path.join(frames, "f_%05d.png"), "-i", wav,
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", "16", "-preset", "medium", "-r", str(FPS), "-vsync", "cfr",
                    "-c:a", "aac", "-ar", str(V.SR), "-ac", "2", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    svg = open(os.path.join(PKG, "vilvik_logo_animated.svg")).read()
    css = open(os.path.join(PKG, "draw-on.css")).read()
    html = V.card_html(svg, css, W, H)
    work = os.path.join(OUTDIR, ".vbump_work")
    if os.path.exists(work):
        shutil.rmtree(work)
    frames = render_frames(html, work)
    for name, mkaudio in [("intro", V.make_intro_audio), ("outro", V.make_outro_audio)]:
        wav = os.path.join(OUTDIR, "vilvik_%s.wav" % name)
        mkaudio(wav)
        out = os.path.join(OUTDIR, "vilvik_%s_1920p.mp4" % name)
        encode(frames, wav, out)
        print("wrote", out)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
