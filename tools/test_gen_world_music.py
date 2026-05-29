"""Headless tests for tools/gen_world_music.py — plain asserts, no pytest.

Run: venv/bin/python tools/test_gen_world_music.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import numpy as np
import gen_world_music as g


def test_note_freq():
    # A4 = MIDI 69 = 440 Hz; one octave up doubles.
    assert abs(g.note_freq(69) - 440.0) < 1e-6
    assert abs(g.note_freq(81) - 880.0) < 1e-6


def test_oscillators_shape_and_range():
    n = SR = g.SAMPLE_RATE // 10
    for osc in (g.osc_sine, g.osc_tri, g.osc_saw, g.osc_soft_square):
        buf = osc(220.0, n)
        assert buf.shape == (n,)
        assert np.max(np.abs(buf)) <= 1.0 + 1e-6, osc.__name__


def test_adsr_starts_and_ends_quiet():
    env = g.adsr(g.SAMPLE_RATE)  # 1 second
    assert env.shape == (g.SAMPLE_RATE,)
    assert env[0] < 0.05
    assert env[-1] < 0.05
    assert env.max() > 0.9


def test_lowpass_reduces_highs():
    n = g.SAMPLE_RATE
    hi = g.osc_sine(8000.0, n)
    lo = g.osc_sine(200.0, n)
    fhi = g.lowpass(hi, 800.0)
    flo = g.lowpass(lo, 800.0)
    # high tone is attenuated much more than the low tone
    assert np.max(np.abs(fhi)) < 0.5 * np.max(np.abs(flo))


def test_normalize_and_soft_clip_bounds():
    loud = g.osc_sine(440.0, 1000) * 5.0
    out = g.soft_clip(loud)
    assert np.max(np.abs(out)) <= 1.0
    norm = g.normalize(g.osc_sine(440.0, 1000) * 0.1, peak=0.9)
    assert abs(np.max(np.abs(norm)) - 0.9) < 1e-3


def test_drums_are_finite_and_bounded():
    for d in (g.kick(), g.snare(), g.hat()):
        assert d.ndim == 1 and d.shape[0] > 0
        assert np.all(np.isfinite(d))
        assert np.max(np.abs(d)) <= 1.0 + 1e-6


if __name__ == "__main__":
    test_note_freq()
    test_oscillators_shape_and_range()
    test_adsr_starts_and_ends_quiet()
    test_lowpass_reduces_highs()
    test_normalize_and_soft_clip_bounds()
    test_drums_are_finite_and_bounded()
    print("PASS: synth core")
