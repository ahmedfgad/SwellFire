"""Generate placeholder audio for Swellfire.

Produces the menu track, one per-world track (worlds 1..6), and the SFX bank
(click, shoot, hit, enemy_death, gate_pickup, coin, level_complete, death,
victory, reload) as 16-bit mono WAV files using only the Python stdlib.
Everything is clearly tagged "placeholder" in the asset README and is replaced
during the M14 asset pass.

Usage:
    python tools/gen_placeholder_audio.py [--out assets]

Re-running overwrites existing files.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import struct
import wave

SAMPLE_RATE = 22050      # plenty for placeholder content; smaller files than 44.1k


# --- low-level helpers ----------------------------------------------------

def _write_wav(path: str, samples: list[float]) -> None:
    """Write a 16-bit mono WAV from a list of floats in [-1, 1]."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, sample))
            frames += struct.pack("<h", int(value * 32767))
        out.writeframes(bytes(frames))


def _envelope(length: int, attack=0.005, release=0.05) -> list[float]:
    """Simple ADSR-ish envelope sized to the buffer."""
    out = [1.0] * length
    attack_n = max(1, int(attack * SAMPLE_RATE))
    release_n = max(1, int(release * SAMPLE_RATE))
    for i in range(min(attack_n, length)):
        out[i] *= i / attack_n
    for i in range(min(release_n, length)):
        out[length - 1 - i] *= i / release_n
    return out


def _tone(freq: float, duration: float, shape: str = "sine", amp: float = 0.6) -> list[float]:
    """Single-pitched buffer (sine, square or triangle)."""
    n = int(duration * SAMPLE_RATE)
    env = _envelope(n)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        phase = 2 * math.pi * freq * t
        if shape == "sine":
            value = math.sin(phase)
        elif shape == "square":
            value = 1.0 if math.sin(phase) >= 0 else -1.0
        elif shape == "triangle":
            value = 2 / math.pi * math.asin(math.sin(phase))
        elif shape == "noise":
            value = random.uniform(-1, 1)
        else:
            value = math.sin(phase)
        out.append(value * amp * env[i])
    return out


def _mix(*buffers: list[float]) -> list[float]:
    """Sample-wise sum of several equal-length buffers, clipped."""
    if not buffers:
        return []
    length = max(len(buf) for buf in buffers)
    out = [0.0] * length
    for buf in buffers:
        for i in range(len(buf)):
            out[i] += buf[i]
    # avoid clipping by dividing through if mix is hot
    peak = max(abs(s) for s in out) or 1.0
    if peak > 0.95:
        scale = 0.95 / peak
        out = [s * scale for s in out]
    return out


def _concat(*buffers: list[float]) -> list[float]:
    out: list[float] = []
    for buf in buffers:
        out.extend(buf)
    return out


# --- SFX bank -------------------------------------------------------------

def sfx_click() -> list[float]:
    """Short crisp tick — UI button press."""
    return _tone(1800, 0.04, "sine", amp=0.55)


def sfx_shoot() -> list[float]:
    """Filtered noise burst — weapon discharge."""
    n = int(0.08 * SAMPLE_RATE)
    env = _envelope(n, attack=0.001, release=0.04)
    out = []
    last = 0.0
    for i in range(n):
        raw = random.uniform(-1, 1)
        last = last * 0.6 + raw * 0.4    # crude low-pass
        out.append(last * 0.8 * env[i])
    return out


def sfx_hit() -> list[float]:
    """Low thud + a quick click on top."""
    thud = _tone(120, 0.10, "sine", amp=0.7)
    click = _tone(1200, 0.02, "triangle", amp=0.4)
    return _mix(thud, click + [0.0] * (len(thud) - len(click)))


def sfx_enemy_death() -> list[float]:
    """Pitched descending whoosh from ~600 Hz to ~200 Hz."""
    duration = 0.30
    n = int(duration * SAMPLE_RATE)
    env = _envelope(n, attack=0.005, release=0.15)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 600 - 400 * (t / duration)
        out.append(math.sin(2 * math.pi * freq * t) * 0.6 * env[i])
    return out


def sfx_gate_pickup() -> list[float]:
    """Ascending two-note chime."""
    a = _tone(660, 0.10, "sine", amp=0.55)
    b = _tone(990, 0.16, "sine", amp=0.50)
    return _concat(a, b)


def sfx_coin() -> list[float]:
    """Bright two-tone — coin pickup."""
    a = _tone(1200, 0.05, "triangle", amp=0.55)
    b = _tone(1600, 0.08, "triangle", amp=0.55)
    return _concat(a, b)


def sfx_level_complete() -> list[float]:
    """C-E-G arpeggio."""
    return _concat(
        _tone(523, 0.18, "sine", amp=0.6),   # C5
        _tone(659, 0.18, "sine", amp=0.6),   # E5
        _tone(784, 0.30, "sine", amp=0.65),  # G5
    )


def sfx_death() -> list[float]:
    """Descending minor — game over."""
    return _concat(
        _tone(440, 0.18, "sine", amp=0.6),
        _tone(370, 0.18, "sine", amp=0.55),
        _tone(294, 0.30, "sine", amp=0.55),
    )


def sfx_victory() -> list[float]:
    """Three rising chords."""
    return _concat(
        _mix(_tone(523, 0.18, amp=0.4), _tone(659, 0.18, amp=0.4), _tone(784, 0.18, amp=0.4)),
        _mix(_tone(587, 0.18, amp=0.4), _tone(740, 0.18, amp=0.4), _tone(880, 0.18, amp=0.4)),
        _mix(_tone(659, 0.30, amp=0.4), _tone(831, 0.30, amp=0.4), _tone(988, 0.30, amp=0.4)),
    )


def sfx_reload() -> list[float]:
    """Two clicks — magazine slot + bolt."""
    return _concat(
        _tone(800, 0.04, "square", amp=0.4),
        [0.0] * int(0.06 * SAMPLE_RATE),
        _tone(1100, 0.05, "square", amp=0.45),
    )


# --- music tracks ---------------------------------------------------------

def menu_music() -> list[float]:
    """~4-second calm loop on top of a slow bass triad."""
    bar = 1.0   # one chord per second
    chords = [
        (220.0, 277.2, 329.6),  # Am
        (196.0, 246.9, 293.7),  # G
        (174.6, 220.0, 261.6),  # F
        (220.0, 277.2, 329.6),  # Am
    ]
    n_per_bar = int(bar * SAMPLE_RATE)
    track: list[float] = []
    for f1, f2, f3 in chords:
        env = _envelope(n_per_bar, attack=0.05, release=0.1)
        out = [0.0] * n_per_bar
        for i in range(n_per_bar):
            t = i / SAMPLE_RATE
            # soft sine triad with a slight detune for body
            s = (math.sin(2 * math.pi * f1 * t)
                 + 0.7 * math.sin(2 * math.pi * f2 * t)
                 + 0.6 * math.sin(2 * math.pi * f3 * t)) / 3.0
            out[i] = s * 0.32 * env[i]
        track.extend(out)
    return track


def world_music(world: int) -> list[float]:
    """Per-world ~4-second loop. Each world has a distinct voice:

        W1 Meadow    — slow sine triads (gentle, pastoral)
        W2 Desert    — minor key, triangle melody, swung rhythm
        W3 Industrial— square-wave riff, fast tempo, mechanical pulse
        W4 Snowfield — bell-like sine arpeggio, sparse, high pitch
        W5 Volcano   — sub-bass thump + driving square stab
        W6 Cosmos    — glitchy low+high overlay, slow chord pad
    """
    if world == 1:
        return _world_meadow()
    if world == 2:
        return _world_desert()
    if world == 3:
        return _world_industrial()
    if world == 4:
        return _world_snowfield()
    if world == 5:
        return _world_volcano()
    return _world_cosmos()


# Tempo + style helpers — each world has its own arrangement so the
# placeholders read as distinct even before real music drops in.

def _bar_seconds(bpm: float, beats: int = 4) -> float:
    return 60.0 / bpm * beats


def _world_meadow() -> list[float]:
    bpm = 92.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # I - vi - IV - V (C - Am - F - G) sustained sine triads, soft + airy.
    chords = [
        (261.63, 329.63, 392.00),    # C
        (220.00, 261.63, 329.63),    # Am
        (174.61, 220.00, 261.63),    # F
        (196.00, 246.94, 293.66),    # G
    ]
    out: list[float] = []
    per_chord = bar_n // 4
    for c in chords:
        env = _envelope(per_chord, attack=0.08, release=0.15)
        for i in range(per_chord):
            t = i / SAMPLE_RATE
            s = (math.sin(2 * math.pi * c[0] * t)
                 + 0.7 * math.sin(2 * math.pi * c[1] * t)
                 + 0.5 * math.sin(2 * math.pi * c[2] * t)) / 3.0
            out.append(s * 0.32 * env[i])
    return out


def _world_desert() -> list[float]:
    bpm = 108.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # Em - D - C - B7 — minor-key, triangle-wave melody syncopated 6-8.
    roots = (164.81, 146.83, 130.81, 123.47)
    fifths = (246.94, 220.00, 196.00, 185.00)
    out: list[float] = []
    per_chord = bar_n // 4
    for r, f in zip(roots, fifths):
        env = _envelope(per_chord, attack=0.02, release=0.08)
        for i in range(per_chord):
            t = i / SAMPLE_RATE
            # Triangle root
            tri = 2 / math.pi * math.asin(math.sin(2 * math.pi * r * t))
            # Sine fifth
            sin = math.sin(2 * math.pi * f * t)
            # 6/8 syncopation: drop in/out 3 times per bar
            mod = 1.0 if int(t * 6) % 2 == 0 else 0.4
            out.append((tri * 0.4 + sin * 0.4) * 0.30 * env[i] * mod)
    return out


def _world_industrial() -> list[float]:
    bpm = 132.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # Driving 4/4 square-wave riff: F5 power chord pulse.
    base = 174.61   # F3
    out: list[float] = []
    beat_n = bar_n // 8
    for k in range(8):
        env = _envelope(beat_n, attack=0.003, release=0.03)
        for i in range(beat_n):
            t = i / SAMPLE_RATE
            # Off-beats accent
            accent = 0.95 if k % 2 == 0 else 0.55
            # Power chord: root + fifth, square wave
            sq1 = 1.0 if math.sin(2 * math.pi * base * t) >= 0 else -1.0
            sq2 = 1.0 if math.sin(2 * math.pi * base * 1.5 * t) >= 0 else -1.0
            out.append((sq1 * 0.5 + sq2 * 0.3) * 0.22 * env[i] * accent)
    return out


def _world_snowfield() -> list[float]:
    bpm = 78.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # Sparse bell arpeggio in E major, high pitches with long decays.
    notes = (659.26, 783.99, 987.77, 783.99,    # E5 G5 B5 G5
             739.99, 880.00, 1108.73, 880.00)   # F#5 A5 C#6 A5
    out: list[float] = []
    per_note = bar_n // 8
    for f in notes:
        env = _envelope(per_note, attack=0.005, release=0.40)
        for i in range(per_note):
            t = i / SAMPLE_RATE
            # Bell = fundamental + sparkly partials
            s = (math.sin(2 * math.pi * f * t)
                 + 0.3 * math.sin(2 * math.pi * f * 2 * t)
                 + 0.12 * math.sin(2 * math.pi * f * 3 * t))
            out.append(s * 0.22 * env[i])
    return out


def _world_volcano() -> list[float]:
    bpm = 124.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # Sub-bass thump + driving root-5 square stabs in C minor.
    base = 130.81    # C3
    out: list[float] = []
    beat_n = bar_n // 8
    for k in range(8):
        env = _envelope(beat_n, attack=0.002, release=0.04)
        for i in range(beat_n):
            t = i / SAMPLE_RATE
            # Sub-bass pulse on every beat
            sub = math.sin(2 * math.pi * base * 0.5 * t)
            # Square stab on accent beats
            stab = (1.0 if math.sin(2 * math.pi * base * t) >= 0 else -1.0) \
                * (1.0 if k % 2 == 0 else 0.0)
            out.append((sub * 0.4 + stab * 0.4) * 0.28 * env[i])
    return out


def _world_cosmos() -> list[float]:
    bpm = 70.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    # Slow chord pad (D-A-Bm-G) with a high glitchy sine overlay.
    roots = (146.83, 220.00, 246.94, 196.00)
    out: list[float] = []
    per_chord = bar_n // 4
    for k, r in enumerate(roots):
        env = _envelope(per_chord, attack=0.15, release=0.20)
        for i in range(per_chord):
            t = i / SAMPLE_RATE
            # Pad: root + fifth + octave
            pad = (math.sin(2 * math.pi * r * t)
                   + 0.6 * math.sin(2 * math.pi * r * 1.5 * t)
                   + 0.3 * math.sin(2 * math.pi * r * 2 * t)) / 3.0
            # Glitch overlay: very high sine with random amplitude bursts
            glitch = math.sin(2 * math.pi * 2400.0 * t) \
                * (1.0 if int(t * 16) % 7 == 0 else 0.0) * 0.15
            out.append((pad * 0.30 + glitch) * env[i])
    return out


def boss_music() -> list[float]:
    """High-tension boss track: driving sub-bass + minor stabs + alarm pulse.

    Used by audio.AudioManager for every world's level-10 boss fight.
    """
    bpm = 138.0
    bar_n = int(_bar_seconds(bpm) * SAMPLE_RATE)
    base = 110.00    # A2 — low and ominous
    out: list[float] = []
    beat_n = bar_n // 16
    for k in range(16):
        env = _envelope(beat_n, attack=0.001, release=0.03)
        for i in range(beat_n):
            t = i / SAMPLE_RATE
            # Sub-bass on every 4th 16th
            sub = math.sin(2 * math.pi * base * t) if k % 4 == 0 else 0.0
            # Minor-third square stab on off-beats
            stab_freq = base * (2 ** (3 / 12))    # minor third up
            stab = (1.0 if math.sin(2 * math.pi * stab_freq * 2 * t) >= 0 else -1.0)
            stab = stab if k % 2 == 1 else 0.0
            # Alarm pulse: rising siren-like sine on every 8th
            alarm = math.sin(2 * math.pi * (440 + 200 * math.sin(t * 8)) * t)
            alarm = alarm if k % 8 == 7 else 0.0
            out.append((sub * 0.55 + stab * 0.30 + alarm * 0.20)
                       * 0.30 * env[i])
    return out


# --- driver ---------------------------------------------------------------

SFX_BANK = {
    "click.wav":          sfx_click,
    "shoot.wav":          sfx_shoot,
    "hit.wav":            sfx_hit,
    "enemy_death.wav":    sfx_enemy_death,
    "gate_pickup.wav":    sfx_gate_pickup,
    "coin.wav":           sfx_coin,
    "level_complete.wav": sfx_level_complete,
    "death.wav":          sfx_death,
    "victory.wav":        sfx_victory,
    "reload.wav":         sfx_reload,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="assets",
                        help="Output asset directory (default: ./assets)")
    args = parser.parse_args()

    music_dir = os.path.join(args.out, "music")
    sfx_dir = os.path.join(args.out, "sfx")

    # Music: menu + 6 world tracks + boss track.
    _write_wav(os.path.join(music_dir, "bg_music_menu.wav"), menu_music())
    print("wrote", os.path.join(music_dir, "bg_music_menu.wav"))
    for world in range(1, 7):
        path = os.path.join(music_dir, "bg_music_world{}.wav".format(world))
        _write_wav(path, world_music(world))
        print("wrote", path)
    boss_path = os.path.join(music_dir, "bg_music_boss.wav")
    _write_wav(boss_path, boss_music())
    print("wrote", boss_path)

    # SFX bank.
    for filename, builder in SFX_BANK.items():
        path = os.path.join(sfx_dir, filename)
        _write_wav(path, builder())
        print("wrote", path)

    # Drop a README in each dir so the placeholder status is obvious to anyone
    # browsing the source tree.
    note = (
        "# PLACEHOLDER AUDIO\n\n"
        "Every WAV in this folder was generated by tools/gen_placeholder_audio.py\n"
        "and is intentionally minimal (sine + envelope tones, low-pass noise for\n"
        "shots). The M14 asset pass replaces them with composed music and\n"
        "designed SFX. Do not ship to users until then.\n"
    )
    with open(os.path.join(music_dir, "README.md"), "w") as f:
        f.write(note)
    with open(os.path.join(sfx_dir, "README.md"), "w") as f:
        f.write(note)


if __name__ == "__main__":
    main()
