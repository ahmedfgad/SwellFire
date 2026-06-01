# Quick Fixes (aim beam + boss-minion size) — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the post-playtest follow-up batch (sub-project **A**; the
batch also has **B** early-game difficulty and **C** progression/headroom, done
after this).

Covers follow-up #1 (manual-aim line: prettify) and #4 (boss-spawned minions are
too small vs normal enemies).

## #1 — Manual-aim line → subtle fading beam

**Current:** `graphics.AimReticle` draws the squad→reticle aim line as a single
flat cyan `Line` (`_line`, color `(0.55, 0.88, 1.0, 0.30)`, width 1.6) —
positioned each frame by `set_endpoints(sx, sy, rx, ry)`, recolored cyan↔red by
`set_locked`.

**Change:** Replace the single line with a **segmented fading beam**: ~5 short
segments laid end-to-end along the squad→reticle vector, with **alpha ramping
down** from ~0.45 at the squad end to ~0.0 at the reticle end and a slight
**width taper**, in the reticle's current hue (cyan normally, red when locked).
Reads as a polished laser-sight that dissolves toward the aim point instead of a
flat stick, while still showing aim direction at a glance.

- In `AimReticle.__init__`, create `N = 5` `(Color, Line)` segment pairs
  (replacing the single `_line`/`_line_color`); keep the ring + dot as-is.
- `set_endpoints(sx, sy, rx, ry)`: for each segment `i` (0 = squad end), set its
  two points to the `i/N … (i+1)/N` fraction along `(sx,sy)→(rx,ry)`, and set its
  `Color.a = base_alpha * (1 - i/N)` and width tapering from ~2.0 down to ~1.0.
- `set_locked(locked)`: set the base RGB on every segment's `Color` (cyan
  `(0.55, 0.88, 1.0)` normally, red `(1.0, 0.40, 0.35)` when locked), preserving
  each segment's alpha ramp. Keep the ring/dot lock behavior unchanged.
- `set_endpoints` is called every frame from `game.py` — recomputing 5 segment
  point-lists + alphas is negligible.

## #4 — Boss-minion size matches normal enemies

**Current bug:** `boss.py` `_volley` and `_stream_one` spawn minions at a
hardcoded `minion_sz = graphics.ws(44.0)`, while normal grunts spawn at
`graphics.ws(64.0)` (`entities.ARCHETYPES[TYPE_GRUNT]["size"]`) — boss minions
are ~69% size. (Reported on W2; the hardcode means it affects every world.)

**Change:** size boss minions like normal enemies — the grunt archetype size
times the same HP-based size factor the formation spawner uses:
- Extract the factor into a shared pure helper **`entities.hp_size_factor(hp)`**
  returning `min(1.6, 1.0 + 0.12 * (hp - 1))`, and use it in **both** the
  formation spawner (replacing its inline `size *= min(1.6, ...)`) and the boss
  minions (DRY + testable).
- In `boss.py` `_volley` and `_stream_one`, replace
  `minion_sz = graphics.ws(44.0)` with:
  `minion_sz = graphics.ws(float(entities.ARCHETYPES[entities.TYPE_GRUNT]["size"]))
  * entities.hp_size_factor(self.minion_hp)`.
  (Use the same `minion_hp` the spawn already passes.)
- **Keep the minions' existing `"enemy_red"` frame** (their visual distinctness
  as boss adds is intentional; only the size was wrong), and keep their speed /
  chase / type unchanged.

## Scope

Two isolated fixes; no gameplay-balance or progression changes (those are
sub-projects B and C). The `hp_size_factor` extraction is a pure refactor that
must not change the formation spawner's behavior.

## Affected files

- `graphics.py` — `AimReticle`: segmented fading beam (replace single line).
- `entities.py` — add `hp_size_factor(hp)`; use it in `FormationSpawner._spawn_rank`
  (replace the inline factor).
- `boss.py` — `_volley` + `_stream_one`: minion size = grunt size ×
  `hp_size_factor(minion_hp)`.

## Testing / verification

- **Unit (pure):** `entities.hp_size_factor(1) == 1.0`; `hp_size_factor(4) ==
  min(1.6, 1+0.12*3)` ; caps at 1.6 for large hp (e.g. `hp_size_factor(50) == 1.6`).
- **Regression:** `test_formation_spawner.py` still passes (the
  tougher-enemy-is-bigger test must still hold after the refactor — the factor is
  unchanged, just relocated).
- **Headless smoke (AimReticle):** construct it, `set_endpoints(0,0,0,300)`,
  `set_locked(True)`/`set_locked(False)`, `show()`/`hide()` run without error;
  assert the squad-end segment's `Color.a` > the reticle-end segment's `Color.a`
  (fade direction), and that there are 5 segments.
- Boot smoke clean.
- **Visual checks (need a display, flagged for the user):** the aim beam looks
  like a tapered laser-sight fading toward the reticle (and turns red on lock);
  boss minions are the same size as normal grunts (try a W2 boss and at least one
  other world's boss).

## Open questions

None — approved as-is (5-segment fading beam; boss minions sized to grunt ×
hp_size_factor, keeping the red frame).
