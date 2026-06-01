"""Procedurally generate the short UI/action sound effects under assets/sfx/.

Stdlib only (wave + math + struct) so it runs anywhere the repo does. These
are simple synthesized cues (tones, sweeps, filtered noise) — placeholders in
the same lo-fi spirit as the rest of the bank, but distinct enough that each
user action reads by ear. Re-run to regenerate:

    python tools/gen_sfx.py

Existing hand-made wavs (click/coin/hit/…) are left untouched unless their
name appears in GENERATORS below.
"""

import math
import os
import struct
import wave

SR = 22050           # sample rate
AMP = 0.5            # headroom so layered tones don't clip
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "sfx")


def _env(i, n, attack=0.01, release=0.25):
    """Attack/decay amplitude envelope in [0,1] for sample i of n."""
    t = i / SR
    dur = n / SR
    a = min(1.0, t / attack) if attack > 0 else 1.0
    rel_start = dur - release
    r = 1.0 if t < rel_start else max(0.0, 1.0 - (t - rel_start) / max(release, 1e-4))
    return a * r


def tone(freq, dur, *, kind="sine", attack=0.01, release=None, vib=0.0, vibhz=0.0):
    """A single tone. kind: sine|square|saw. vib = ± freq Hz at vibhz."""
    n = int(SR * dur)
    if release is None:
        release = dur * 0.5
    out = []
    for i in range(n):
        t = i / SR
        f = freq + (vib * math.sin(2 * math.pi * vibhz * t) if vib else 0.0)
        phase = 2 * math.pi * f * t
        if kind == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif kind == "saw":
            s = 2.0 * ((f * t) % 1.0) - 1.0
        else:
            s = math.sin(phase)
        out.append(s * _env(i, n, attack, release))
    return out


def sweep(f0, f1, dur, *, kind="sine", attack=0.01, release=None):
    n = int(SR * dur)
    if release is None:
        release = dur * 0.4
    out = []
    for i in range(n):
        t = i / SR
        f = f0 + (f1 - f0) * (i / max(1, n - 1))
        phase = 2 * math.pi * f * t
        if kind == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif kind == "saw":
            s = 2.0 * ((f * t) % 1.0) - 1.0
        else:
            s = math.sin(phase)
        out.append(s * _env(i, n, attack, release))
    return out


def noise(dur, *, smooth=1, release=0.2):
    """White/filtered noise via a tiny LCG (deterministic, no deps)."""
    n = int(SR * dur)
    seed = 1234567
    raw = []
    for _ in range(n):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        raw.append((seed / 0x3FFFFFFF) - 1.0)
    if smooth > 1:                       # moving average = crude low-pass
        sm = []
        acc = 0.0
        for i in range(n):
            acc += raw[i]
            if i >= smooth:
                acc -= raw[i - smooth]
            sm.append(acc / min(i + 1, smooth))
        raw = sm
    return [raw[i] * _env(i, n, 0.005, release) for i in range(n)]


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, s in enumerate(t):
            out[i] += s
    return out


def seq(*tracks):
    out = []
    for t in tracks:
        out.extend(t)
    return out


def silence(dur):
    return [0.0] * int(SR * dur)


def save(name, samples):
    peak = max((abs(s) for s in samples), default=1.0) or 1.0
    norm = AMP / peak
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s * norm)) * 32767))
            for s in samples))
    return path


# name -> sample builder. Only these are (re)generated.
GENERATORS = {
    # Grenade boom: low thump + filtered noise blast.
    "explosion.wav": lambda: mix(
        tone(70, 0.45, kind="sine", release=0.4),
        noise(0.45, smooth=6, release=0.42)),
    # Shield up: warm rising shimmer.
    "shield.wav": lambda: mix(
        sweep(440, 880, 0.35, kind="sine"),
        sweep(660, 1320, 0.35, kind="sine")),
    # Reinforcements: bright ascending triad (power-up).
    "reinforce.wav": lambda: seq(
        tone(523, 0.09, kind="square"), tone(659, 0.09, kind="square"),
        tone(784, 0.16, kind="square")),
    # Freeze: icy high shimmer gliding down with tremolo.
    "freeze.wav": lambda: mix(
        sweep(1400, 900, 0.4, kind="sine"),
        tone(1900, 0.4, kind="sine", vib=40, vibhz=18)),
    # Overdrive: energetic buzzy rev upward.
    "overdrive.wav": lambda: sweep(220, 660, 0.4, kind="saw"),
    # Magnet: low wobbling hum.
    "magnet.wav": lambda: tone(160, 0.5, kind="sine", vib=30, vibhz=7),
    # Shop purchase: quick bright two-note "ka-ching".
    "purchase.wav": lambda: seq(
        tone(880, 0.08, kind="square"), tone(1320, 0.18, kind="square")),
    # Weapon upgrade: ascending four-note arpeggio.
    "upgrade.wav": lambda: seq(
        tone(523, 0.07, kind="square"), tone(659, 0.07, kind="square"),
        tone(784, 0.07, kind="square"), tone(1047, 0.16, kind="square")),
    # Error / can't afford: low double buzz.
    "error.wav": lambda: seq(
        tone(170, 0.10, kind="square"), silence(0.04),
        tone(140, 0.14, kind="square")),
    # Pause: soft short blip.
    "pause.wav": lambda: tone(420, 0.12, kind="sine"),
    # Weapon swap: mechanical click — short noise tick + low thunk.
    "weapon_swap.wav": lambda: seq(
        noise(0.05, smooth=2, release=0.04),
        tone(240, 0.08, kind="square")),
    # UI open: soft quick rising whoosh for modals appearing.
    "ui_open.wav": lambda: sweep(300, 620, 0.18, kind="sine", release=0.12),
    # Enemy smash (death): low square crunch + filtered noise burst.
    "smash.wav": lambda: mix(
        tone(110, 0.18, kind="square", release=0.16),
        noise(0.18, smooth=3, release=0.16)),
    # Enemy hit (non-lethal): short mid thud, quick decay.
    "enemy_hit.wav": lambda: mix(
        sweep(220, 120, 0.09, kind="square", release=0.07),
        noise(0.07, smooth=2, release=0.06)),
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, build in GENERATORS.items():
        save(name, build())
        print("wrote", name)


if __name__ == "__main__":
    main()
