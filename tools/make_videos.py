"""Build Swellfire's videos (portrait, the game is portrait).

  long  -> swellfire_autoplay_1080p.mp4   (2 levels per world, autoplayer-driven)

Captures gameplay at 540x960 (fast under the Xvfb software-GL display) and
ffmpeg-upscales to 1080x1920; rebuilds each segment's soundtrack from the game's
OWN wav files via tools/mix_audio; frames an intro/outro logo card. Heavy:
captures thousands of frames. Run: `venv/bin/python tools/make_videos.py long`
"""

import os
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

import levels
from tools import capture_run, mix_audio, video_core, title_cards

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "swellfire_media")
WORK = os.path.join(ROOT, "build", "video_work")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")
SFX_DIR = os.path.join(ROOT, "assets", "sfx")

FPS = 60
CAP = "540x960"          # capture size (fast); upscaled on encode
OUT_SIZE = (1080, 1920)  # portrait 1080p

WORLD_NAMES = {1: "Meadow", 2: "Desert", 3: "Industrial",
               4: "Snowfield", 5: "Volcano", 6: "Cosmos"}


WARMUP = 60          # frames to settle before the first grab
SEG_MARGIN = 300     # +5s of cap headroom for warmup + the victory-screen tail


def _segments():
    """One full regular (non-boss) level per world for worlds 1-4, played
    start->finish via the capture's --playthrough mode. Level 6 of each
    (6,16,26,36). Worlds 5-6 levels are very long at real game-time (~110s /
    ~130s each) so they're left to the screenshots/promo rather than filmed in
    full here. (label, level, warmup, frames-cap).

    The frames value is a hard SAFETY CAP only — the capture stops at the
    genuine level-complete. It's sized from the level's real length
    (distance_goal / SCROLL_SPEED * FPS) plus margin, since levels grow from
    ~30s (W1) to ~90s (W4) and a fixed cap would truncate the longer ones."""
    segs = []
    for wi in range(1, 5):
        level = (wi - 1) * 10 + 6
        secs = (levels.get_level(level)["distance_goal"]
                / levels.SCROLL_SPEED_PX_PER_SEC)
        cap = int(secs * FPS) + SEG_MARGIN
        label = "World {} · {}".format(wi, WORLD_NAMES[wi])
        segs.append((label, level, WARMUP, cap))
    return segs


def _silence(path, seconds):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(np.zeros(int(44100 * seconds), np.int16).tobytes())


def _capture_segment(level, warmup, frames, framedir, audio_json):
    args = ["--level", level, "--out", framedir, "--audio", audio_json,
            "--size", CAP, "--fps", FPS, "--warmup", warmup, "--frames", frames,
            "--playthrough"]
    subprocess.run(capture_run.capture_cmd(args), cwd=ROOT,
                   env=capture_run.capture_env(), check=True, timeout=2400)


def _card_clip(work, name, seconds, caption, out_mp4):
    cdir = os.path.join(work, name)
    n = title_cards.card_frames(cdir, seconds, FPS, OUT_SIZE, caption=caption)
    sil = os.path.join(work, name + ".wav")
    _silence(sil, n / FPS)
    video_core.encode_clip(cdir, sil, out_mp4, fps=FPS, size=OUT_SIZE)
    shutil.rmtree(cdir, ignore_errors=True)


def build_long():
    os.makedirs(MEDIA, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    clips = []

    intro = os.path.join(WORK, "00_intro.mp4")
    _card_clip(WORK, "intro", 2.5, "Grow your squad. Open fire.", intro)
    clips.append(intro)

    for i, (label, level, warmup, frames) in enumerate(_segments()):
        framedir = os.path.join(WORK, "f%02d" % i)
        audio_json = os.path.join(WORK, "a%02d.json" % i)
        print("capturing segment %d/%d: %s" % (i + 1, len(_segments()), label))
        _capture_segment(level, warmup, frames, framedir, audio_json)
        for fn in sorted(os.listdir(framedir)):
            title_cards.overlay_lower_third(os.path.join(framedir, fn), label)
        wav = os.path.join(WORK, "a%02d.wav" % i)
        mix_audio.build_mix(audio_json, frames / FPS, wav, MUSIC_DIR, SFX_DIR)
        seg_mp4 = os.path.join(WORK, "seg%02d.mp4" % i)
        video_core.encode_clip(framedir, wav, seg_mp4, fps=FPS, size=OUT_SIZE)
        clips.append(seg_mp4)
        shutil.rmtree(framedir, ignore_errors=True)

    outro = os.path.join(WORK, "zz_outro.mp4")
    _card_clip(WORK, "outro", 3.0, "60 levels · 6 worlds · 2-player versus", outro)
    clips.append(outro)

    out = os.path.join(MEDIA, "swellfire_autoplay_1080p.mp4")
    video_core.concat_clips(clips, out)
    print("wrote", out)
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    which = argv[0] if argv else "long"
    if which in ("long", "all"):
        build_long()


if __name__ == "__main__":
    main()
