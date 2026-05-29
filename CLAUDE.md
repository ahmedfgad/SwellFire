# CLAUDE.md — working notes for Gate Runner

Gate Runner is a Kivy auto-runner squad-shooter (mobile + desktop). The player
drags to steer a squad that grows via gates and auto-fires at enemies; each
world ends in a boss. Built to mirror the CoinTex project's tooling/structure.

## ⭐ Visual richness is a first-class requirement

**This game is played by children, who strongly favor lively visuals. Keep the
game visually interesting and animated at all times.** When you add or change
*anything* the player can see or trigger, give it visual (and where sensible,
audio) feedback. Treat a silent, instant, un-animated state change as a bug.

Apply this to: booster activations and their active state, gate pickups, kills,
level start/complete, screen and modal transitions, pause, shop purchases,
unlocks, hits/attrition, and any new feature. Prefer **reusing the existing
effect primitives** rather than reinventing:

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
- Linux audio: run with `SDL_AUDIODRIVER=dummy` (known SDL2 init issue).

## Verify

`SDL_AUDIODRIVER=dummy venv/bin/python main.py` (needs a display). Headless logic
tests run via `venv/bin/python - <<'PY' … PY` from the repo root (cwd import).
