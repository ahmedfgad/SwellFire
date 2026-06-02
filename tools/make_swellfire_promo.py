"""Build the SwellFire autoplay promo (portrait 1080x1920).

Structure: Vilvik intro -> Swellfire title ("Available on Google Play") ->
one full-level autoplay per world, end-to-end INCLUDING the pass/fail result
dialog (worlds 1-4 seeded to win, worlds 5-6 unseeded so the advanced levels
genuinely fail) -> Vilvik outro. Per-world soundtrack (world music + SFX) is
rebuilt from the capture's audio-event log. Emits chapter timestamps.

Reuses tools/capture.py (--playthrough --mp4 [--no-seed]) + tools/mix_audio.
Run: venv/bin/python tools/make_swellfire_promo.py
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import imageio_ffmpeg
import levels
from tools import capture_run, mix_audio

FF = imageio_ffmpeg.get_ffmpeg_exe()
MEDIA = os.path.join(ROOT, "swellfire_media")
VIDEOS = os.path.join(MEDIA, "videos")
BUILD = os.path.join(VIDEOS, ".promo_build")
MUSIC = os.path.join(ROOT, "assets", "music")
SFX = os.path.join(ROOT, "assets", "sfx")

SIZE = "540x960"        # capture at the game's logical size (correct scale)
OUT_SCALE = "1080:1920"  # upscale the image to 1080p portrait on mux
FPS = 60
CRF = 18
WARMUP = 60
WORLD_NAMES = {1: "Meadow", 2: "Desert", 3: "Industrial",
               4: "Snowfield", 5: "Volcano", 6: "Cosmos"}
# one representative level per world; all get upgraded weapons + a strong
# starting squad (size still varies via gates) so the autoplayer genuinely
# clears them. Worlds 1-4 pass 100%; 5-6 are best-effort.
SEGMENTS = [(1, 6), (2, 16), (3, 26), (4, 36), (5, 46), (6, 56)]
SQUAD_BONUS = 40        # strong starting squad (grows/shrinks naturally)
POWER = 8               # weapon-damage multiplier ("upgraded weapons")

INTRO = os.path.join(VIDEOS, "vilvik_intro_1920p.mp4")
TITLE = os.path.join(VIDEOS, "swellfire_title_1080x1920.mp4")
OUTRO = os.path.join(VIDEOS, "vilvik_outro_1920p.mp4")
OUTPUT = os.path.join(VIDEOS, "swellfire_autoplay_promo_1080x1920.mp4")
CHAPTERS = os.path.join(VIDEOS, "swellfire_autoplay_promo_chapters.txt")
SCROLL = getattr(levels, "SCROLL_SPEED_PX_PER_SEC", 360.0)


def cap_frames(level):
    goal = levels.get_level(level).get("distance_goal", 0) or 0
    secs = goal / SCROLL if goal else 60
    return int((secs + 10) * FPS)   # full level + a few seconds for the dialog tail


def dur(path):
    out = subprocess.run([FF, "-hide_banner", "-i", path],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True).stdout
    for tok in out.split():
        if tok.startswith("00:"):
            h, m, s = tok.strip(",").split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError("no duration: " + path)


def capture(level, seg_video, seg_json):
    args = ["--level", str(level), "--playthrough", "--size", SIZE,
            "--fps", str(FPS), "--warmup", str(WARMUP),
            "--frames", str(cap_frames(level)), "--crf", "18",
            "--squad-bonus", str(SQUAD_BONUS), "--power", str(POWER),
            "--auto-indicator", "--mp4", seg_video, "--audio", seg_json]
    subprocess.run(capture_run.capture_cmd(args), cwd=ROOT,
                   env=capture_run.capture_env(), check=True, timeout=3000)


def won(json_path):
    import json
    names = {e[2] for e in json.load(open(json_path)).get("events", [])}
    return "level_complete" in names


def mux(seg_video, seg_wav, out_mp4):
    # upscale the 540x960 capture to 1080x1920 (lanczos) and add the soundtrack
    subprocess.run([FF, "-y", "-i", seg_video, "-i", seg_wav,
                    "-vf", "scale=%s:flags=lanczos" % OUT_SCALE,
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", str(CRF), "-preset", "medium",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_mp4],
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


def ts(sec):
    sec = int(round(sec))
    return "%d:%02d" % (sec // 60, sec % 60)


def main():
    for p in (INTRO, TITLE, OUTRO):
        if not os.path.exists(p):
            sys.exit("missing card: " + p)
    os.makedirs(BUILD, exist_ok=True)

    seg_mp4s = []
    for world, level in SEGMENTS:
        seg_mp4 = os.path.join(BUILD, "seg%d.mp4" % world)
        if not os.path.exists(seg_mp4):
            print("== capturing world %d (level %d) ==" % (world, level), flush=True)
            sv = os.path.join(BUILD, "seg%d_video.mp4" % world)
            sj = os.path.join(BUILD, "seg%d.json" % world)
            for attempt in range(3):     # retry until the level is cleared
                capture(level, sv, sj)
                if won(sj):
                    break
                print("   world %d attempt %d did not win; retrying" % (
                    world, attempt + 1), flush=True)
            d = dur(sv)
            sw = os.path.join(BUILD, "seg%d.wav" % world)
            mix_audio.build_mix(sj, d, sw, MUSIC, SFX)
            mux(sv, sw, seg_mp4)
        print("   world %d: %.1fs (%s)" % (
            world, dur(seg_mp4),
            "win" if won(os.path.join(BUILD, "seg%d.json" % world)) else "fail"),
            flush=True)
        seg_mp4s.append(seg_mp4)

    clips = [INTRO, TITLE] + seg_mp4s + [OUTRO]
    print("== concatenating promo ==", flush=True)
    concat(clips, OUTPUT)

    # chapters
    lines = ["0:00 Intro"]
    t = dur(INTRO) + dur(TITLE)
    for (world, level), seg in zip(SEGMENTS, seg_mp4s):
        lines.append("%s World %d - %s" % (ts(t), world, WORLD_NAMES[world]))
        t += dur(seg)
    lines.append("%s Outro" % ts(t))
    open(CHAPTERS, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("DONE ->", OUTPUT, flush=True)


if __name__ == "__main__":
    main()
