"""Render the Swellfire title intro card at portrait 1080x1920 (or any size).

Mirrors the CoinTex title intro: the app icon animates in, then "Swellfire",
"Available on Google Play", and vilvik.com, on the dark navy backdrop used by
the Vilvik bumpers. Deterministic frame rendering via headless Chrome + NumPy
audio. Output: <outdir>/swellfire_title_<tag>.mp4
"""

import argparse
import base64
import os
import subprocess
import sys
import wave

import numpy as np
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CHS = os.environ.get(
    "CHROME_SHELL",
    os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1223/"
                       "chrome-headless-shell-linux64/chrome-headless-shell"))
ICON = os.path.join(ROOT, "swellfire_media", "icon.png")
SECONDS = 3.8
SR = 44100


def _icon_uri():
    with open(ICON, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def card_html(W, H):
    s = H / 1080.0
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#070c18;
  font-family:'DejaVu Sans','Liberation Sans',sans-serif}}
.bg{{position:fixed;inset:0;background:
  radial-gradient(ellipse 80% 70% at 50% 42%, #1b2c4d 0%, #101a33 48%, #070c18 100%);}}
.bokeh{{position:fixed;inset:0;overflow:hidden;opacity:.5}}
.bokeh i{{position:absolute;border-radius:50%;
  background:radial-gradient(circle, rgba(80,120,200,.18), rgba(80,120,200,0) 70%);}}
.stage{{position:fixed;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:{34*s:.1f}px;}}
.icon{{width:{300*s:.1f}px;height:{300*s:.1f}px;border-radius:{66*s:.1f}px;
  box-shadow:0 {18*s:.1f}px {44*s:.1f}px rgba(0,0,0,.45);
  animation:icon-in .95s cubic-bezier(.34,1.4,.5,1) both,
            bob 3.6s ease-in-out infinite 1.2s;}}
@keyframes icon-in{{0%{{opacity:0;transform:scale(.35) rotate(-28deg)}}
  60%{{opacity:1;transform:scale(1.08) rotate(7deg)}}
  100%{{opacity:1;transform:scale(1) rotate(0)}}}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY({-10*s:.1f}px)}}}}
.title{{font-size:{120*s:.1f}px;font-weight:bold;color:#f4c20a;letter-spacing:.01em;
  text-shadow:0 {3*s:.1f}px {16*s:.1f}px rgba(0,0,0,.5);
  opacity:0;animation:rise .7s ease-out both .85s;}}
.gp{{font-size:{46*s:.1f}px;font-weight:bold;color:#eef3ff;letter-spacing:.02em;
  opacity:0;animation:rise .7s ease-out both 1.2s;}}
.site{{font-size:{34*s:.1f}px;font-weight:300;color:#7f9bd6;letter-spacing:.22em;
  text-indent:.22em;opacity:0;animation:rise .7s ease-out both 1.55s;}}
@keyframes rise{{0%{{opacity:0;transform:translateY({16*s:.1f}px)}}
  100%{{opacity:1;transform:translateY(0)}}}}
.blackout{{position:fixed;inset:0;background:#000;pointer-events:none;
  animation:blackout {SECONDS}s linear both;}}
@keyframes blackout{{0%{{opacity:1}}11%{{opacity:0}}88%{{opacity:0}}100%{{opacity:1}}}}
</style></head><body>
  <div class="bg"></div>
  <div class="bokeh">
    <i style="width:{420*s:.0f}px;height:{420*s:.0f}px;left:6%;top:16%"></i>
    <i style="width:{300*s:.0f}px;height:{300*s:.0f}px;left:72%;top:10%"></i>
    <i style="width:{520*s:.0f}px;height:{520*s:.0f}px;left:58%;top:62%"></i>
    <i style="width:{260*s:.0f}px;height:{260*s:.0f}px;left:16%;top:70%"></i>
  </div>
  <div class="stage">
    <img class="icon" src="{_icon_uri()}" alt="Swellfire">
    <div class="title">Swellfire</div>
    <div class="gp">Available on Google Play</div>
    <div class="site">vilvik.com</div>
  </div>
  <div class="blackout"></div>
  <script>
    const T = parseFloat(new URLSearchParams(location.search).get('t') || '0');
    function freeze(){{document.getAnimations().forEach(a=>{{a.pause();a.currentTime=T;}});}}
    freeze(); requestAnimationFrame(()=>{{freeze();requestAnimationFrame(freeze);}});
  </script>
</body></html>"""


def _bell(t, f0, dur, amp):
    env = np.exp(-t / (dur * 0.32)) * (t >= 0)
    sig = np.zeros_like(t)
    for ratio, a in [(1.0, 1.0), (2.76, 0.55), (5.40, 0.32), (8.93, 0.18)]:
        sig += a * np.sin(2 * np.pi * f0 * ratio * t)
    return amp * env * sig


def make_audio(path):
    n = int(SECONDS * SR); t = np.arange(n) / SR
    sig = np.zeros(n, np.float32)
    c0 = int(0.9 * SR); tb = t[:n - c0]
    sig[c0:] += _bell(tb, 783.99, 1.8, 0.34) + _bell(tb, 1174.66, 1.8, 0.20)
    c1 = int(1.25 * SR); tb2 = t[:n - c1]
    sig[c1:] += _bell(tb2, 1567.98, 1.4, 0.14)
    sig = sig / (np.max(np.abs(sig)) or 1) * 0.8
    pcm = (np.clip(sig, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render(W, H, fps, work):
    import shutil
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    html = os.path.join(work, "card.html")
    open(html, "w").write(card_html(W, H))
    n = int(round(SECONDS * fps))
    frames = os.path.join(work, "frames")
    os.makedirs(frames)
    # Render concurrently but give each worker its OWN profile dir (a pool of 6),
    # so no two concurrent chrome instances share a user-data-dir (which produces
    # blank/white frames). Borrow/return profiles via a thread-safe queue.
    import queue
    from concurrent.futures import ThreadPoolExecutor
    NPROF = 6
    pool = queue.Queue()
    for k in range(NPROF):
        pdir = os.path.join(work, "prof_%d" % k)
        os.makedirs(pdir, exist_ok=True)
        pool.put(pdir)

    def one(i):
        prof = pool.get()
        try:
            out = os.path.join(frames, "f_%05d.png" % i)
            subprocess.run([CHS, "--no-sandbox", "--user-data-dir=" + prof,
                            "--no-first-run", "--no-default-browser-check",
                            "--hide-scrollbars", "--disable-gpu",
                            "--window-size=%d,%d" % (W, H), "--force-device-scale-factor=1",
                            "--virtual-time-budget=700",
                            "--run-all-compositor-stages-before-draw",
                            "--screenshot=" + out,
                            "file://%s?t=%.3f" % (html, (i / fps) * 1000.0)],
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60)
        finally:
            pool.put(prof)
    with ThreadPoolExecutor(max_workers=NPROF) as ex:
        list(ex.map(one, range(n)))
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--outdir", default=os.path.join(ROOT, "swellfire_media", "videos"))
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    work = os.path.join(a.outdir, ".title_work")
    frames = render(a.width, a.height, a.fps, work)
    wav = os.path.join(a.outdir, "swellfire_title.wav")
    make_audio(wav)
    tag = "%dx%d" % (a.width, a.height)
    out = os.path.join(a.outdir, "swellfire_title_%s.mp4" % tag)
    subprocess.run([FFMPEG, "-y", "-framerate", str(a.fps),
                    "-i", os.path.join(frames, "f_%05d.png"), "-i", wav,
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", "16", "-preset", "medium", "-r", str(a.fps), "-vsync", "cfr",
                    "-c:a", "aac", "-ar", str(SR), "-ac", "2", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    print("DONE ->", out)


if __name__ == "__main__":
    main()
