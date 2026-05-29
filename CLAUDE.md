# CLAUDE.md — working notes for Gate Runner

Gate Runner is a Kivy auto-runner squad-shooter (mobile + desktop). The player
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

- Add a logical name → filename entry in `audio.py: SFX_FILES`, then play it
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
- `audio.play_sfx(name)` — sfx cue (bank in `audio.py: SFX_FILES`).

When you finish a change, sanity-check that nothing meaningful happens silently
or instantly. If you must bound coverage, say what you left un-juiced — don't
imply full coverage you didn't do.

## Architecture quick map

- `main.py` — App + ScreenManager (FadeTransition); registers all screens incl. `"shop"`, `"game"`. Navigate via `app().go("<screen>")`.
- `game.py` — `GameScreen`: the run loop (`_update`), HUD, boosters, boss, pause, multiplayer host/client.
- `gates.py` — `Gate` (two-line glyph labels), `GateSpawner` (math-vs-math pairing, bonus pairs), `GateController`.
- `boosters.py` — booster registry; effects live in `GameScreen` (keys G/S/R/F/O/M).
- `levels.py` — config-driven levels (`get_level`, `build_mp_level`); everything (gates/enemies/boss) reads from the level `cfg`.
- `state.py` — JSON save: coins, booster balances (`*_balance`), weapon tiers, flags.
- `shop.py` — `CATALOG` of `ShopItem`s (weapons/boosters/squad); `ui.ShopScreen` renders, `state` purchases.
- `graphics.py` — `SpriteAtlas` (atlas UVs — see note), `BatchedRenderer` (pooled mesh draws), sprite widgets, `Background`, `ShieldAura`.
- `entities.py` — pools/controllers (enemies, projectiles, particles, pickups, squad).

## Gotchas

- **Atlas UVs**: `SpriteAtlas._build_frames` maps frames with **no vertical flip** (this Kivy/provider loads PIL-row-0 at GL v=0). Don't "restore" a `1 - y/H` flip or `get_region`-derived coords — they sample the empty half and render transparent against the 256×256 atlases.
- **Gate labels**: `label_text` stays canonical ASCII (synced to MP client, used by logic); the `Gate` widget prettifies for display. Math gates pair only with math gates; bonus gates (grenade/reinforce/freeze/overdrive/magnet/weapon) form rare bonus pairs.
- **Boss HP** is time-scaled in `_spawn_boss` (`BOSS_TARGET_SECONDS`), not a flat number.
- **Progress bar / boss health**: one always-visible top progress bar (`dist_bar_holder`, on `root_layout`) shows level progress on every level — `distance/goal` normally, boss-kill progress (`1 − hp/max_hp`) on boss levels (`_level_progress`). The `show_stats` toggle hides only the band/title/chips, never the bar. There is **no** boss HP bar; the boss's health shows on its body — a solid grey "stone" twin (`BossWidget._stone_rect`) petrifies the monster **top→bottom** like a slider: only the top band is drawn, its height = fraction of HP lost (`band_h = h·(1−hp/max_hp)`), so a crisp grey front slides down as the boss dies. A thin glowing line (`_front_rect`/`_front_color`) rides that boundary while the wipe is in progress (hidden at full HP and at death). The band crop is done in `_sync` by both moving `_stone_rect.pos/size` **and** cropping `_stone_rect.tex_coords` to the same top fraction; the crop interpolates the v-coords of `_stone_base_tc` (the texture's own full coords) in *vertex* space, so it stays aligned regardless of the texture's flip convention — don't hard-code a v=0/v=1 assumption. The stone twins are baked by `tools/gen_boss_stone.py` (`enemy_w{N}_stone.png`, neutral light grey); rerun it if the boss PNGs change. **Gotcha**: the stone overlay (and the front line) must live in `BossWidget.canvas.after`, not the main canvas — an overlay rect with vertices identical to the body rect gets its second draw rejected in-game (depth test on the stage); it renders in isolation but vanishes in the real game. `canvas.after` (a separate pass) fixes it, same as `TextureSprite.flash`.
- Linux audio: run with `SDL_AUDIODRIVER=dummy` (known SDL2 init issue).

## Verify

`SDL_AUDIODRIVER=dummy venv/bin/python main.py` (needs a display). Headless logic
tests run via `venv/bin/python - <<'PY' … PY` from the repo root (cwd import).
