# Manual Aim — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the larger Swellfire gameplay backlog (this spec covers items
#8 manual aim, #5 boss-level controls, #6 boss fire-rate perception, #9 autoplayer aiming).

## Goal

Add an opt-in **Manual aim** mode that makes the game more exciting and skill-based:
the player must aim the squad's fire while also steering through the right gates,
creating tension between "go where the good gate is" and "point my guns at the
monsters". Auto-aim remains the default for young/casual players.

This sub-project also fixes a boss-level targeting bug (#5) where the squad locks
onto the boss and ignores the adds it spawns, and investigates a reported
"faster firing" feeling on boss levels (#6).

## Scope

In scope:
- A player-chosen **Aiming: Auto / Manual** mode (setting, persisted).
- Manual-aim input model, shot geometry, reticle, and visual/audio juice.
- Boss-level auto-targeting fix (applies in both modes).
- Boss fire-rate investigation (#6).
- Autoplayer aim control when running in Manual mode (#9).

Out of scope (other sub-projects): difficulty/weapon balance (#11/#12/#16/#18),
reward-gate auto-activation (#14/#15), general juice (#1/#2/#7), economy (#17),
UI fixes (#3/#10/#13/#4).

## A. Mode & default

- New setting **Aiming: Auto / Manual**, added to `SettingsScreen` (`ui.py:1684`)
  and persisted via `state.py` (a `get_setting`/`set_setting` key, e.g. `"aim_mode"`,
  default `"auto"`).
- **Default = Auto.** Manual is opt-in. Manual applies on all levels, bosses included.
- **Auto mode:** guns auto-target as today, plus the boss-add fix in section E.
- **Manual mode:** auto-targeting is disabled; every gun fires at the
  player-controlled reticle point.

## B. Control model — "aim follows steering"

- Drag still sets the squad's target lane; steering is unchanged.
- A **reticle** sits a fixed lead-distance ahead of the squad along the aim angle.
- Aim angle = `clamp(k · (finger_x − squad_x), ±θ_max)`, with `θ_max ≈ 35°`.
  While the player leans toward a side, the aim leans with them; when they hold
  still the squad catches up to the finger, the offset → 0, and the aim eases
  back to straight-up. **Self-centering and predictable.**
- Rationale for self-centering over a "hold last aim" model: bullets are fast
  (820–1400 px/s), so a target does not need to be held in the reticle long;
  self-centering gives a stable, learnable default and avoids a "stuck aim" feel.
- All world-pixel magnitudes (lead distance, etc.) wrapped in `graphics.ws()` per
  the density-independence rule in CLAUDE.md.

## C. Shot geometry — converge on the reticle

- Every muzzle (hero + squad) fires toward the reticle point, reusing the existing
  "all guns fire at one target point" path (`game.py:1815`, `entities.py:665`
  `fire_from_positions`). Bullets continue past the reticle.
- **No fire-rate change** — the weapon's own `fire_rate` (`weapons.py`) is used,
  identical to auto mode.

## D. Visual & audio juice (per CLAUDE.md "visual richness")

- A **reticle sprite** rendered ahead of the squad, with a faint aim line from the
  squad to the reticle so the aim direction is always visible.
- The reticle **pulses** continuously, and **turns red / does a lock flash**
  (reusing `flash()`) when it is over an enemy or the boss — clear "you will hit
  this" feedback.
- **No per-shot aim SFX** (would be audio spam). Target-acquired/lock sound kept
  minimal or omitted; if added later it must be rate-limited. (User chose minimal.)
- Mode toggle in settings uses the existing button-tap SFX.

## E. Boss-level targeting fix (#5) — applies in BOTH modes

- **Problem:** on boss levels the auto-targeting locks the boss and ignores the
  adds (grunts/tanks/etc.) the boss spawns, so adds slip into the squad and cause
  attrition; this reads as "the squad fires only on the boss and ignores the
  monsters, which pass through."
- **Auto mode fix:** target the **nearest threatening add when one is close**
  (within a threat band ahead of the squad), otherwise target the boss. Tunable
  threat distance; reuses `find_nearest_enemy` (`entities.py:496`) with a boss
  fallback at `game.py:1812-1816`.
- **Manual mode:** the player chooses what to shoot, which solves this directly.

## F. Boss "faster firing" investigation (#6)

- Exploration found **no** fire-rate multiplier specific to boss levels; weapon
  `fire_rate` is the same. Likely causes of the "faster" feel: the boss-level
  head-start squad (more muzzles → more bullets) and all bullets converging on one
  point reading as a dense stream.
- **Action during implementation:** verify in code. If a real boss-only multiplier
  exists, remove it so boss levels use the regular weapon fire rate. If it is
  purely perceptual, report that and leave fire rate unchanged. No speculative
  change before confirming.

## G. Autoplayer aim control (#9)

- The in-game GA autoplayer (`autoplay.py`) today only steers (`_hero_target_x`)
  and relies on auto-aim for shooting.
- **When the game is in Manual mode and the autoplayer is on**, the autoplayer
  gains an **aim controller**: it points the reticle at the best target (nearest
  threatening monster, or the boss) while still steering toward favorable gates —
  demonstrating the same aim-while-steer tension a human faces.
- **In Auto mode the autoplayer is unchanged.**

## Affected files (anticipated)

- `state.py` — new `aim_mode` setting (default `"auto"`).
- `ui.py` — Auto/Manual toggle in `SettingsScreen`.
- `game.py` — read mode in the fire tick (`~1803-1871`); reticle state, aim-angle
  computation from steering; reticle rendering + juice; boss-add targeting fix.
- `entities.py` — minor: ensure `fire_from_positions` accepts an explicit aim
  point for the reticle; threat-band helper if needed.
- `graphics.py` — reticle sprite/aim-line primitive (or reuse a sprite widget).
- `autoplay.py` — aim controller used only in Manual mode.

## Testing / verification

- `SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py` — density regression
  (new world-px magnitudes must pass).
- Headless logic check for aim-angle clamp and reticle point math.
- Manual run: `SDL_AUDIODRIVER=dummy venv/bin/python main.py` — verify Auto
  unchanged, Manual aim feels right, reticle/juice present, boss adds get shot in
  Auto mode, autoplayer aims in Manual mode.

## Open questions

None — design approved as-is (self-centering aim, default Auto, minimal aim SFX).
