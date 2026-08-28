# Swellfire media

Marketing / store assets for Swellfire. Everything here is reproducible from the
repo. Install the dev deps once: `venv/bin/pip install -r requirements-media.txt`.

## Contents

| Asset | File | Size |
|---|---|---|
| App / launcher / window icon | `icon.png` (repo root) | 512×512 |
| Splash screen | `presplash.png` (repo root) | 1080×1920 |
| Phone screenshots ×8 | `01..08_*.png` | 720×1280 (portrait) |
| Tablet screenshots ×8 | `tablet_screenshots/01..08_*.png` | 1080×1920 |
| App Store iPhone screenshots ×8 | `app_store/iphone_6_9/` | 1284×2778 |
| App Store iPad screenshots ×8 | `app_store/ipad_13/` | 2064×2752 |
| Google Play feature graphic | `feature_graphic_1024x500.png` | 1024×500 |
| YouTube cover | `youtube_thumbnail_1280x720.png` | 1280×720 |
| Long autoplay video | `swellfire_autoplay_1080p.mp4` | 1080×1920, 60 fps, ~4:11 |
| Promo video | `swellfire_promo.mp4` | 1080×1920, 60 fps, ~54s |
| Vertical short | `swellfire_short_vertical.mp4` | 1080×1920, 60 fps, ~28s |

`re/` holds the hand-authored source art (logo, presplash, YouTube cover) the
brand graphics are derived from.

## Regenerate

Run from the repo root with the venv.

| Asset | Command |
|---|---|
| icon.png + presplash.png | `venv/bin/python tools/gen_brand_assets.py` |
| feature graphic | `venv/bin/python tools/make_feature_graphic.py` |
| YouTube cover | `venv/bin/python tools/make_youtube_thumbnail.py` |
| 8 phone screenshots | `venv/bin/python tools/make_screenshots.py` |
| 8 tablet screenshots | `venv/bin/python tools/upscale_screenshots.py` |
| App Store iPhone + iPad screenshots | `venv/bin/python tools/make_app_store_screenshots.py` |
| long autoplay video | `venv/bin/python tools/make_videos.py long` |
| promo video | `venv/bin/python tools/make_promo.py` |
| vertical short | `venv/bin/python tools/make_short.py` |

## How it works

- **Brand graphics** are the hand-authored art in `re/`, resized/cropped into the
  canonical deliverables (icon/presplash/cover/feature). `tools/brandkit.py` holds
  shared helpers.
- **Screenshots & video frames** are captured from the real game by
  `tools/capture.py` (a deterministic, fixed-dt harness that drives the GA
  autoplayer inline and grabs the GL framebuffer). The game is **portrait**, and
  on a display shorter than the portrait window the capture runs inside a tall
  **Xvfb** virtual display — `tools/capture_run.py` handles this automatically
  (install `xvfb`; falls back to the real display otherwise).
- **Video soundtracks** are rebuilt from the game's own `assets/music` + `assets/sfx`
  wavs by `tools/mix_audio.py` (per-segment world/boss music bed + SFX one-shots at
  their captured timestamps), then muxed with the frames via the pip-bundled static
  ffmpeg (`tools/video_core.py`). Title cards (`tools/title_cards.py`) use the logo.
- All videos are captured and encoded at **60 fps at true real game-time**. The
  capture harness steps the sim at a fixed `dt = 1/fps` and is the *sole* driver:
  it re-cancels the game's own `Clock`-scheduled `_update_event` every step
  (`_reset` re-arms it after the harness's first cancel), so the sim is never
  double-stepped — otherwise the interval ran with real wall-clock `dt` and the
  footage played several times too fast.
- The long autoplay video plays **one complete regular level per world for
  worlds 1–4** (levels 6/16/26/36), start → finish including the Level-Complete /
  stars screen, via `capture.py --playthrough`. That mode seeds a **capture-only**
  strong squad (max weapon tiers + squad bonus, never persisted to the real save)
  so the autoplayer reliably wins. Worlds 5–6 levels are very long at real
  game-time (~110s/~130s each) and are left to the screenshots/promo; bosses also
  stay in the screenshots (the autoplayer can't reliably beat a boss).
- The promo and vertical short are smooth real-time **montages** of short (6s)
  highlight windows across worlds, driven by the autoplayer with the default
  starting squad.
