"""Generate placeholder audio for GateRunner.

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
    """~4-second pulse loop. Bass note + pulsing 4-beat melody.

    The world index varies tempo + key so each world feels distinct without
    asking for real composed music at M2.
    """
    tempo_bpm = 90 + world * 8                # 98, 106, ..., 138
    root_hz = 196.0 * (2 ** ((world - 1) / 12))   # G3 up a semitone per world
    beat = 60.0 / tempo_bpm
    bar_n = int(4 * beat * SAMPLE_RATE)

    # bass: low fifth held for the bar
    bass = []
    env = _envelope(bar_n, attack=0.02, release=0.05)
    for i in range(bar_n):
        t = i / SAMPLE_RATE
        bass.append(math.sin(2 * math.pi * (root_hz / 2) * t) * 0.30 * env[i])

    # melody: arpeggiated triad on each beat
    intervals = [1.0, 1.25, 1.5, 1.25]   # root, third, fifth, third
    melody = []
    for k in range(4):
        n_beat = int(beat * SAMPLE_RATE)
        env_b = _envelope(n_beat, attack=0.005, release=0.06)
        freq = root_hz * intervals[k] * 2  # one octave up
        chunk = []
        for i in range(n_beat):
            t = i / SAMPLE_RATE
            value = math.sin(2 * math.pi * freq * t)
            value = math.copysign(min(0.7, abs(value)), value)  # soft clip
            chunk.append(value * 0.28 * env_b[i])
        melody.extend(chunk)

    # pad bar lengths
    while len(melody) < bar_n:
        melody.append(0.0)
    melody = melody[:bar_n]

    return _mix(bass, melody)


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

    # Music: menu + 6 world tracks.
    _write_wav(os.path.join(music_dir, "bg_music_menu.wav"), menu_music())
    print("wrote", os.path.join(music_dir, "bg_music_menu.wav"))
    for world in range(1, 7):
        path = os.path.join(music_dir, "bg_music_world{}.wav".format(world))
        _write_wav(path, world_music(world))
        print("wrote", path)

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
