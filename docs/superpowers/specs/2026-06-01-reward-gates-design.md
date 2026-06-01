# Reward Gates — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the Swellfire gameplay backlog (③). Covers #14 (reward gates
auto-activate instead of banking, with the icon counter blocking re-activation
while active) and #15 (the reward "×N" factor on its own line).

## Goal

Make reward gates feel immediate and readable: passing a reward gate
**activates its booster right away** (scaled by a ×N strength) rather than
silently banking a charge the player has to remember to use, and the gate label
shows the booster **name with its "×N" factor on a separate line** instead of
cramming "GRENADE x1" onto one line.

## Background (current behavior)

- Reward/bonus gates (ops: grenade, reinforce, freeze, overdrive, magnet) today
  **bank a charge**: `_on_apply_gate` does `self.<b>_count += gate.value`
  (`game.py` ~2293-2336). The player later activates manually via the booster
  HUD buttons.
- Booster types: **instant** — grenade (`_detonate_grenade`), reinforce
  (`_activate_reinforce`, +8 squad); **timed** — freeze (3s), overdrive (5s),
  magnet (6s), each setting a `*_active_until` timer. Shield is shop-only (never
  a gate op) and is out of scope.
- The HUD already shows a **countdown** on a booster icon while its timed effect
  is active and **disables** the button then (`_sync_booster_btn`,
  `game.py` ~2716-2741). That is exactly #14's "counter that prevents
  re-activation while active" — it just needs gate-activated effects to drive the
  same `*_active_until` timers (they will).
- Shop-bought charges bank into `state.*_balance` and are spent by the buttons —
  this stays unchanged.

## A. Auto-activation (#14)

1. **Split each booster into effect + handler.** For each gate-acquirable
   booster, factor the work into:
   - `_apply_<b>_effect(scale=1)` — performs the effect with NO balance
     check/decrement. Instant boosters do their effect scaled by `scale`; timed
     boosters set `*_active_until = max(*_active_until, self._run_time +
     base_duration * scale)` (**refresh-not-rob**: re-triggering never shortens
     an active effect).
   - `_activate_<b>()` (the existing button handler) — keeps its current
     contract: if the shop charge count ≤ 0 → play the can't-afford/error cue;
     if the effect is already active → return without spending (the HUD counter
     blocks it); otherwise decrement the shop charge and call
     `_apply_<b>_effect(1)`.
2. **Gate pass auto-activates.** In `_on_apply_gate`, replace each
   `self.<b>_count += gate.value` with `self._apply_<b>_effect(int(gate.value))`
   (gate.value carries the ×N — see section B). The gate spends no charge and
   does not touch `state.*_balance`.
3. **Effect scaling by N:**
   - **reinforce** ×N → `squad_count += boosters.REINFORCE_AMOUNT * N`.
   - **grenade** ×N → stronger blast: damage and radius scale with N (first pass:
     damage ×N, radius ×(1 + 0.5·(N−1)); tunable). Boss damage scales ×N.
   - **freeze / overdrive / magnet** ×N → `active_until = max(current, now +
     base_duration · N)`.
4. **Instant boosters** keep their existing juice (particles / float-text / sfx)
   on auto-activation; they have no "active" state and thus no countdown. **Timed
   boosters** drive the existing HUD countdown + button-disable (no new HUD work
   beyond pointing the gate at the same timers).
5. The booster HUD buttons remain (they serve shop charges); a gate-only booster
   with 0 shop charges shows "0"/disabled but still shows the countdown when a
   gate activates its timed effect.

## B. ×N reward strength + two-line label (#15)

1. **Spawner picks ×N.** For reward/bonus gates, `GateSpawner` assigns a strength
   `value = N ∈ {1, 2, 3}`, weighted so ×1 is common and ×3 rare, with higher N
   more likely in later worlds (reuse the existing `world_tier`). Canonical
   `label_text` stays ASCII (e.g. `"GRENADE x2"`) for multiplayer sync and logic.
2. **Two-line label.** The `Gate` widget renders bonus gates as **name on the top
   line and "×N" on its own line below** (the factor tinted amber like the math
   accent, smaller than the name). Always shown, including ×1 (per approval).
   This reuses the two-label layout pattern the math gates already use
   (operator-on-top / value-below) so it stays consistent and never crams onto
   one line. The widget derives the display from the op (`CONSUMABLE_BONUS[op]`)
   + `value`; `label_text` remains the canonical synced string.
3. The emphasis scale-pop (from the UI-fixes pass) applies to the whole gate, so
   the two-line label scales without reflow.

## C. Scope & multiplayer

- Targets **single-player** reward gates. The local player auto-activates in both
  single-player and multiplayer (booster activations are already local-only). The
  multiplayer **opponent-mirror** path (`_apply_gate_effect_to_opponent`) is left
  as-is — it approximates opponent gate effects on the host and is not the focus
  here; reinforce's squad change still flows through the existing squad mirror.
- **Shield** is unaffected (shop-only, never a gate).
- No `state.py` change: reward gates stop touching `*_balance`; the shop still
  banks charges there.

## Affected files

- `game.py` — `_on_apply_gate`: auto-activate scaled effect instead of banking;
  split each `_activate_<b>` into `_apply_<b>_effect(scale)` + the button
  handler; refresh-not-rob timer logic in the timed effects.
- `gates.py` — `GateSpawner`: assign `value = N` (1–3, world-weighted) to reward
  gates and build the canonical `"NAME xN"` `label_text`; `Gate` widget: render
  the two-line name/×N bonus label.
- `boosters.py` — reuse existing duration/amount constants; add a small scale
  helper only if it reads cleaner.

## Testing / verification

- **Headless unit tests** (SDL dummy / pure where possible):
  - Spawner ×N: reward gates produce `value` in {1,2,3} and a canonical
    `label_text` of the form `"NAME xN"`; later worlds skew higher (statistical
    check over many spawns, or deterministic with a seed).
  - Gate label: a bonus `Gate` built with value N exposes a two-line display
    (name + "×N"); `label_text` stays canonical ASCII.
  - Effect scaling (pure-ish, with a lightweight GameScreen stand-in or by
    testing a extracted helper): `_apply_reinforce_effect(N)` adds 8·N;
    timed `_apply_<b>_effect(N)` sets `active_until` to `now + base·N` and a
    second call with a smaller N does not shorten it (refresh-not-rob).
- Existing suites (gate emphasis, world scale, formation, weapon, aim, balance)
  still pass — no regressions.
- Boot smoke: `SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py` — no
  traceback.
- **Visual / feel checks (need a display, flagged for the user):** passing a
  reward gate immediately triggers the effect (blast / +squad / freeze etc.); the
  timed icon shows the countdown and can't be re-triggered manually while active;
  re-passing a timed gate refreshes (doesn't shorten); the gate shows NAME with
  ×N on a second line and scales without wrapping; shop-bought charges still work
  via the buttons.

## Open questions

None — approved as-is (auto-activate only, no banking; ×N 1–3; refresh-not-rob;
×N always shown including ×1; single-player focus).
