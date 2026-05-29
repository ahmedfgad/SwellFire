"""Generate composed background music for Gate Runner (all 8 tracks).

Replaces the minimal stdlib placeholders from gen_placeholder_audio.py with
higher-fidelity, melodic, seamless-looping tracks using a small numpy synth.

Dev/build-time only: numpy is NOT a runtime/mobile dependency. The WAVs ship
pre-generated under assets/music/. Re-running overwrites the existing files.

Usage:
    python tools/gen_world_music.py [--out assets/music] [--only world3,boss]
"""

from __future__ import annotations

import argparse
import os
import wave

import numpy as np

SAMPLE_RATE = 44100
LOOP_SECONDS = 20.0          # nominal target; actual length snaps to whole bars
DEFAULT_OUT = os.path.join("assets", "music")


def bars_for(bpm: float, beats_per_bar: int = 4) -> int:
    """Whole bars whose total duration is closest to LOOP_SECONDS."""
    bar_sec = 60.0 / bpm * beats_per_bar
    return max(1, round(LOOP_SECONDS / bar_sec))


def _t(n: int) -> np.ndarray:
    """Time vector of length n in seconds."""
    return np.arange(n, dtype=np.float64) / SAMPLE_RATE


def note_freq(midi: float) -> float:
    """MIDI note number -> frequency in Hz (A4 = 69 = 440 Hz)."""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def osc_sine(freq: float, n: int) -> np.ndarray:
    return np.sin(2 * np.pi * freq * _t(n))


def osc_tri(freq: float, n: int) -> np.ndarray:
    # triangle via arcsin of sine -> band-limited, no harsh edges
    return (2.0 / np.pi) * np.arcsin(np.sin(2 * np.pi * freq * _t(n)))


def _bandlimited(freq: float, n: int, weights) -> np.ndarray:
    """Sum harmonics k*freq with given weights, skipping any above Nyquist."""
    t = _t(n)
    out = np.zeros(n)
    nyq = SAMPLE_RATE / 2.0
    for k, w in enumerate(weights, start=1):
        if k * freq >= nyq:
            break
        out += w * np.sin(2 * np.pi * k * freq * t)
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


def osc_saw(freq: float, n: int) -> np.ndarray:
    # band-limited saw: harmonic k has amplitude 1/k
    return _bandlimited(freq, n, [1.0 / k for k in range(1, 25)])


def osc_soft_square(freq: float, n: int) -> np.ndarray:
    # band-limited square: odd harmonics 1/k only -> rounded, not buzzy
    weights = [1.0 / k if k % 2 == 1 else 0.0 for k in range(1, 25)]
    return _bandlimited(freq, n, weights)


def adsr(n: int, attack=0.01, decay=0.08, sustain=0.7, release=0.12) -> np.ndarray:
    """ADSR envelope sized to n samples; clamps segments to fit."""
    a = min(int(attack * SAMPLE_RATE), n)
    d = min(int(decay * SAMPLE_RATE), n - a)
    r = min(int(release * SAMPLE_RATE), n - a - d)
    s = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0.0, 1.0, a, endpoint=False) if a else np.array([]),
        np.linspace(1.0, sustain, d, endpoint=False) if d else np.array([]),
        np.full(s, sustain),
        np.linspace(sustain, 0.0, r) if r else np.array([]),
    ])
    if env.shape[0] < n:
        env = np.concatenate([env, np.zeros(n - env.shape[0])])
    return env[:n]


def lowpass(x: np.ndarray, cutoff: float, resonance: float = 0.0) -> np.ndarray:
    """One-pole low-pass (optionally light resonance via a second pass)."""
    dt = 1.0 / SAMPLE_RATE
    rc = 1.0 / (2 * np.pi * cutoff)
    alpha = dt / (rc + dt)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(x.shape[0]):
        prev = prev + alpha * (x[i] - prev)
        y[i] = prev
    if resonance > 0.0:
        y = y + resonance * (y - lowpass(y, cutoff * 0.5))
    return y


def delay(x: np.ndarray, time_s: float, feedback: float = 0.35,
          mix: float = 0.3) -> np.ndarray:
    """Simple feedback delay (echo/space)."""
    d = max(1, int(time_s * SAMPLE_RATE))
    out = x.copy()
    buf = np.zeros(x.shape[0] + d)
    buf[:x.shape[0]] = x
    for i in range(x.shape[0]):
        echo = buf[i] * feedback
        if i + d < buf.shape[0]:
            buf[i + d] += echo
        out[i] = x[i] + mix * buf[i + d if i + d < buf.shape[0] else i]
    peak = np.max(np.abs(out)) or 1.0
    return out / peak if peak > 1.0 else out


def kick(dur: float = 0.18) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = _t(n)
    freq = 120.0 * np.exp(-t * 30.0) + 45.0   # pitch sweep down
    env = np.exp(-t * 18.0)
    return np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE) * env


def snare(dur: float = 0.16) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    t = _t(n)
    noise = np.random.uniform(-1, 1, n)
    body = np.sin(2 * np.pi * 180.0 * t) * 0.4
    env = np.exp(-t * 22.0)
    return lowpass(noise, 6000.0) * 0.8 * env + body * env


def hat(dur: float = 0.05) -> np.ndarray:
    n = int(dur * SAMPLE_RATE)
    env = np.exp(-_t(n) * 80.0)
    noise = np.random.uniform(-1, 1, n)
    return (noise - lowpass(noise, 7000.0)) * env   # crude high-pass


def mix(*layers: np.ndarray) -> np.ndarray:
    """Sum equal/variable-length layers (zero-padded to the longest)."""
    length = max(l.shape[0] for l in layers)
    out = np.zeros(length)
    for l in layers:
        out[:l.shape[0]] += l
    return out


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


def soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)
