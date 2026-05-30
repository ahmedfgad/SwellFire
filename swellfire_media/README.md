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
| Google Play feature graphic | `feature_graphic_1024x500.png` | 1024×500 |
| YouTube cover | `youtube_thumbnail_1280x720.png` | 1280×720 |
| Long autoplay video | `swellfire_autoplay_1080p.mp4` | 1080×1920 |
| Promo video | `swellfire_promo.mp4` | 1080×1920 |
| Vertical short | `swellfire_short_vertical.mp4` | 1080×1920 |

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
- The long autoplay video shows 2 regular levels per world; bosses appear in the
  screenshots and the promo (the autoplayer's small starting squad can't survive a
  boss long enough to film as autoplay).
