# Balance — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the Swellfire gameplay backlog (sub-project ②).
Covers backlog items #18 (weapon balance), #11 (World-2 too easy / tougher
monsters), #12 (all worlds too easy with upgraded weapons), #16 (spawn from the
top half).

## Goal

Make the game meaningfully harder — especially for a player who returns from
World 1 with coins and an upgraded weapon — and give each weapon a distinct
reason to exist, without hurting frame rate. All numbers below are a tuned
first pass and are expected to be adjusted during playtesting; the **design
philosophy** (niches, raised HP curve, mild power-scaling, HP-based size,
top-half spawns) is what is fixed.

## Root cause (why it's too easy today)

The difficulty ramp `t` is global across all 60 levels (`levels.py:160`), and
`enemy_hp` stays at **1 until t≥0.40** (~W3-L4). So W2-L1 (t=0.17) and W3-L1
(t=0.34) spawn only 1-HP enemies, which an upgraded weapon (tier 2-4 =
1.5–3× damage) one-shots. Nothing in the difficulty curve responds to the
player's weapon tier. The rifle dominates because it lands every shot on the
nearest enemy at long range (range ≈ `speed × ttl` = 980 px) with a high fire
rate, while the shotgun's nominal DPS only materializes against clusters and the
sniper's per-shot damage is low.

## #18 — Weapon niches (range is the primary lever)

Each weapon gets a clear role; the rifle's dominance is removed mainly by
cutting its range. Values are in `weapons.py: WEAPONS` (`range ≈ speed × ttl`).

| Weapon | Current | Proposed | Role |
|---|---|---|---|
| Pistol | fire 2.5, dmg 1, 1 proj, spd 820, ttl 1.2 (range ~984) | fire 2.5, dmg 1, 1 proj, spd 820, **ttl 1.0** (range ~820) | Free starter; balanced medium-range poke |
| Rifle | fire 7.0, dmg 1, 1 proj, spd 980, ttl 1.0 (range ~980) | fire 7.0, dmg 1, 1 proj, spd 980, **ttl 0.70** (range ~686) | Rapid sustained DPS at **medium range only** (the nerf) |
| Shotgun | fire 1.4, **5** pellets, spd 720, ttl 0.8 (range ~576) | **fire 1.7, 6 pellets**, spread 15°, spd 720, ttl 0.8 (range ~576) | **Crowd clearer**, short range; shreds clusters/swarms |
| Sniper | fire 1.0, **dmg 3**, spd 1400, ttl 1.5 (range ~2100) | fire 1.0, **dmg 5**, spd 1400, ttl 1.5 (range ~2100) | **Single-target / tough-enemy / long range**; kills tanks, reaches the top |

Rationale: on a portrait screen the squad-to-top distance (~700–840 px) exceeds
the rifle's new ~686 range, so top/far enemies require the sniper and dense
close waves favor the shotgun. The rifle is still the best sustained
single-target DPS, but only once enemies are within medium range. **No
projectile pierce in v1** (would require collision changes; out of scope).

Tier scaling (`weapons.py: TIER_DAMAGE_MULT`) is unchanged.

## #11 / #12 — Difficulty

Four coordinated changes in `levels.py` (build_levels) and the enemy spawner:

1. **Raised enemy-HP curve** (`levels.py` ~167-172). Replace the
   `1 (t<0.40) / 2 (t<0.78) / 3 else` tiers with:
   - `1` if `t < 0.10`
   - `2` if `t < 0.40`
   - `3` if `t < 0.75`
   - `4` otherwise

   So W1 stays gentle early then ramps; **W2-L1 and W3-L1 now spawn 2-HP
   enemies**, making a 1-damage rifle take **2 shots** to kill (the #18 ask,
   achieved via HP rather than a sub-1 damage value).

2. **Mild weapon-tier power-scaling.** A new `EnemySpawner.hp_scale` (default
   1.0) multiplies each spawned enemy's HP. `GameScreen` sets it **at level
   start** (in `_apply_level_config`) from the equipped weapon's tier:
   `hp_scale = 1 + 0.25 · (tier − 1)` (tier 4 → ×1.75). Because weapon *damage*
   scales faster (×1.5/2/3) than this HP bump, an upgraded player still nets an
   advantage; the snapshot is taken at entry only (weapon gates mid-level do not
   re-scale), keeping it simple and predictable.

3. **More enemies, early/mid only.** `enemy_spawn_interval` lerp endpoints
   `0.18 → 0.05` become `0.15 → 0.05` (denser early; late unchanged to protect
   frame rate). The intro-delay and pool cap are unchanged.

4. **Tanks one world earlier.** In `_allowed_enemy_types`, introduce the tank
   archetype at **W3** instead of W4, so a high-HP target for the sniper niche
   exists by mid-game. (Other archetype timings unchanged.)

## #11 — Tougher enemies look bigger (HP-based size)

In `EnemySpawner._spawn_one` (`entities.py` ~287-288), after computing `hp`,
multiply the sprite `size` by `min(1.6, 1 + 0.12 · (hp − 1))` so a tougher
enemy is visibly larger. The factor is capped so even a tank (high archetype
`hp_mult` × `enemy_hp`) stays imposing rather than absurd. `size` is already
`ws()`-scaled, so density independence is preserved (apply the factor to the
already-scaled size).

## #16 — Spawn from the top half + appearance poof

1. **Varied spawn Y.** In `_spawn_one`, the spawn Y becomes
   `uniform(mid_screen_y, y_max + above_top)` instead of always
   `y_max + above_top`, where `mid_screen_y = y_min + 0.5 · (y_max − y_min)`.
   Enemies can now appear anywhere in the **top half**, some closer to the
   squad with less reaction time. (X spread is already full-width — unchanged.)

2. **Appearance poof (juice).** Enemies that spawn **on-screen** (spawn Y below
   `y_max`) emit a small particle burst at their spawn point so they *appear*
   rather than harshly pop in. The spawner gets an optional
   `spawn_poof: Callable[[x, y], None] | None = None` hook; `GameScreen` sets it
   to a wrapper around `ParticleController.burst(...)`. Enemies entering from
   above the top edge (off-screen) get no poof (they slide in as before). This
   avoids per-sprite alpha in the batched mesh.

## Performance

Higher HP and larger size are nearly free; only the early-spawn-interval bump
adds entities, and it is mild (late-game rate unchanged). The existing enemy
pool capacity and the sub-linear `MAX_SHOOTERS_PER_SHOT` fire cap bound the
cost. If the early bump shows in a profile, the spawn-interval endpoint is the
single knob to back off.

## Affected files

- `weapons.py` — new stat values for rifle/shotgun/sniper/pistol (`WEAPONS`).
- `levels.py` — raised `enemy_hp` curve; `enemy_spawn_interval` endpoints;
  tanks at W3 in `_allowed_enemy_types`.
- `entities.py` — `EnemySpawner.hp_scale` (applied in `_spawn_one`); HP-based
  size factor; `spawn_poof` hook + varied spawn Y.
- `game.py` — set `spawner.hp_scale` from equipped weapon tier in
  `_apply_level_config`; wire `spawner.spawn_poof` to the particle controller.

## Testing / verification

- **Headless unit tests** (no display, SDL dummy):
  - Weapon range ordering: assert `range(sniper) > range(pistol) > range(rifle)
    > 0` and shotgun stays short; assert sniper dmg = 5, shotgun pellets = 6.
  - Enemy-HP curve: assert the new HP tiers at representative `t` (e.g. a
    W2-L1-like index yields base `enemy_hp == 2`).
  - `hp_scale`: a spawner with `enemy_hp=2, hp_scale=1.75` spawns a grunt with
    `hp == max(1, round(2 · 1.0 · 1.75)) == 4`.
  - Size factor: a 4-HP enemy spawns larger than a 1-HP enemy of the same
    archetype.
  - Spawn-poof: with a recording `spawn_poof` callback and a forced on-screen
    spawn Y, the callback fires; with an off-screen (above-top) spawn it does
    not.
- `SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py` — density
  regression still passes.
- Boot smoke: `SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py` — no
  traceback.
- **Visual / feel checks (need a display, flagged for the user):** W2-L1 and
  W3-L1 feel non-trivial with an upgraded rifle; tougher enemies look bigger;
  enemies appear across the top half with a poof; each weapon feels distinct
  (rifle medium-range, shotgun crowds, sniper tough/far).

## Open questions

None — approved as-is (mild power-scaling at +0.25/tier, tanks moved to W3, no
sniper pierce, HP-based size cap 1.6).
