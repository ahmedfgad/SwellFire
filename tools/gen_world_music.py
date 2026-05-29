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
