# CLAUDE.md — working notes for Swellfire

Swellfire is a Kivy auto-runner squad-shooter (mobile + desktop). The player
drags to steer a squad that grows via gates and auto-fires at enemies; each
world ends in a boss. Built to mirror the CoinTex project's tooling/structure.

## ⭐ Visual richness is a first-class requirement

**This game is played by children, who strongly favor lively visuals. Keep the
game visually interesting and animated at all times.** When you add or change
*anything* the player can see or trigger, give it visual feedback. Treat a
silent, instant, un-animated state change as a bug.

Apply this to: booster activations and their active state, gate pickups, kills,
level start/complete, screen and modal transitions, pause, shop purchases,
unlocks, hits/attrition, and any new feature. Prefer **reusing the existing
effect primitives** rather than reinventing:

## 🔊 Sound effects are required for user actions

**Every user action must have an appropriate sound effect when applicable** —
booster activations, gate/weapon swaps, shop buy/upgrade/equip, errors
(can't-afford / locked), pause, button taps, modal appearances, level
end. Each *distinct* action should have a *distinct, fitting* cue — don't reuse
one generic blip for unrelated actions. If an action has **no** suitable sound,
**generate one** and wire it:

- Add a logical name → filename entry in `swellfire/audio.py: SFX_FILES`, then play it
  with `app().audio.play_sfx("<name>")` at the action site.
- New cues are synthesized by **`tools/gen_sfx.py`** (stdlib only) — add a
  builder there and run `python tools/gen_sfx.py` to (re)generate the WAV under
  `assets/sfx/`. Keep them short and tasteful.
- Missing wav files are silent, not fatal — but that means a forgotten cue
  fails silently, so verify the file exists and the name is registered.
- **Restraint for continuous/high-rate events**: don't play a one-shot per
  bullet or per enemy kill (audio spam); those stay handled by particles/shake.
  Sound is for *discrete* user actions and notable events.

Prefer **reusing the existing effect primitives** rather than reinventing:

- `entities.ParticleController.burst(x, y, count, speed, ttl, size, frame, rng)` — particle pops.
- `GameScreen._add_shake(amount)` — screen shake (`_step_shake` decays it).
- `graphics.TextureSprite/AtlasSprite.flash(duration, color)` — sprite tint flash.
- `graphics.ShieldAura` — glowing aura around the hero (model for other auras).
- `kivy.animation.Animation(prop=…, duration=…, t="out_quad").start(widget)` — tween any property (opacity/pos/size/font_size/color).
- `ui._fade_in_modal(modal)` — dialogs fade in instead of popping; use on every new modal.
- `audio.play_sfx(name)` — sfx cue (bank in `swellfire/audio.py: SFX_FILES`).

When you finish a change, sanity-check that nothing meaningful happens silently
or instantly. If you must bound coverage, say what you left un-juiced — don't
imply full coverage you didn't do.

## Architecture quick map

- `main.py` — App + ScreenManager (FadeTransition); registers all screens incl. `"shop"`, `"game"`. Navigate via `app().go("<screen>")`.
- `swellfire/game.py` — `GameScreen`: the run loop (`_update`), HUD, boosters, boss, pause, multiplayer host/client.
- `swellfire/gates.py` — `Gate` (two-line glyph labels), `GateSpawner` (math-vs-math pairing, bonus pairs), `GateController`.
- `swellfire/boosters.py` — booster registry; effects live in `GameScreen` (keys G/S/R/F/O/M).
- `swellfire/levels.py` — config-driven levels (`get_level`, `build_mp_level`); everything (gates/enemies/boss) reads from the level `cfg`.
- `swellfire/state.py` — JSON save: coins, booster balances (`*_balance`), weapon tiers, flags.
- `swellfire/shop.py` — `CATALOG` of `ShopItem`s (weapons/boosters/squad); `ui.ShopScreen` renders, `state` purchases.
- `swellfire/graphics.py` — `SpriteAtlas` (atlas UVs — see note), `BatchedRenderer` (pooled mesh draws), sprite widgets, `Background`, `ShieldAura`.
- `swellfire/entities.py` — pools/controllers (enemies, projectiles, particles, pickups, squad).

## Gotchas

- **World pixel scale (density independence)**: the game *world* (sprite sizes,
  speeds, distances, gate boxes, offsets, radii) is dimensioned in raw pixels
  tuned on a **density-1.0 desktop window**. On a high-density (Retina) surface
  Kivy reports `Window.size` in physical pixels and `Metrics.density` is 2–3, so
  raw-px magnitudes render tiny while `sp()`/`dp()` *text* scales up — sprites
  look small and gate equations overflow their box (the iOS bug). The fix:
  **every runtime read of a world-px size/speed/distance/offset is wrapped in
  `graphics.ws(value)`** (= `value * Metrics.density`, cached, clamped ≥1.0,
  **no-op at density 1.0** so desktop is unchanged). Positions derived from the
  (already-scaled) stage bounds are left alone. The scroll *distance* domain
  (`self.distance`, `distance_goal`, gate/pickup interval thresholds) scales
  too, which keeps level duration + gate cadence identical across densities
  (numerator and denominator both ×density). **When you add any new world-px
  magnitude, wrap it in `graphics.ws()`** — keep the base constant as the
  readable logical value. Sites that bypass the scaled spawners (direct
  `enemy_controller.spawn` in the splitter code + `boss.py` minions) scale
  inline. Regression test: `SDL_AUDIODRIVER=dummy .venv/bin/python
  tests/test_world_scale.py`. (MP positions are sent normalized to stage fraction —
  `norm_x` — so they stay density-independent; cross-device *different*-density
  lockstep is still untested.)
- **Atlas UVs**: `SpriteAtlas._build_frames` maps frames with **no vertical flip** (this Kivy/provider loads PIL-row-0 at GL v=0). Don't "restore" a `1 - y/H` flip or `get_region`-derived coords — they sample the empty half and render transparent against the 256×256 atlases.
- **Gate labels**: `label_text` stays canonical ASCII (synced to MP client, used by logic); the `Gate` widget prettifies for display. Math gates pair only with math gates; bonus gates (grenade/reinforce/freeze/overdrive/magnet/weapon) form rare bonus pairs.
- **Boss HP** is time-scaled in `_spawn_boss` (`BOSS_TARGET_SECONDS`), not a flat number.
- **Progress bar / boss health**: one always-visible top progress bar (`dist_bar_holder`, on `root_layout`) shows level progress on every level — `distance/goal` normally, boss-kill progress (`1 − hp/max_hp`) on boss levels (`_level_progress`). The `show_stats` toggle hides only the band/title/chips, never the bar. There is **no** boss HP bar; the boss's health shows on its body — a solid grey "stone" twin (`BossWidget._stone_rect`) petrifies the monster **top→bottom** like a slider: only the top band is drawn, its height = fraction of HP lost (`band_h = h·(1−hp/max_hp)`), so a crisp grey front slides down as the boss dies. A thin glowing line (`_front_rect`/`_front_color`) rides that boundary while the wipe is in progress (hidden at full HP and at death). The band crop is done in `_sync` by both moving `_stone_rect.pos/size` **and** cropping `_stone_rect.tex_coords` to the same top fraction; the crop interpolates the v-coords of `_stone_base_tc` (the texture's own full coords) in *vertex* space, so it stays aligned regardless of the texture's flip convention — don't hard-code a v=0/v=1 assumption. The stone twins are baked by `tools/gen_boss_stone.py` (`enemy_w{N}_stone.png`, neutral light grey); rerun it if the boss PNGs change. **Gotcha**: the stone overlay (and the front line) must live in `BossWidget.canvas.after`, not the main canvas — an overlay rect with vertices identical to the body rect gets its second draw rejected in-game (depth test on the stage); it renders in isolation but vanishes in the real game. `canvas.after` (a separate pass) fixes it, same as `TextureSprite.flash`.
- Linux audio: run with `SDL_AUDIODRIVER=dummy` (known SDL2 init issue).
- **Packaged-build asset paths**: assets are referenced by **cwd-relative** strings (`"assets/sprites/…"`). Kivy resolves these via `resource_find`, whose default search path is the cwd — so a PyInstaller binary crashes (`load_from_filename(None)` → `AttributeError: 'NoneType'…encode`) the instant it's launched from any dir but the one holding `assets/`. `main.py` fixes this by registering a frozen-aware `ASSET_ROOT` (`sys._MEIPASS` when frozen, else the source dir) via `resource_add_path` at import, and deriving the audio `asset_dir` from it. Raw `open()` of atlas JSON (`graphics.py`) bypasses `resource_find`, so those go through `open(resource_find(p) or p)`. **When adding new asset access, use a relative `"assets/…"` path** (auto-resolved) — don't reintroduce `os.path.dirname(__file__)`-based paths, which point into the temp `_MEIPASS` and break audio/saves in the bundle. Always smoke-test a packaged build from a *foreign* cwd (e.g. `cd /tmp && /path/to/dist/Swellfire`), not from the repo root.

## Media generation

Marketing/store assets live in `marketing/` (build-excluded) and are
reproducible from `tools/` — dev deps in `requirements/media.txt` (PIL, numpy,
imageio-ffmpeg; never a runtime/mobile dep). Brand graphics derive from the
hand-authored art in `marketing/re/` (`gen_brand_assets`,
`make_feature_graphic`, `make_youtube_thumbnail`). Screenshots + video frames are
captured from the real game by `tools/capture.py` (fixed-dt harness that drives
the GA autoplayer inline and grabs the GL framebuffer). The game is **portrait**;
because the portrait window can exceed the dev screen height, captures run inside
a tall **Xvfb** virtual display via `tools/capture_run.py` (`capture.py` also
creates the Window at the capture size *before* importing `main`, whose
import-time `Config` would otherwise force a too-tall window). Video soundtracks
are rebuilt from the game's own wavs by `tools/mix_audio.py` and muxed via the
static ffmpeg in `tools/video_core.py`; `make_videos`/`make_promo`/`make_short`
build the three videos, `title_cards` renders logo cards/labels. See
`marketing/README.md` for regen commands.

## Verify

Run all regression tests from the repository root with `SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest -q`. Boot the app with `SDL_AUDIODRIVER=dummy .venv/bin/python main.py` (needs a display).
Media tool tests: `SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest tools/tests/ -q`.
