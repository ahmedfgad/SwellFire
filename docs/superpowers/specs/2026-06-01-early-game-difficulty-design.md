# Early-Game Difficulty — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the post-playtest follow-up batch (sub-project **B**; #2).
Sub-project C (progression/headroom, #3) follows and does the full
beatable-with-available-power re-tune.

## Goal

Make World 1 (and the early ramp) beatable by a **brand-new player with no
weapon upgrades**, fixing the reported death-trap (e.g. W1-L8: start squad 1 →
first gate ×2 → squad 2 → dead before the second gate). Success criterion: a
fresh save can clear all of W1 without buying anything.

## Levers (four, coordinated)

### 1. Starting squad — the main cushion
Non-boss `starting_squad` (`levels.py`, currently `= world` → W1 = 1) becomes
**`4 + world`** → W1 = **5**, W2 = 6, … W6 = 10. Five muzzles can clear the
front rank and reach the gates. The persistent shop `squad_bonus` still adds on
top (C makes it world-gated). Boss-level starting squad is **unchanged**
(separate head-start formula tied to `BOSS_TARGET_SECONDS`).

### 2. Softer early formation density
Lower the **low end** of the density ramp so W1 isn't a wall, keeping the
high-end endpoints so late worlds stay dense (the ramp is over global `t`):
- `formation_columns`: `lerp(6, 9)` → **`lerp(5, 9)`** (W1 ≈ 5).
- `rank_interval_start`: `lerp(220, 120)` → **`lerp(260, 120)`** (W1 sparser).
- `rank_interval_end`: `lerp(120, 60)` → **`lerp(140, 60)`** (W1 late-level
  pressure gentler).

### 3. Stronger growth multiplier
`gates.py` `_pick_op` MUL value pool `[2]` → **`[2, 3]`** so the squad can grow
faster (the "higher multiplier factor" requested). Bounded by `MAX_SQUAD` and
the sub-linear `MAX_SHOOTERS_PER_SHOT` fire cap, so it doesn't break later
worlds.

### 4. First gate of every level biased to a gain
The **opening gate pair** of each level guarantees at least one **growth** gate
so the player always gets an early boost (never a SUB/DIV-only opening that can
only shrink the squad):
- `GateSpawner` tracks pairs spawned this level (a counter reset in
  `reset_per_level`). For the **first** pair, force one gate's op to a gain —
  prefer **MUL** (×2/×3) if in `allowed_ops`, else **ADD** with a solid value
  (e.g. 5 or 7); the other gate is the normal distinct pick (math partner). The
  pair stays a real choice (the gain vs the partner), but a strong growth option
  is always present at the start.
- Bonus pairs and weapon pairs are unaffected by this rule (it applies to the
  first *math* opening; if the spawner would otherwise open with a bonus pair,
  leave it — bonus pairs already help the player).

## Scope & the curve tension

Targets the **early game only**. Because difficulty ramps on global `t`,
softening W1 also slightly eases W2–W3 — but the curve still **rises** (W2 harder
than W1, W3+ climbing), which is the correct onboarding shape. The **full
re-tune so every world is beatable with the power available by then** (the W4
wall) is sub-project **C**; B just makes the opening fair. These are tuning
values, expected to be adjusted after playtest.

## Affected files

- `levels.py` — `starting_squad` formula (non-boss); the three density lerps
  (`formation_columns`, `rank_interval_start`, `rank_interval_end`).
- `gates.py` — MUL pool `[2, 3]`; `GateSpawner` first-pair gain bias (pair
  counter reset per level + force a gain on the opening math pair).

## Testing / verification

- **Headless unit tests** (SDL dummy):
  - `levels`: W1-L1 `starting_squad == 5`; W6-L1 `== 10` (non-boss);
    W1 `formation_columns == 5`; W1 `rank_interval_start ≈ 260`.
  - `gates`: MUL value pool includes 3 (a `_pick_op`/op_table check, or
    statistically over many picks a ×3 appears).
  - `GateSpawner` first-pair bias: build the first pair of a level (after
    `reset_per_level`) repeatedly with a seeded spawner and assert at least one
    gate in the opening pair is a gain op (MUL or ADD), and that subsequent pairs
    are not forced.
- Existing suites (formation, world-scale, gates) still pass.
- Boot smoke clean.
- **Manual checks (need a display, flagged for the user):** a fresh save can
  clear W1-L1 through W1-L10 (incl. the old L8 trap) without buying upgrades;
  W1 feels like a fair onboarding (not a walkover, not a wall); W2–W3 still
  noticeably ramp up.

## Open questions

None — approved as-is plus the first-gate-gain bias (starting squad 4+world,
softer W1 density, MUL ×3 available, opening pair guarantees a growth gate).
