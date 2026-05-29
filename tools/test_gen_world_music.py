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


if __name__ == "__main__":
    test_note_freq()
    test_oscillators_shape_and_range()
    test_adsr_starts_and_ends_quiet()
    print("PASS: synth core (note/osc/adsr)")
