# Faithful, complete, longer Swellfire videos — design

Date: 2026-05-30

## Problem

The three marketing videos in `swellfire_media/` (`swellfire_autoplay_1080p.mp4`,
`swellfire_promo.mp4`, `swellfire_short_vertical.mp4`) have two issues:

1. **They read as too fast** and don't reflect real play.
2. **They're too short**, and the autoplay video only shows ~5-second slices of a
   handful of levels instead of complete levels played from start to finish.

### Root-cause finding (speed)

The capture→encode pipeline is already **mathematically real-time**: the sim
advances `distance += SCROLL_SPEED_PX_PER_SEC (360) * dt`, `capture.py` steps the
sim at `dt = 1/fps` and grabs one frame per step, and `video_core.encode_clip`
encodes at the same `fps`. So 1 video-second = 1 game-second = 360 px of scroll,
identical to the live game (which has no `dt` clamp or fps cap that would change
wall-clock speed). The videos are also **not stale** — they were regenerated
(commit `d931f43`, 2026-05-30) *after* the last speed change (commit `0193709`,
2026-05-28).

Therefore the "fast" perception is **choppiness**, not wall-clock speed: capture
runs at 30 fps with a coarse `dt = 1/30`, and jerky motion reads as fast. The fix
is to capture and encode at **60 fps** (`dt = 1/60`) — smooth motion at the exact
same real game-time. No game-speed or slow-motion change.

## Goals

- All three videos: smooth, faithful **real-time** motion (60 fps), and **longer**.
- Autoplay video: **complete level playthroughs**, one full level per world
  (6 levels), each start → finish **including the victory/stars completion**.

## Non-goals

- No change to the game's actual speed (`SCROLL_SPEED_PX_PER_SEC` stays 360).
- No slow-motion / playback-speed factor.
- Boss levels remain excluded from the autoplay video (the GA autoplayer can't
  reliably beat a boss; bosses stay showcased in the screenshots/promo).
- No changes to real save files — capture-only state seeding.

## Design

### 1. 60 fps everywhere (smooth, real-time)

In `tools/make_videos.py`, `tools/make_promo.py`, `tools/make_short.py`:
- `FPS = 60` (was 30).
- The `fps` value is already threaded into `capture.py --fps`, `mix_audio.build_mix`
  (via `seconds = frames / FPS`), `title_cards.card_frames`, and
  `video_core.encode_clip(..., fps=FPS)`, so the bump propagates with no timing math
  changes.
- Bump the per-segment `subprocess.run(..., timeout=...)` from 900 → **1800 s**
  (≈2× frames per segment, plus full-level captures are longer).

### 2. New `--playthrough` capture mode (`tools/capture.py`)

Add a `--playthrough` flag, used with `--level`. Behaviour:

- **Seed a strong squad/weapon (capture-only)** in `after_build`, before
  `app.start_level`: equip the best weapon and set its tier to max via the existing
  `state` API (`set_setting("equipped_weapon", ...)`, `upgrade_weapon_tier(...)`),
  plus any starting-squad boost the game exposes. This runs against the in-memory
  capture `app.state`; it must not persist to the real save (verify `state` writes
  only on explicit save, or seed in-memory only).
- **Drive the autoplayer naturally** to the real `distance_goal` — do **not** use
  the `--win` distance shove.
- **Capture through the win sequence**: today level captures stop the instant
  `gs._level_ended` (to avoid the banner). In `--playthrough`, instead of stopping,
  keep stepping and grabbing frames through the `VICTORY!` banner and the
  `LevelResultDialog` (stars/score) — reusing the `--win` mode's technique of
  stepping on a small real delay so the deferred dialog (`_open_result_dialog`,
  scheduled ~1 s real-time after `_end_level`) actually opens and lays out. Once the
  dialog is open and settled, capture ~2 s of it, then `_finish()`.
- **Safety**: keep a max-frames cap (`--frames`) as a hard stop. If the level ends
  in defeat (`_end_level(won=False)`), log a clear warning so the level pick / seed
  can be retuned (a defeat clip must never ship).
- Audio-event JSON is still emitted as today.

### 3. `make_videos.py`: one full level per world

`_segments()` returns 6 segments — levels **6, 16, 26, 36, 46, 56** (mid-world,
non-boss; ~30 s each). Each is captured via the new `--playthrough` mode with a
generous safety `--frames` cap (e.g. enough for 45 s + the win sequence at 60 fps,
~3000 frames). The existing world lower-third overlay (`overlay_lower_third`) and
the world label are retained. Intro/outro title cards unchanged. Expected runtime
≈ **3.5–4 min**.

### 4. Promo & short: longer + smooth

Keep the montage structure but at 60 fps and with longer windows:
- `make_promo.py`: each window ≈ 6 s of gameplay (frames `≈ 360` at 60 fps);
  total promo ≈ 50–60 s.
- `make_short.py`: each window ≈ 7 s (frames `≈ 420`); total short ≈ 28 s.
- These stay regular (non-boss) levels driven by the autoplayer with the existing
  warmup; no playthrough/seed change required (montage windows, not full levels).

### 5. Docs

Update `swellfire_media/README.md`: new durations, "60 fps real-time", and "the
autoplay video plays one complete level per world start → finish (including the
victory screen)".

## Verification

- **Speed sanity**: confirm a 60 fps capture's `distance` advances ~360 px per
  encoded second (re-confirms real-time).
- **Autoplayer survival**: smoke-test each of levels 6/16/26/36/46/56 under
  `--playthrough` with the strong seed; each must reach a genuine win. Swap to an
  easier same-world level or raise the seed if any fails.
- **Save safety**: confirm the capture seed does not mutate the on-disk save.
- **Disk/time**: per-segment frame dirs are already deleted after encode; smoke-test
  one full segment end-to-end before the full build.
- Re-probe the final mp4 durations/fps with ffmpeg.
