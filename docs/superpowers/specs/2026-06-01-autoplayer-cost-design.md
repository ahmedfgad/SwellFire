# Autoplayer Cost — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the Swellfire gameplay backlog (⑤ economy, #17).

## Goal

Make the in-game autoplayer cost coins so it's a deliberate, paid convenience
rather than a free default — without ever charging the player by surprise.

## Cost calibration

A level yields only ~20–30 coins (kills + completion bonus), and the autoplayer
earns ~25 while it plays. So the cost is **30 coins per level**: roughly one
level's worth, making autoplay net ≈ 0 to −10 per use — usable occasionally,
but not a coin farm and not bankrupting. (`AUTOPLAYER_COST = 30`, a tunable
constant.) The user vetoed the original 100 — far too high for this economy.

## Behavior

1. **No carry-over.** Autoplay does **not** persist across levels. Every level
   **starts with autoplay OFF** and the GA daemon stopped, so the player is
   never charged without an explicit action. (This removes the current
   `_reset` carry-over restart of the autoplayer.)
2. **Charge only on an explicit in-level toggle.** The 30-coin charge happens in
   `_toggle_auto` when the player turns autoplay **on** during a level:
   - **Affordable:** deduct 30 from the persistent bank (`state.spend_coins`),
     enable autoplay + start the daemon (existing path), and show the deduction
     feedback.
   - **Can't afford:** do **not** enable; keep the button Off, play the `error`
     cue, and show a red "NEED 30 COINS" float. No partial state.
3. **Once per level.** A per-level flag `_auto_paid_for_level` (reset to `False`
   at level start) makes re-enabling within the **same** level free after the
   first paid activation. Turning autoplay off gives **no refund**. Each new
   level that the player enables autoplay in charges again.
4. **Persistent bank.** The charge spends `state.coins_balance` (prior-level
   savings); the current level's in-progress `_coins_earned` only banks at level
   end, so it isn't available to spend mid-level — correct and intended.

## UX / feedback

- **Button label** advertises the cost when off so it's discoverable:
  `Auto (30c)` when off → `Auto: On` when active (`_refresh_auto_button`).
- **On a successful charge:** a red `−30 c` float near the hero (reuse
  `_float_text`) + a spend sfx (reuse `purchase`).
- **On can't-afford:** `error` sfx + red `NEED 30 COINS` float; button stays Off.
- **AutoPlayer settings screen** (`ui.AutoPlayerScreen`): add a one-line notice,
  e.g. "Using auto-play costs 30 coins per level."

## Scope

- **Single-player only.** Multiplayer never touches the save (existing rule), so
  no charge applies in versus; autoplay there keeps its current behavior. Guard
  the charge on `current_mode == "single"`.
- **CoinTex (the other project) is out of scope here.** #17 asks to "apply a
  similar thing" to CoinTex, but that is a *separate repository* not present in
  this project. It will be handled as its own task when pointed at that codebase;
  a sensible CoinTex cost must be re-derived from *its* (smaller) economy, not
  copied from the 30 here.

## Affected files

- `game.py` — `AUTOPLAYER_COST` constant; `_auto_paid_for_level` state (init +
  per-level reset); a `_charge_autoplayer() -> bool` helper (spends once per
  level, shows feedback); hook it in `_toggle_auto` (block enable on failure);
  in `_reset`, force `auto_mode = False` + stop the daemon + button Off (remove
  the carry-over restart); update `_refresh_auto_button` to show the cost.
- `ui.py` — cost notice line on `AutoPlayerScreen`.
- No `state.py` change — `spend_coins`/`can_afford`/`coins_balance` already exist.

## Testing / verification

- **Headless unit test** (SDL dummy): `state.spend_coins(AUTOPLAYER_COST)`
  deducts and returns `True` when affordable, returns `False` and leaves the
  balance unchanged when not (locks the spend semantics the feature relies on).
  (The exact value 30 is asserted against `game.AUTOPLAYER_COST`.)
- **Structural check** (import `game`): `AUTOPLAYER_COST == 30`; `_toggle_auto`
  source references `_charge_autoplayer`/`spend_coins`; `_reset` source sets
  `auto_mode = False` (no carry-over restart). Confirms the wiring without a live
  GameScreen.
- Existing suites still pass; boot smoke clean.
- **Manual checks (need a display, flagged for the user):**
  - Each new level starts with autoplay **Off** even if it was on the prior level.
  - Toggling autoplay on with ≥30 coins deducts 30 (red `−30 c` float, sfx) and
    starts it; off→on again in the same level is free.
  - With <30 coins, toggling does nothing but the `error` cue + "NEED 30 COINS";
    button stays Off.
  - The button reads `Auto (30c)` when off; the settings screen shows the notice.

## Open questions

None — approved as-is (30/level; no carry-over, each level starts off; charge
only on explicit toggle, once per level; can't-afford keeps it off; button shows
the cost; single-player only; CoinTex separate).
