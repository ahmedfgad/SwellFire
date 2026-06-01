# Army-Formation Combat — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the Swellfire gameplay backlog (new item, raised after the
balance pass shipped).

## Goal

Replace the current free-roaming, hero-chasing enemy behavior on normal levels
with a professional **army-formation** model inspired by lane-runner crowd
games: monsters march **straight down the lane in a grid of ranks**, the player
engages them inside a **kill-zone** whose reach depends on the equipped weapon
(shown by a visible range line), and difficulty is **hard and continuous,
ramping up** rather than easy-until-the-end. This fixes two current problems:
(1) most of a level is too easy and only the end is hard; (2) monsters appear
abruptly mid-screen and die the instant the player fires near them.

## Scope

Applies to **non-boss levels only**. Boss levels keep their current minion
behavior and unlimited firing range (the boss sits above any kill-zone cap and
must remain hittable). In scope: formation spawning, straight-down movement,
per-weapon kill-zone + range line, difficulty pacing. This **supersedes the
#16 varied-Y spawn + appearance poof** from the balance pass — enemies now enter
cleanly from the top in formation (revert the varied-Y/poof spawn for normal
levels; the `spawn_poof` hook may be removed or left unused).

## A. Formation & movement

1. **Columns.** The road is divided into a fixed number of evenly spaced
   columns (`FORMATION_COLUMNS`, ≈5–7, density-aware). Enemy X positions snap to
   column centers so the crowd reads as aligned.
2. **Ranks on a distance cadence.** A new **rank** (one row across some/all
   columns) spawns every `RANK_INTERVAL_PX` of world scroll (distance-based, like
   gates — not time-based), so ranks stay evenly spaced into a marching grid
   regardless of frame rate. Replaces the time-based `enemy_spawn_interval` +
   `ramp` pacing for normal levels.
3. **Straight-down movement, no chase.** Enemies move only downward at the
   level's `enemy_speed`; the lateral **chase is removed** (chase strength 0, and
   the per-frame chase steering in `EnemyController.update` is skipped for
   formation enemies). They never approach the player's X.
4. **Mixed strength per the HP spec.** Each rank draws archetypes from the
   current world's mix (`_allowed_enemy_types`); HP uses the existing curve +
   weapon-tier power-scaling (`hp_scale`) from the balance pass. **Tougher/higher-
   HP types are weighted toward deeper ranks** so the player chews through weaker
   front ranks first. Tougher enemies render bigger (HP-based size factor,
   already implemented).

## B. Kill-zone & per-weapon range line

1. **Per-weapon range fraction.** Add `range_frac` to each `Weapon`
   (fraction of the play-field height the weapon can reach above the squad),
   capped below the top so the back of the army is always visible-but-untouchable:
   - sniper ≈ **0.50**, rifle ≈ **0.33**, pistol ≈ **0.33**, shotgun ≈ **0.25**
     (first-pass, tunable; preserves the #18 reach ordering).
2. **Range in px.** `GameScreen` computes `weapon_range_px = range_frac ×
   play_field_height` (the squad-to-top span), recomputed on layout and whenever
   the equipped weapon changes (weapon gate **or** shop equip).
3. **Visible range line.** A horizontal line is drawn across the lane at
   `squad_y + weapon_range_px`. It **moves when the weapon changes**, with a short
   tween and an sfx cue (reuse an existing weapon-swap sound or add one) so the
   change is legible. Styled to read as the "engagement line."
4. **Enforcement.**
   - Auto-aim targeting only considers enemies with `front ≤ weapon_range_px`
     (extend the existing `max_front` pattern already used on boss levels).
   - The manual-aim reticle's lead distance is clamped to within
     `weapon_range_px`.
   - **Projectiles despawn at the range line** (when they pass `squad_y +
     weapon_range_px`), so shots visibly stop at the line and can't kill the far
     army. Implemented in the projectile update via a per-shot max-Y or a
     controller-level kill-line Y set each frame.

## C. Difficulty pacing (hard, continuous, increasing)

1. **Present from the start.** After a brief intro (~1.5s so the first ranks
   form on screen), the formation is continuous — no sparse early phase.
2. **Ramps within the level.** Rank density and per-rank toughness increase with
   `distance / distance_goal` (e.g. `RANK_INTERVAL_PX` shrinks and the
   tough-archetype weight rises toward the end).
3. **Ramps across worlds.** Driven by the existing per-world archetype mix and
   the enemy-HP curve. Net effect: every part of every level has real pressure,
   scaling up over the run.

## D. Fail / win condition

- **Attrition unchanged:** ranks the player fails to kill inside the zone reach
  the squad at the bottom and cause attrition (the lose pressure). The player
  must clear each rank before it passes the squad.
- **Win is still distance-based** (`distance ≥ distance_goal`) — unchanged. The
  army is continuous content, not a kill quota.

## E. Performance

- Concurrent enemies are bounded by `FORMATION_COLUMNS × (visible_lane_height /
  RANK_INTERVAL_PX)` plus a margin; tuned to stay well under the 200-enemy pool
  cap (target ~60–130 typical, denser late). Ranks despawn at the bottom as
  today. If a dense late level strains the frame rate, `RANK_INTERVAL_PX` and
  `FORMATION_COLUMNS` are the knobs (and the FPS overlay — toggleable from the
  UI-fixes pass — is the measurement tool).

## Affected files

- `entities.py` — `EnemyController.update`: skip lateral chase for formation
  enemies (chase 0). Rework `EnemySpawner` into a **rank/formation spawner**
  (distance-cadence ranks across columns) or add a `FormationSpawner`. Projectile
  despawn-at-range-line in `ProjectileController.update`.
- `weapons.py` — add `range_frac: float` to the `Weapon` dataclass and set it per
  weapon.
- `levels.py` — per-world/level formation params (`FORMATION_COLUMNS`,
  `RANK_INTERVAL_PX` endpoints, deeper-rank toughness weighting); retire the
  normal-level time-based spawn ramp.
- `game.py` — compute `weapon_range_px` (on layout + weapon change), draw/update
  the range-line widget, gate auto-aim + manual reticle + projectile range on it
  (non-boss only), drive rank spawning from distance, and ensure boss levels
  bypass the cap (unlimited range, existing behavior).

## Testing / verification

- **Headless unit tests** (SDL dummy / pure where possible):
  - Formation spawner: spawning a rank places enemies at the expected column X
    positions and at the top edge; ranks spawn on the distance cadence (advancing
    distance by `RANK_INTERVAL_PX` yields exactly one new rank).
  - Chase removal: a formation enemy's per-frame X does not change when the hero
    is off to the side (lateral velocity 0).
  - Weapon range: `range_frac` present and ordered (sniper > rifle ≈ pistol >
    shotgun); `weapon_range_px` = `range_frac × field_height`.
  - Range enforcement: an enemy with `front > weapon_range_px` is not targeted by
    auto-aim; a projectile past the kill line is released.
  - Boss-level bypass: on a boss level, range gating is disabled (boss remains
    targetable).
- `SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py` and the existing
  balance/aim/gate suites still pass (no regressions).
- Boot smoke: `SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py` — no
  traceback.
- **Visual / feel checks (need a display, flagged for the user):** the army
  fills the lane in marching ranks; nothing dies above the range line; the range
  line is visible and moves when a weapon gate/shop swap changes the weapon;
  difficulty feels continuous and rising; frame rate holds in dense late levels;
  boss levels still play correctly (boss hittable).

## Open questions

None — approved as-is (grid ranks ≈5–7 columns, per-weapon capped range with a
visible moving line, continuous-but-ramping difficulty, distance win, non-boss
only, supersedes the #16 varied-Y spawn).
