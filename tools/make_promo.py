"""Promo video (portrait 1080x1920, ~35s): logo intro -> fast highlight windows
(squad growth, combat across worlds, a boss fight) -> end card. Captures at
540x960 and upscales on encode. Run: `venv/bin/python tools/make_promo.py`
"""

import os
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from tools import capture_run, mix_audio, video_core, title_cards

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "swellfire_media")
WORK = os.path.join(ROOT, "build", "promo_work")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")
SFX_DIR = os.path.join(ROOT, "assets", "sfx")

FPS = 30
CAP = "540x960"
OUT_SIZE = (1080, 1920)

# (level, warmup, frames, caption) — regular levels across varied worlds.
# (Boss levels wipe the small starting squad in ~1s, so they film as a "Level
# Failed" dialog rather than a fight; the boss is showcased in the screenshots.)
WINDOWS = [
    (3,  60, 180, "Multiply your squad"),
    (13, 50, 180, "Swarm the desert"),
    (23, 50, 180, "Industrial firepower"),
    (33, 50, 150, "Frostbite assault"),
]


def _silence(path, seconds):
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(np.zeros(int(44100 * seconds), np.int16).tobytes())


def _card(work, name, seconds, caption, mp4):
    cdir = os.path.join(work, name)
    n = title_cards.card_frames(cdir, seconds, FPS, OUT_SIZE, caption=caption)
    _silence(os.path.join(work, name + ".wav"), n / FPS)
    video_core.encode_clip(cdir, os.path.join(work, name + ".wav"), mp4,
                           fps=FPS, size=OUT_SIZE)
    shutil.rmtree(cdir, ignore_errors=True)


def build_promo():
    os.makedirs(MEDIA, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    clips = []

    intro = os.path.join(WORK, "00_intro.mp4")
    _card(WORK, "intro", 2.5, "Grow your squad. Open fire.", intro)
    clips.append(intro)

    for i, (level, warmup, frames, caption) in enumerate(WINDOWS):
        framedir = os.path.join(WORK, "f%d" % i)
        aud = os.path.join(WORK, "a%d.json" % i)
        subprocess.run(capture_run.capture_cmd(
            ["--level", level, "--out", framedir, "--audio", aud, "--size", CAP,
             "--fps", FPS, "--warmup", warmup, "--frames", frames]),
            cwd=ROOT, env=capture_run.capture_env(), check=True, timeout=900)
        for fn in sorted(os.listdir(framedir)):
            title_cards.overlay_caption(os.path.join(framedir, fn), caption)
        wav = os.path.join(WORK, "a%d.wav" % i)
        mix_audio.build_mix(aud, frames / FPS, wav, MUSIC_DIR, SFX_DIR)
        seg = os.path.join(WORK, "seg%d.mp4" % i)
        video_core.encode_clip(framedir, wav, seg, fps=FPS, size=OUT_SIZE)
        clips.append(seg)
        shutil.rmtree(framedir, ignore_errors=True)

    outro = os.path.join(WORK, "zz_outro.mp4")
    _card(WORK, "outro", 3.0, "60 levels · 6 worlds · 2-player versus", outro)
    clips.append(outro)

    out = os.path.join(MEDIA, "swellfire_promo.mp4")
    video_core.concat_clips(clips, out)
    print("wrote", out)
    return out


def main():
    build_promo()


if __name__ == "__main__":
    main()
