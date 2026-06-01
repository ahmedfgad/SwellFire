# Progression & Power Headroom — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the post-playtest follow-up batch (sub-project **C**; #3).

## Goal

Keep the game **always passable**: at every world W, the difficulty is
hard-but-beatable with the power a player can realistically have by then —
a weapon tier and squad capped by W, affordable from the coins earned getting
there — with clear nudges to upgrade. Fixes the reported wall ("max rifle,
4K coins spent, can't pass a single World-4 level"). The guiding principle:
**world W is beatable with tier ≤ W + the squad available by W.**

## Components

### 1. Extended weapon tiers (`weapons.py`)
- `MAX_TIER` **4 → 6**.
- `TIER_DAMAGE_MULT` extended: `[None, 1.0, 1.5, 2.0, 3.0, 4.0, 5.5]` (tiers 5-6
  added; first pass, tunable).
- These give later worlds real power headroom ("a new upgrade to chase").

### 2. Per-world weapon-tier cap (world-gated) (`state.py`, `shop.py`)
- `state.max_tier_for_world(world) = min(weapons.MAX_TIER, world)` → **W1 caps at
  tier 1 (no weapon upgrades in W1, matching B's onboarding)**, W2→2, … W6→6.
- "Max world reached" = `(highest_unlocked - 1) // LEVELS_PER_WORLD + 1`
  (a new `state.max_world_reached` helper/property).
- **Enforce** in `state.upgrade_weapon_tier`: refuse a purchase whose target tier
  exceeds `max_tier_for_world(max_world_reached)`.
- **Shop display:** weapon rows whose next tier is above the cap show a locked
  "Reach World N" state (reuse the existing locked/`can_buy=False` styling)
  instead of an affordable upgrade.

### 3. Per-world squad-bonus cap (`state.py`, `shop.py`)
- `squad_bonus` (persistent, stacks on B's `4 + world` base) becomes world-gated:
  `state.max_squad_bonus_for_world(world) = min(SQUAD_BONUS_MAX, world - 1)`
  (`SQUAD_BONUS_MAX = 6`) → W1→0, W2→1, … W6→5 (tunable). Enforce in
  `purchase_squad_bonus`; the shop shows the cap / "Reach World N".

### 4. Coin income scales by world (`game.py`)
- At level end, the banked coins are multiplied by a world factor
  `coin_world_factor(world) = 1.0 + 0.4 * (world - 1)` → W1×1.0 … W6×3.0 (tunable),
  so income tracks the rising tier/squad prices and the needed upgrades stay
  affordable. (Applied once to `self._coins_earned` before `state.add_coins`, so
  in-run popups can stay raw or scale — implementation picks one and is consistent;
  recommended: scale at bank, keep popups raw, and the level-complete summary
  shows the scaled total.)

### 5. Late-world difficulty re-tune (beatable at tier ≤ W) (`levels.py`)
Soften the **high end** of the curves so a world is beatable with the tier+squad
available by then (the existing curves assumed unlimited/immediate max power).
**First-pass values — will need playtest iteration; the levers are:**
- Enemy-HP curve thresholds pushed later: `1` (t<0.10) / `2` (t<0.45) / `3`
  (t<0.85) / `4` (else) — so 4-HP enemies are W6-only, not W4-5.
- Density upper endpoints eased: `formation_columns` `lerp(5, 8)` (was 9);
  `rank_interval_end` `lerp(140, 75)` (was 60).
- Boss HP eased: `boss_hp` `lerp(1100, 2200)` (was 2800) — late bosses winnable
  with the available tier rather than requiring impossible DPS.
These are starting points; the success test is a manual playtest per world
(no headless difficulty oracle exists).

### 6. Pre-world shop-nudge modal (`ui.py`, `game.py`)
- On the **first** entry to each new world W≥2 (the unused `intro_seen_w2..w6`
  flags), show a modal once: e.g. *"World N — tougher enemies ahead. Visit the
  Shop to upgrade your weapon (now up to tier N) and grow your squad."* with
  **"Go to Shop"** and **"Continue"** buttons; mark `intro_seen_wN` true so it
  shows once per world. Faded-in per the `ui._fade_in_modal` pattern + a sfx.

## Scope & honesty

One cohesive progression system. **The difficulty re-tune (#5) and the overall
"beatable per world" outcome cannot be verified headlessly** — the numbers are a
first pass and the real validation is a per-world playtest loop (the listed
levers are the dials). Everything else (#1-#4, #6 flag logic) is unit-testable.
CoinTex (the separate-repo parallel of #17) remains out of scope here.

## Affected files

- `weapons.py` — `MAX_TIER = 6`, extended `TIER_DAMAGE_MULT`.
- `shop.py` — tier-5/6 `TIER_PRICES` per weapon; world-locked display for tiers
  above the cap and squad bonus above its cap.
- `state.py` — `max_world_reached`; `max_tier_for_world(w)`; cap enforcement in
  `upgrade_weapon_tier`; `max_squad_bonus_for_world(w)` + enforcement in
  `purchase_squad_bonus`.
- `game.py` — world coin-income scaling at level-end banking; show the pre-world
  modal on first entry to a new world.
- `levels.py` — re-tuned high-end enemy-HP curve, density endpoints, boss HP.
- `ui.py` — the world-intro/shop-nudge modal.

## Testing / verification

- **Unit (pure / SDL-dummy):**
  - `weapons.MAX_TIER == 6`; `len(TIER_DAMAGE_MULT)` covers tiers 1-6 and is
    monotonic increasing.
  - `state.max_tier_for_world`: W1→1, W4→4, W6→6, W9-equivalent clamps to 6.
  - `upgrade_weapon_tier` refuses a tier above the world cap (balance unchanged
    on refusal) and allows one at/below it (with a stubbed `max_world_reached`).
  - `max_world_reached` from `highest_unlocked` (e.g. unlocked L31 → world 4).
  - `max_squad_bonus_for_world` schedule; `purchase_squad_bonus` respects it.
  - `coin_world_factor(1)==1.0`, `coin_world_factor(6)==3.0`; banked coins scale.
  - tier-5/6 prices exist for every weapon and increase with tier.
  - levels: the re-tuned curve values at representative indices (HP thresholds,
    boss_hp endpoints, density endpoints) match the new numbers.
  - modal flag logic: entering W2 first time flips `intro_seen_w2` and would show;
    second time does not.
- Existing suites still pass; boot smoke clean.
- **Manual / playtest (needs a display — flagged):** each world W1→W6 is
  beatable with the tier+squad obtainable by then (the core success criterion);
  the shop locks tiers above the world cap; the pre-world modal appears once per
  world; coins feel sufficient to afford the needed upgrades. Iterate the #5
  numbers from here.

## Open questions

None — approved as one spec (extend to tier 6, cap = min(6, world), squad cap
min(6, world-1), coin income ×(1+0.4·(world-1)), high-end difficulty re-tune as a
playtest-tunable first pass, once-per-world shop-nudge modal).
