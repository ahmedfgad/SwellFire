"""Rebuild a Swellfire soundtrack WAV from a capture audio-event timeline.

Lays the correct looping music bed (menu / world N / boss) under the SFX
one-shots at their timestamps, reading the game's OWN wav files from
assets/music and assets/sfx. High-rate cues (shoot) are rate-limited so the
mix stays musical. numpy + stdlib wave only.
"""

import json
import os
import wave

import numpy as np

import audio as game_audio  # SFX_FILES, world_music_name, MENU/BOSS_MUSIC

SR = 44100
MUSIC_DUCK = 0.55   # bed level under SFX
SFX_GAIN = 0.9


def _read_wav_mono(path):
    if not path or not os.path.exists(path):
        return np.zeros(0, dtype=np.float32)
    with wave.open(path) as w:
        n, ch, sw, fr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        a = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if fr != SR and a.size:
        idx = np.linspace(0, a.size - 1, int(a.size * SR / fr)).astype(np.int64)
        a = a[idx]
    return a


def _music_file(name):
    if name == "menu":
        return game_audio.MENU_MUSIC
    if name == "boss":
        return game_audio.BOSS_MUSIC
    if name.startswith("world:"):
        return game_audio.world_music_name(int(name.split(":")[1]))
    return None


def rate_limit_events(events, min_gap):
    """Drop events of a given name that arrive within min_gap[name] seconds of
    the previous kept one. Events without an entry in min_gap pass through."""
    last = {}
    out = []
    for t, kind, name in events:
        gap = min_gap.get(name)
        if gap is not None and name in last and (t - last[name]) < gap:
            continue
        last[name] = t
        out.append([t, kind, name])
    return out


def build_mix(events_json, duration_sec, out_path, music_dir, sfx_dir):
    with open(events_json) as f:
        data = json.load(f)
    events = [list(e) for e in data["events"]]
    total = int(duration_sec * SR)
    track = np.zeros(total, dtype=np.float32)

    # --- music bed: tile each segment's loop until the next music event ---
    music_evs = [(t, _music_file(n)) for t, k, n in events if k == "music"]
    if not music_evs:
        music_evs = [(0.0, game_audio.MENU_MUSIC)]
    if music_evs[0][0] > 0:
        music_evs.insert(0, (0.0, music_evs[0][1]))
    for i, (t, fname) in enumerate(music_evs):
        start = int(t * SR)
        end = total if i + 1 >= len(music_evs) else int(music_evs[i + 1][0] * SR)
        loop = _read_wav_mono(os.path.join(music_dir, fname)) if fname else np.zeros(0, np.float32)
        if loop.size == 0:
            continue
        seg = np.zeros(max(0, end - start), dtype=np.float32)
        if seg.size:
            reps = int(np.ceil(seg.size / loop.size))
            tiled = np.tile(loop, reps)[:seg.size]
            seg += tiled * MUSIC_DUCK
            track[start:start + seg.size] += seg

    # --- sfx one-shots, rate-limited ---
    sfx_evs = [[t, k, n] for t, k, n in events if k == "sfx"]
    sfx_evs = rate_limit_events(sfx_evs, min_gap={"shoot": 0.12, "hit": 0.08,
                                                  "enemy_death": 0.08, "damage": 0.08})
    cache = {}
    for t, _k, name in sfx_evs:
        fname = game_audio.SFX_FILES.get(name)
        if not fname:
            continue
        if name not in cache:
            cache[name] = _read_wav_mono(os.path.join(sfx_dir, fname))
        clip = cache[name]
        if clip.size == 0:
            continue
        start = int(t * SR)
        end = min(total, start + clip.size)
        if end > start:
            track[start:end] += clip[:end - start] * SFX_GAIN

    # --- normalize + write 16-bit mono ---
    peak = float(np.max(np.abs(track))) if track.size else 0.0
    if peak > 1.0:
        track /= peak
    pcm = (np.clip(track, -1.0, 1.0) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with wave.open(out_path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path
