"""Generate Swellfire background music by rendering MIDI through a GM soundfont.

Every note is a *recorded* General-MIDI instrument sample played by FluidSynth,
so there is no synthesis noise. Eight action-forward loops, each matching its
world (see levels.py): menu, Meadow, Desert, Industrial, Snowfield, Volcano,
Cosmos, and the boss theme. The musical material is original to Swellfire and
shares nothing with the sibling CoinTex soundtrack.

Pipeline per track:
  1. compose the part list (pad / lead / bass / drums / ...) on a beat grid,
  2. write a tiny Standard MIDI File (pure stdlib — no python deps),
  3. render to 44.1 kHz WAV with `fluidsynth <soundfont> <midi>`,
  4. downmix to mono, fold the reverb tail onto the head for a seamless loop,
     normalize, and write a 16-bit mono WAV into assets/music/.

Dev/build-time only. Requires the `fluidsynth` binary and a GM soundfont
(default: /usr/share/sounds/sf2/default-GM.sf2). numpy is used only here, not
at runtime (audio.py just loads the shipped WAVs).

Usage:
    python tools/gen_world_music_sf2.py [--out assets/music] [--only boss,world5]
                                        [--soundfont /path/to.sf2]
"""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import tempfile
import wave

import numpy as np

SAMPLE_RATE = 44100
LOOP_SECONDS = 20.0
TICKS_PER_BEAT = 480
REVERB_TAIL_S = 2.2
DEFAULT_OUT = os.path.join("assets", "music")
DEFAULT_SF2 = "/usr/share/sounds/sf2/default-GM.sf2"

# General MIDI program numbers (0-indexed).
PIANO, CLAVINET, CELESTA, GLOCKEN, MUSIC_BOX, VIBES = 0, 7, 8, 9, 10, 11
TUBULAR = 14
NYLON_GTR, STEEL_GTR, OVERDRIVE_GTR, DIST_GTR = 24, 25, 29, 30
AC_BASS, FINGER_BASS, SYNTH_BASS1, SYNTH_BASS2 = 32, 33, 38, 39
STRINGS, SYNTH_STRINGS, CHOIR_AAHS = 48, 50, 52
TRUMPET, FRENCH_HORN, BRASS, SYNTH_BRASS = 56, 60, 61, 62
SQUARE_LEAD, SAW_LEAD = 80, 81
WARM_PAD, POLY_PAD, CHOIR_PAD = 89, 90, 91
SITAR = 104
TAIKO = 116

DRUM_CH = 9                  # GM percussion channel (MIDI channel 10)
KICK, SNARE, CLAP, HAT, OPEN_HAT, CRASH = 36, 38, 39, 42, 46, 49
LOW_TOM, HI_TOM, RIDE = 45, 50, 51


def bars_for(bpm, beats_per_bar=4):
    bar_sec = 60.0 / bpm * beats_per_bar
    return max(1, round(LOOP_SECONDS / bar_sec))


def total_beats(bpm):
    return bars_for(bpm) * 4


# --------------------------------------------------------------------------
# Composition helpers — note lists are (start_beat, dur_beats, midi)
# --------------------------------------------------------------------------

def tile_chords(block, total, block_len=16):
    out = []
    for blk in range(0, int(total), block_len):
        for off, dur, midis in block:
            if blk + off < total:
                for m in midis:
                    out.append((blk + off, dur, m))
    return out


def tile_mel(motif, total, block_len=16, octave_alt=False):
    out = []
    for i, blk in enumerate(range(0, int(total), block_len)):
        lift = 12 if (octave_alt and i % 2) else 0
        for off, dur, m in motif:
            if blk + off < total:
                out.append((blk + off, dur, m + lift))
    return out


def tile_riff(riff, total, bar=4):
    """Tile a one-bar (or N-beat) phrase across the loop."""
    return [(b0 + b, d, m) for b0 in range(0, int(total), bar)
            for (b, d, m) in riff if b0 + b < total]


def tile_arp(seq, total, bar=4, step=0.5):
    return [(b0 + i * step, step, m) for b0 in range(0, int(total), bar)
            for i, m in enumerate(seq) if b0 + i * step < total]


def pulse_bass(roots, total, step=0.5):
    """Cycle one root per 4-beat bar, repeated as steady `step`-beat notes."""
    out = []
    for i, bar in enumerate(range(0, int(total), 4)):
        r = roots[i % len(roots)]
        k = 0
        while k * step < 4 and bar + k * step < total:
            out.append((bar + k * step, step * 0.95, r))
            k += 1
    return out


def offbeat_bass(roots, total):
    out = []
    for i, bar in enumerate(range(0, int(total), 4)):
        r = roots[i % len(roots)]
        for off in (0.5, 1.5, 2.5, 3.5):
            if bar + off < total:
                out.append((bar + off, 0.4, r))
    return out


def bounce_bass(roots, total):
    """Root / fifth bounce per bar — bouncy pop/folk feel."""
    out = []
    for i, bar in enumerate(range(0, int(total), 4)):
        r = roots[i % len(roots)]
        for off, p in ((0, r), (1, r + 7), (2, r), (3, r + 7)):
            if bar + off < total:
                out.append((bar + off, 0.5, p))
    return out


def chord_stabs(block, total, hits, dur=0.4, block_len=16):
    out = []
    for blk in range(0, int(total), block_len):
        for off, _d, midis in block:
            for h in hits:
                t = blk + off + h
                if t < total:
                    for m in midis:
                        out.append((t, dur, m))
    return out


def chug(block, total, step=0.5, block_len=16):
    """Repeated power-chord eighth hits across each chord's span."""
    out = []
    for blk in range(0, int(total), block_len):
        for off, d, midis in block:
            k = 0
            while k * step < d and blk + off + k * step < total:
                for m in midis:
                    out.append((blk + off + k * step, step * 0.9, m))
                k += 1
    return out


# --------------------------------------------------------------------------
# Track builders — return (bpm, parts); a part is {ch, prog, vel, notes}.
# --------------------------------------------------------------------------

def build_menu():
    """Title screen — anthemic synth-pop runner hook, E major, four-on-floor."""
    bpm = 124.0
    T = total_beats(bpm)
    prog = [(0, 4, [64, 68, 71]), (4, 4, [59, 63, 66]),
            (8, 4, [61, 64, 68]), (12, 4, [57, 61, 64])]
    pad = tile_chords(prog, T)
    motif = [(0, 1, 76), (1, 1, 80), (2, 1, 83), (3, 1, 80), (4, 1, 78),
             (5, 1, 76), (6, 2, 73), (8, 1, 76), (9, 1, 78), (10, 2, 80),
             (12, 1, 73), (13, 1, 76), (14, 2, 78)]
    lead = tile_mel(motif, T)
    stabs = chord_stabs(prog, T, hits=(1, 3), dur=0.45)
    bass = pulse_bass([40, 47, 49, 45], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, SNARE))
        pat.append((b + 0.5, 0.1, HAT))
    pat.append((0, 0.1, CRASH))
    return bpm, [
        {"ch": 0, "prog": STRINGS,     "vel": 40, "notes": pad},
        {"ch": 1, "prog": SAW_LEAD,    "vel": 90, "notes": lead},
        {"ch": 2, "prog": SYNTH_BRASS, "vel": 78, "notes": stabs},
        {"ch": 3, "prog": SYNTH_BASS1, "vel": 92, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 100, "notes": pat},
    ]


def build_world1():
    """Meadow — sunny folk-pop gallop, G major, steel guitar + glockenspiel."""
    bpm = 132.0
    T = total_beats(bpm)
    prog = [(0, 4, [55, 59, 62]), (4, 4, [50, 54, 57]),
            (8, 4, [52, 55, 59]), (12, 4, [48, 52, 55])]
    pad = tile_chords(prog, T)
    motif = [(0, 0.5, 67), (0.5, 0.5, 71), (1, 1, 74), (2, 0.5, 71),
             (2.5, 0.5, 74), (3, 1, 79), (4, 0.5, 76), (4.5, 0.5, 74),
             (5, 1, 71), (6, 2, 67), (8, 0.5, 74), (8.5, 0.5, 71), (9, 1, 67),
             (10, 0.5, 69), (10.5, 0.5, 71), (11, 1, 74), (12, 1, 79),
             (13, 1, 76), (14, 2, 74)]
    lead = tile_mel(motif, T)
    sparkle = tile_arp([79, 83, 86, 83, 79, 74, 71, 74], T)
    bass = bounce_bass([43, 38, 40, 36], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK if b % 2 == 0 else SNARE))
        pat.append((b, 0.1, HAT))
        pat.append((b + 0.5, 0.1, HAT))
    return bpm, [
        {"ch": 0, "prog": STRINGS,     "vel": 38, "notes": pad},
        {"ch": 1, "prog": STEEL_GTR,   "vel": 92, "notes": lead},
        {"ch": 2, "prog": GLOCKEN,     "vel": 60, "notes": sparkle},
        {"ch": 3, "prog": FINGER_BASS, "vel": 82, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 86, "notes": pat},
    ]


def build_world2():
    """Desert — chase groove, A Phrygian-dominant (Hijaz), sitar + taiko."""
    bpm = 122.0
    T = total_beats(bpm)
    prog = [(0, 4, [45, 52, 57]), (4, 4, [45, 52, 57]),
            (8, 4, [46, 53, 58]), (12, 4, [45, 52, 57])]
    pad = tile_chords(prog, T)
    motif = [(0, 0.5, 69), (0.5, 0.5, 70), (1, 0.5, 73), (1.5, 0.5, 74),
             (2, 1, 76), (3, 1, 74), (4, 0.5, 73), (4.5, 0.5, 70), (5, 1, 69),
             (6, 2, 64), (8, 0.5, 69), (8.5, 0.5, 73), (9, 0.5, 74),
             (9.5, 0.5, 76), (10, 1, 77), (11, 1, 76), (12, 0.5, 74),
             (12.5, 0.5, 73), (13, 1, 70), (14, 2, 69)]
    lead = tile_mel(motif, T)
    taiko = tile_riff([(0, 0.5, 45), (1.5, 0.5, 45), (2, 0.5, 45),
                       (3, 0.5, 45)], T)
    bass = pulse_bass([33, 33, 34, 33], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        pat.append((b + 0.5, 0.1, HAT))
        pat.append((b + 0.75, 0.1, HAT))
        if b % 4 == 2:
            pat.append((b, 0.1, CLAP))
    return bpm, [
        {"ch": 0, "prog": SYNTH_STRINGS, "vel": 36, "notes": pad},
        {"ch": 1, "prog": SITAR,         "vel": 90, "notes": lead},
        {"ch": 2, "prog": TAIKO,         "vel": 95, "notes": taiko},
        {"ch": 3, "prog": FINGER_BASS,   "vel": 80, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 80, "notes": pat},
    ]


def build_world3():
    """Industrial — mechanical electro-funk, C minor, clavinet + distortion."""
    bpm = 126.0
    T = total_beats(bpm)
    prog = [(0, 4, [48, 51, 55]), (4, 4, [44, 48, 51]),
            (8, 4, [51, 55, 58]), (12, 4, [46, 50, 53])]
    pad = tile_chords(prog, T)
    riff = [(0, 0.25, 60), (0.5, 0.25, 63), (0.75, 0.25, 60), (1, 0.25, 67),
            (1.5, 0.25, 65), (2, 0.25, 63), (2.25, 0.25, 60), (3, 0.25, 58),
            (3.5, 0.25, 60)]
    lead = tile_riff(riff, T)
    power = [(0, 4, [36, 43]), (4, 4, [32, 39]), (8, 4, [39, 46]),
             (12, 4, [34, 41])]
    stabs = chord_stabs(power, T, hits=(0.5, 2.5), dur=0.3)
    bnote = [(0, 0.5, 36), (0.75, 0.25, 36), (1.5, 0.5, 39), (2, 0.5, 36),
             (2.75, 0.25, 41), (3.5, 0.5, 34)]
    bass = tile_riff(bnote, T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        if b % 2 == 0:
            pat.append((b + 0.5, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, SNARE))
        for q in (0.25, 0.5, 0.75):
            pat.append((b + q, 0.1, HAT))
    return bpm, [
        {"ch": 0, "prog": SYNTH_STRINGS, "vel": 34, "notes": pad},
        {"ch": 1, "prog": CLAVINET,      "vel": 86, "notes": lead},
        {"ch": 2, "prog": DIST_GTR,      "vel": 84, "notes": stabs},
        {"ch": 3, "prog": SYNTH_BASS2,   "vel": 92, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 92, "notes": pat},
    ]


def build_world4():
    """Snowfield — crystalline ice-trance, E major, glockenspiel + choir pad."""
    bpm = 120.0
    T = total_beats(bpm)
    prog = [(0, 4, [64, 68, 71]), (4, 4, [61, 64, 68]),
            (8, 4, [57, 61, 64]), (12, 4, [59, 63, 66])]
    pad = tile_chords(prog, T)
    arp = tile_arp([76, 80, 83, 88, 83, 80, 71, 76], T)
    air = tile_mel([(0, 4, 83), (4, 4, 80), (8, 4, 76), (12, 4, 78)], T)
    bass = offbeat_bass([40, 49, 45, 47], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, CLAP))
        pat.append((b + 0.5, 0.1, OPEN_HAT))
    return bpm, [
        {"ch": 0, "prog": CHOIR_PAD,   "vel": 42, "notes": pad},
        {"ch": 1, "prog": GLOCKEN,     "vel": 76, "notes": arp},
        {"ch": 2, "prog": SAW_LEAD,    "vel": 58, "notes": air},
        {"ch": 3, "prog": SYNTH_BASS1, "vel": 78, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 82, "notes": pat},
    ]


def build_world5():
    """Volcano — molten metal march, F# minor, distortion power chords + brass."""
    bpm = 140.0
    T = total_beats(bpm)
    power = [(0, 4, [42, 49, 54]), (4, 4, [38, 45, 50]),
             (8, 4, [45, 52, 57]), (12, 4, [40, 47, 52])]
    strings = tile_chords(power, T)
    rhythm = chug(power, T, step=0.5)
    mel = [(0, 1, 66), (1, 1, 69), (2, 1, 68), (3, 1, 66), (4, 2, 73),
           (6, 2, 69), (8, 1, 71), (9, 1, 73), (10, 1, 74), (11, 1, 76),
           (12, 2, 78), (14, 2, 73)]
    brass = tile_mel(mel, T)
    bass = pulse_bass([42, 38, 45, 40], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        pat.append((b + 0.5, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, SNARE))
        pat.append((b + 0.25, 0.1, HAT))
        pat.append((b + 0.75, 0.1, HAT))
        if b % 8 == 0:
            pat.append((b, 0.1, CRASH))
    return bpm, [
        {"ch": 0, "prog": STRINGS,     "vel": 46, "notes": strings},
        {"ch": 1, "prog": DIST_GTR,    "vel": 84, "notes": rhythm},
        {"ch": 2, "prog": BRASS,       "vel": 102, "notes": brass},
        {"ch": 3, "prog": FINGER_BASS, "vel": 90, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 104, "notes": pat},
    ]


def build_world6():
    """Cosmos — driving space synthwave, A minor, pulsing saw arp + synth bass."""
    bpm = 128.0
    T = total_beats(bpm)
    prog = [(0, 4, [57, 60, 64]), (4, 4, [53, 57, 60]),
            (8, 4, [48, 52, 55]), (12, 4, [55, 59, 62])]
    pad = tile_chords(prog, T)
    arp = tile_arp([69, 72, 76, 81, 76, 72, 69, 64], T)
    motif = [(0, 2, 76), (2, 2, 72), (4, 2, 69), (6, 2, 71), (8, 2, 72),
             (10, 2, 76), (12, 3, 67), (15, 1, 69)]
    lead = tile_mel(motif, T)
    bass = pulse_bass([33, 29, 36, 31], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, CLAP))
        pat.append((b + 0.5, 0.1, HAT))
    return bpm, [
        {"ch": 0, "prog": WARM_PAD,    "vel": 42, "notes": pad},
        {"ch": 1, "prog": SAW_LEAD,    "vel": 80, "notes": arp},
        {"ch": 2, "prog": SQUARE_LEAD, "vel": 66, "notes": lead},
        {"ch": 3, "prog": SYNTH_BASS1, "vel": 80, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 86, "notes": pat},
    ]


def build_boss():
    """Boss — epic battle, D minor, full brass + distortion + taiko, fast drums."""
    bpm = 150.0
    T = total_beats(bpm)
    power = [(0, 4, [38, 45, 50]), (4, 4, [34, 41, 46]),
             (8, 4, [41, 48, 53]), (12, 4, [36, 43, 48])]
    strings = tile_chords(power, T)
    rhythm = chug(power, T, step=0.5)
    mel = [(0, 0.5, 62), (0.5, 0.5, 62), (1, 1, 65), (2, 0.5, 64),
           (2.5, 0.5, 62), (3, 1, 69), (4, 0.5, 67), (4.5, 0.5, 65), (5, 1, 62),
           (6, 2, 57), (8, 0.5, 62), (8.5, 0.5, 65), (9, 1, 69), (10, 1, 70),
           (11, 1, 72), (12, 2, 74), (14, 2, 69)]
    brass = tile_mel(mel, T)
    taiko = tile_riff([(0, 0.5, 38), (1, 0.5, 38), (2, 0.5, 38), (2.5, 0.5, 38),
                       (3, 0.5, 38)], T)
    bass = pulse_bass([38, 34, 41, 36], T)
    pat = []
    for b in range(int(T)):
        pat.append((b, 0.1, KICK))
        pat.append((b + 0.5, 0.1, KICK))
        if b % 2 == 1:
            pat.append((b, 0.1, SNARE))
        for q in (0.25, 0.5, 0.75):
            pat.append((b + q, 0.1, HAT))
        if b % 4 == 0:
            pat.append((b, 0.1, CRASH))
    return bpm, [
        {"ch": 0, "prog": STRINGS,     "vel": 50, "notes": strings},
        {"ch": 1, "prog": DIST_GTR,    "vel": 84, "notes": rhythm},
        {"ch": 2, "prog": BRASS,       "vel": 104, "notes": brass},
        {"ch": 3, "prog": TAIKO,       "vel": 100, "notes": taiko},
        {"ch": 4, "prog": SYNTH_BASS2, "vel": 92, "notes": bass},
        {"ch": DRUM_CH, "prog": 0, "vel": 108, "notes": pat},
    ]


# --------------------------------------------------------------------------
# Minimal Standard MIDI File writer (format 1, pure stdlib)
# --------------------------------------------------------------------------

def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _track_chunk(events):
    """events: (abs_tick, status, d1, d2). Program-change/aftertouch are 2-byte
    messages; note on/off are 3-byte. Wrong lengths desync the parser."""
    events = sorted(events, key=lambda e: (e[0], 0 if e[1] & 0xF0 == 0x80 else 1))
    body = bytearray()
    last = 0
    for tick, status, d1, d2 in events:
        if status & 0xF0 in (0xC0, 0xD0):
            msg = bytes([status, d1])
        else:
            msg = bytes([status, d1, d2])
        body += _vlq(tick - last) + msg
        last = tick
    body += _vlq(0) + b"\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def write_midi(path, bpm, parts):
    tpb = TICKS_PER_BEAT
    inst_chunks = []
    max_tick = 0
    for p in parts:
        ch = p["ch"]
        ev = [(0, 0xC0 | ch, p["prog"], 0)]
        for start, dur, midi in p["notes"]:
            on = int(round(start * tpb))
            off = int(round((start + dur) * tpb))
            ev.append((on, 0x90 | ch, int(midi), p["vel"]))
            ev.append((off, 0x80 | ch, int(midi), 0))
            max_tick = max(max_tick, off)
        inst_chunks.append(_track_chunk(ev))

    us = int(round(60_000_000 / bpm))
    tail_ticks = max_tick + int(REVERB_TAIL_S * bpm / 60.0 * tpb)
    tempo = bytearray(_vlq(0) + b"\xFF\x51\x03" + struct.pack(">I", us)[1:])
    tempo += _vlq(tail_ticks) + b"\xFF\x2F\x00"
    tempo_trk = b"MTrk" + struct.pack(">I", len(tempo)) + bytes(tempo)

    track_chunks = [tempo_trk] + inst_chunks
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(track_chunks), tpb)
    with open(path, "wb") as f:
        f.write(header)
        for c in track_chunks:
            f.write(c)


# --------------------------------------------------------------------------
# Render + post-process
# --------------------------------------------------------------------------

def render_midi(midi_path, wav_path, soundfont):
    cmd = ["fluidsynth", "-ni", "-C", "0", "-g", "0.6", "-r", str(SAMPLE_RATE),
           "-F", wav_path, soundfont, midi_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def read_wav_mono(path):
    with wave.open(path, "rb") as w:
        ch, sw, nf = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(nf)
    assert sw == 2, "expected 16-bit PCM from fluidsynth"
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


def seamless_loop(mono, loop_samples, fade_s=0.04):
    loop_samples = min(loop_samples, mono.shape[0])
    body = mono[:loop_samples].copy()
    tail = mono[loop_samples:]
    if tail.shape[0]:
        k = min(tail.shape[0], body.shape[0])
        body[:k] += tail[:k]
    f = min(int(fade_s * SAMPLE_RATE), body.shape[0] // 4)
    if f > 0:
        head = body[:f].copy()
        out = body[f:].copy()
        fade_out = np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        fade_in = np.sin(np.linspace(0, np.pi / 2, f)) ** 2
        out[-f:] = out[-f:] * fade_out + head * fade_in
        return out
    return body


def normalize(x, peak=0.92):
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


def write_wav_mono(path, x):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

TRACKS = {
    "bg_music_menu.wav":   build_menu,
    "bg_music_world1.wav": build_world1,
    "bg_music_world2.wav": build_world2,
    "bg_music_world3.wav": build_world3,
    "bg_music_world4.wav": build_world4,
    "bg_music_world5.wav": build_world5,
    "bg_music_world6.wav": build_world6,
    "bg_music_boss.wav":   build_boss,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--soundfont", default=DEFAULT_SF2)
    ap.add_argument("--only", default="",
                    help="comma list of track keys w/o prefix, e.g. boss,world5")
    args = ap.parse_args()
    if not os.path.exists(args.soundfont):
        raise SystemExit("soundfont not found: " + args.soundfont)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    for fname, builder in TRACKS.items():
        key = fname.replace("bg_music_", "").replace(".wav", "")
        if only and key not in only:
            continue
        bpm, parts = builder()
        loop_samples = int(round(total_beats(bpm) * 60.0 / bpm * SAMPLE_RATE))
        with tempfile.TemporaryDirectory() as td:
            mid = os.path.join(td, key + ".mid")
            raw_wav = os.path.join(td, key + ".wav")
            write_midi(mid, bpm, parts)
            render_midi(mid, raw_wav, args.soundfont)
            mono = read_wav_mono(raw_wav)
        looped = normalize(seamless_loop(mono, loop_samples))
        path = os.path.join(args.out, fname)
        write_wav_mono(path, looped)
        disc = abs(float(looped[-1] - looped[0]))
        print("wrote {:<22} {:.1f}s peak={:.3f} loopΔ={:.4f} {:.1f}MB".format(
            fname, looped.shape[0] / SAMPLE_RATE, float(np.max(np.abs(looped))),
            disc, os.path.getsize(path) / 1e6))


if __name__ == "__main__":
    main()
