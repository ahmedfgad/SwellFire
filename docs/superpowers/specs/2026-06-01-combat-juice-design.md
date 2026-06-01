# Combat Juice — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the Swellfire gameplay backlog (④). Covers #1 (gate
squad-change popups, distinct color from coins), #2 (score-from-kill popups,
distinct color), #7 (monster smash death SFX + hit SFX, rate-limited).

## Goal

Add satisfying combat feedback — floating popups for gate squad changes and for
score earned per kill, plus impact/death sound effects — without audio spam or
per-frame Label churn in the dense army formations.

## Constraint (the central design issue)

With the army-formation model, kills and hits happen many times per second, and
`_float_text` creates a fresh `Label` per call (`game.py` ~2704) while
`play_sfx` has no throttle (`audio.py` ~179). So per-kill popups/sounds would
spam visually, audibly, and on the GC. The design uses **aggregation** (score)
and a **rate-limited audio channel** (combat SFX); gate popups are naturally
infrequent (one gate at a time) so they stay per-event.

## #1 — Gate squad-change popups (every gate)

In `_on_apply_gate` (`game.py` ~2293), after the squad/weapon mutation, show one
`_float_text` (gates fire one at a time, so no spam):
- **Math gates** (mul/add/sub/div): pop the operator+value — `×2`, `+5`, `−3`,
  `÷2` — colored by outcome: a **gain** uses squad light-blue
  `(0.55, 0.80, 1.0, 1.0)`, a **loss** (sub, div, or a mul/add that somehow
  reduces) uses red `(1.0, 0.42, 0.40, 1.0)`. Determine gain/loss by comparing
  `squad_count` before vs after the mutation.
- **Weapon gates**: pop the weapon name (e.g. `RIFLE!`) in weapon-amber
  `(1.0, 0.80, 0.30, 1.0)`.
- **Reward gates** (grenade/reinforce/freeze/overdrive/magnet): already pop their
  own booster float-text via the effect functions — unchanged.

All colors are distinct from the coin gold `(1.0, 0.90, 0.30)`. (Squad-blue vs
gold are close enough to matter — squad-blue leans clearly blue; acceptable per
approval. The user can retune.)

## #2 — Score-from-kill popups (aggregated, distinct color)

1. **Per-kill score table** (new constant, e.g. `SCORE_PER_KILL` in `game.py`
   near `COIN_PARTIAL_REWARD`): grunt 10, swarmer 8, splitter 20, bomber 25,
   tank 50 (first pass, tunable). A running `self.score_total` accumulates it
   (also usable to enrich the end-of-level score later; not required here).
2. **Aggregation:** `_on_kill` adds the kill's score to a pending accumulator
   `self._pending_score` (local player only, `killer == 0`). A throttle in
   `_update` flushes it every `SCORE_POPUP_INTERVAL` (~0.35s): if
   `_pending_score > 0`, show one `_float_text("+{}".format(pending), color)` in
   **white/silver** `(0.95, 0.96, 1.0, 1.0)` above the squad
   (`hero.center_x`, `hero.center_y + offset`), then reset the accumulator and
   re-arm the timer. One Label per window — no spam.
3. The score color (white) is distinct from coin gold and the gate blue/red.

## #7 — Combat SFX (rate-limited; new cues)

1. **New cues** synthesized in `tools/gen_sfx.py` and registered in
   `audio.py: SFX_FILES`:
   - `smash` — enemy death crunch: low square tone (~120 Hz) + filtered noise,
     short release (model on `explosion.wav`).
   - `enemy_hit` — non-lethal impact thud: brief mid tone/sweep (~200→120 Hz),
     quick release (model on `weapon_swap`'s low thunk). Use a **new** name
     `enemy_hit` (the existing `hit` name in `SFX_FILES` is left untouched to
     avoid repurposing a cue that may be used elsewhere).
2. **Hit signal:** add an optional `on_hit=None` callback parameter to
   `entities.resolve_projectile_collisions`, fired once per projectile-enemy
   contact that does **not** kill. `GameScreen` passes a callback that just sets
   `self._had_hit_this_frame = True` (cheap; no per-hit work). `_on_kill`
   similarly sets `self._had_kill_this_frame = True`.
3. **Rate-limited channel:** in `_update`, after collision resolution, run a
   single combat-audio throttle: if `self._run_time - self._last_combat_sfx >=
   COMBAT_SFX_INTERVAL` (~0.07s ≈ 14/sec) and a flag is set, play **`smash`** if
   `_had_kill_this_frame` else **`hit`** if `_had_hit_this_frame` (death takes
   priority), update `_last_combat_sfx`. Reset both flags each frame. This caps
   combat sounds regardless of how many enemies die/are hit that frame, honoring
   CLAUDE.md's "no one-shot per bullet/kill" rule.

## No new pooling

Gate popups are per-gate (rare) and the score popup is one-per-window, so the
existing unpooled `_float_text` is sufficient — no Label pool needed.

## Affected files

- `game.py` — gate-delta popups in `_on_apply_gate`; `SCORE_PER_KILL` +
  `score_total`/`_pending_score` accumulation in `_on_kill`; score-flush +
  combat-SFX throttle in `_update`; `_had_hit_this_frame`/`_had_kill_this_frame`
  flags + the `on_hit` callback wiring; reset flags/accumulators on level start.
- `entities.py` — optional `on_hit` callback in `resolve_projectile_collisions`
  (non-lethal contacts).
- `tools/gen_sfx.py` — `smash` and `smash` + `enemy_hit` builders.
- `audio.py` — register the new cue name(s) in `SFX_FILES`.

## Testing / verification

- **Headless unit tests** (SDL dummy / pure where possible):
  - `resolve_projectile_collisions` fires `on_hit` for a non-lethal contact and
    `on_kill` (not `on_hit`) for a lethal one — using fake pools (mirrors the
    existing collision-test approach).
  - Score aggregation helper: a small pure throttle/accumulator (extract the
    "flush every interval" + sum logic into a testable helper, or test the
    `SCORE_PER_KILL` sum) returns the summed score and resets.
  - Combat-SFX limiter: a pure helper `should_play(now, last, interval)` (or the
    chosen-cue selector preferring kill over hit) returns the right cue and
    respects the min interval.
  - New sfx names resolve: after running `tools/gen_sfx.py`, the wavs exist and
    the names are in `audio.SFX_FILES`.
- `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/ -q` if the sfx
  tooling has tests; otherwise run `tools/gen_sfx.py` and assert the files.
- Existing suites still pass; boot smoke clean.
- **Visual / audio checks (need a display + sound, flagged for the user):** every
  gate shows a delta popup (blue gain / red loss / weapon name); score `+N`
  popups appear above the squad in white and don't spam; smash plays on deaths
  and hit on non-lethal contacts, both capped (no machine-gun audio) in dense
  formations.

## Open questions

None — approved as-is (aggregated white score popups; blue-gain/red-loss gate
deltas; single death-priority rate-limited combat-SFX channel; generate smash +
hit cues).
