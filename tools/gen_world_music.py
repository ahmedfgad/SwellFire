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
