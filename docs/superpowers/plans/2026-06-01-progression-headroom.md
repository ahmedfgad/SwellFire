# Progression & Power Headroom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every world beatable with the power obtainable by then — extended weapon tiers gated by world, world-gated squad upgrades, world-scaled coin income, a softened late-world difficulty curve, and a pre-world shop-nudge modal.

**Architecture:** `weapons.py` extends to tier 6. `state.py` adds `max_world_reached` + per-world tier/squad caps and enforces them in the purchase methods. `shop.py`/`ui.py` price the new tiers and show world-locked rows. `game.py` scales banked coins by world and shows a once-per-world modal. `levels.py` softens the high-end difficulty (playtest-tunable).

**Tech Stack:** Python 3, Kivy 2.3. Logic (tiers, caps, economy, curve values, modal-flag) is unit-tested; shop-lock + modal rendering verified by boot + structural checks + manual play. The difficulty re-tune is a playtest-tunable first pass.

---

### Task 1: Extended weapon tiers (`weapons.py`)

**Files:**
- Modify: `weapons.py` — `MAX_TIER`, `TIER_DAMAGE_MULT` (lines 68-69)
- Test: `test_weapon_tiers.py`

- [ ] **Step 1: Write the failing test** — create `test_weapon_tiers.py`:

```python
"""test_weapon_tiers.py — extended weapon tiers 1-6.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_weapon_tiers.py"""
import weapons


def test_max_tier_is_6():
    assert weapons.MAX_TIER == 6


def test_damage_mult_covers_all_tiers_and_increases():
    m = weapons.TIER_DAMAGE_MULT
    assert m[0] is None
    vals = m[1:7]
    assert len(vals) == 6
    assert all(vals[i] < vals[i + 1] for i in range(5))   # strictly increasing


def test_tier_damage_at_top():
    rifle = weapons.get("rifle")   # damage 1
    assert weapons.tier_damage(rifle, 6) == max(1, round(1 * weapons.TIER_DAMAGE_MULT[6]))
    assert weapons.tier_damage(rifle, 99) == weapons.tier_damage(rifle, 6)   # clamps


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON TIER TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_weapon_tiers.py`
Expected: FAIL — `MAX_TIER == 6` (currently 4).

- [ ] **Step 3: Extend the tiers**

In `weapons.py`, change lines 68-69:
```python
MAX_TIER = 4
TIER_DAMAGE_MULT: list[float] = [None, 1.0, 1.5, 2.0, 3.0]
```
to:
```python
MAX_TIER = 6
TIER_DAMAGE_MULT: list[float] = [None, 1.0, 1.5, 2.0, 3.0, 4.0, 5.5]
```
(`tier_damage` already clamps to `MAX_TIER`, so it works unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_weapon_tiers.py`
Expected: PASS — `ALL WEAPON TIER TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add weapons.py test_weapon_tiers.py
git commit -m "feat: weapon tiers extend to 6 (#3 headroom)"
```

---

### Task 2: World-gated caps + enforcement (`state.py`)

**Files:**
- Modify: `state.py` — add a `_LEVELS_PER_WORLD` constant + `max_world_reached`, `max_tier_for_world`, `max_squad_bonus_for_world`; enforce in `upgrade_weapon_tier` (lines 230-245) and `purchase_squad_bonus` (lines 295-301). Ensure `import weapons` at top.
- Test: `test_progression_caps.py`

- [ ] **Step 1: Write the failing test** — create `test_progression_caps.py`:

```python
"""test_progression_caps.py — world-gated tier/squad caps.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_progression_caps.py"""
import state
import levels
import weapons


def _s(highest_unlocked, coins=100000):
    s = state.GameState("/tmp/sf_prog_{}".format(highest_unlocked))
    s.data["highest_unlocked"] = highest_unlocked
    s.data["coins_balance"] = coins
    s.data["weapon_tiers"] = {}
    s.data["squad_bonus"] = 0
    return s


def test_levels_per_world_constant_matches():
    assert state._LEVELS_PER_WORLD == levels.LEVELS_PER_WORLD


def test_max_world_reached():
    assert _s(1).max_world_reached == 1
    assert _s(11).max_world_reached == 2     # W2-L1 unlocked
    assert _s(31).max_world_reached == 4
    assert _s(60).max_world_reached == 6


def test_max_tier_for_world():
    s = _s(1)
    assert s.max_tier_for_world(1) == 1
    assert s.max_tier_for_world(4) == 4
    assert s.max_tier_for_world(6) == 6
    assert s.max_tier_for_world(9) == weapons.MAX_TIER   # clamps to 6


def test_upgrade_blocked_above_world_cap():
    s = _s(1)                       # world 1 -> cap tier 1
    assert s.upgrade_weapon_tier("rifle", 2, 1) is False    # tier 2 > cap 1
    assert s.coins_balance == 100000                        # not charged


def test_upgrade_allowed_at_or_below_cap():
    s = _s(11)                      # world 2 -> cap tier 2
    assert s.upgrade_weapon_tier("rifle", 2, 400) is True
    assert s.get_weapon_tier("rifle") == 2
    assert s.upgrade_weapon_tier("rifle", 3, 1000) is False  # tier 3 > cap 2


def test_max_squad_bonus_for_world():
    s = _s(1)
    assert s.max_squad_bonus_for_world(1) == 0
    assert s.max_squad_bonus_for_world(2) == 1
    assert s.max_squad_bonus_for_world(6) == 5


def test_squad_bonus_blocked_above_cap():
    s = _s(1)                       # world 1 -> squad cap 0
    assert s.purchase_squad_bonus(1, 50) is False
    s2 = _s(31)                     # world 4 -> cap 3
    assert s2.purchase_squad_bonus(3, 50) is True
    assert s2.purchase_squad_bonus(4, 50) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROGRESSION CAP TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_progression_caps.py`
Expected: FAIL — `AttributeError ... 'max_world_reached'` (or `_LEVELS_PER_WORLD`).

- [ ] **Step 3: Add the constant + helpers + enforcement**

In `state.py`, ensure `import weapons` is present at the top (add it next to the other imports if missing). Add a module constant near the top:
```python
# Keep in sync with levels.LEVELS_PER_WORLD (kept local to avoid an import cycle).
_LEVELS_PER_WORLD = 10
SQUAD_BONUS_MAX = 6
```
Add these to the `GameState` class (e.g. near `get_weapon_tier`):
```python
    @property
    def max_world_reached(self) -> int:
        """Highest world the player has reached, from highest_unlocked."""
        return (max(1, self.highest_unlocked) - 1) // _LEVELS_PER_WORLD + 1

    def max_tier_for_world(self, world: int) -> int:
        """Weapon-tier cap at `world`: min(MAX_TIER, world) — W1=1 ... W6=6."""
        return min(weapons.MAX_TIER, max(1, int(world)))

    def max_squad_bonus_for_world(self, world: int) -> int:
        """Squad-bonus cap at `world`: min(SQUAD_BONUS_MAX, world-1)."""
        return min(SQUAD_BONUS_MAX, max(0, int(world) - 1))
```

In `upgrade_weapon_tier`, replace the `if target_tier > 4: return False` (line 237-238) with a world-cap check:
```python
        if target_tier > self.max_tier_for_world(self.max_world_reached):
            return False
```

In `purchase_squad_bonus`, after the `if self.squad_bonus >= target: return False` line (line 296-297), add:
```python
        if target > self.max_squad_bonus_for_world(self.max_world_reached):
            return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_progression_caps.py`
Expected: PASS — `ALL PROGRESSION CAP TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add state.py test_progression_caps.py
git commit -m "feat: world-gated weapon-tier + squad-bonus caps (#3)"
```

---

### Task 3: Shop — tier-5/6 prices + world-locked display

**Files:**
- Modify: `shop.py` — extend `TIER_PRICES` (lines 59-71); change the weapon-max check `>= 4` → `>= weapons.MAX_TIER` (line 214)
- Modify: `ui.py` — `ShopScreen` weapon-card build (lines 824-844): compute the world cap, mark a card world-locked when the next tier exceeds it; `ShopItemCard` (constructor + `_build_weapon_right_column`, ~1215-1264): render "Reach World N" for a world-locked weapon; block the `_buy` weapon path when world-locked.

- [ ] **Step 1: Extend tier prices + max check in shop.py**

In `shop.py`, extend each weapon's `TIER_PRICES` dict (lines 59-71) with tiers 5 and 6 (first pass, tunable):
```python
TIER_PRICES: dict[str, dict[int, int]] = {
    "pistol":  {2: 200,  3: 500,  4: 1200, 5: 2400,  6: 4500},
    "rifle":   {2: 400,  3: 1000, 4: 2200, 5: 4500,  6: 8500},
    "shotgun": {2: 700,  3: 1500, 4: 3000, 5: 6000,  6: 11000},
    "sniper":  {2: 1000, 3: 2500, 4: 5000, 5: 10000, 6: 19000},
}
```
(Keep the existing tiers 2-4 values; only add 5 and 6.) Then change the weapon-"owned at max" check (line 214) from:
```python
        return state.get_weapon_tier(item.weapon_id) >= 4
```
to:
```python
        return state.get_weapon_tier(item.weapon_id) >= weapons.MAX_TIER
```
Add `import weapons` to `shop.py` if not already imported.

- [ ] **Step 2: Mark the weapon card world-locked in ui.py**

Read the `ShopScreen` weapon-card build (ui.py:824-844). After `is_max = (next_price is None)` (line 828), compute the world cap and lock:
```python
            cap = state.max_tier_for_world(state.max_world_reached)
            world_locked = (not is_max) and (current_tier + 1 > cap)
            unlock_world = current_tier + 1   # world that lifts the lock
```
Then pass them to the card (add to the `ShopItemCard(...)` call at line 837-843):
```python
                weapon_world_locked=world_locked,
                weapon_unlock_world=unlock_world,
```
And make the card non-buyable while world-locked: change `can_buy = is_max or can_afford` (line 836) to:
```python
            can_buy = (is_max or can_afford) and not world_locked
```

- [ ] **Step 3: Accept + render the lock on ShopItemCard**

In `ui.py` `ShopItemCard.__init__` (around line 1044), add the two kwargs with defaults:
```python
                 weapon_world_locked: bool = False,
                 weapon_unlock_world: int = 0,
```
and store them:
```python
        self.weapon_world_locked = weapon_world_locked
        self.weapon_unlock_world = weapon_unlock_world
```
In `_build_weapon_right_column` (around line 1242, the `if self.weapon_is_max:` / upgrade-price branch), add a world-locked branch FIRST:
```python
        if self.weapon_world_locked:
            up_text = "Reach World {}".format(self.weapon_unlock_world)
            up_color = (0.95, 0.55, 0.55, 1.0)
        elif self.weapon_is_max:
            ...
```
(Leave the existing `weapon_is_max` / affordable branches after it.)

- [ ] **Step 4: Block the buy path when world-locked**

In `ShopScreen._buy` (ui.py ~860), the weapon branch: if the tapped weapon card is world-locked, play the error cue and return instead of opening the upgrade confirm. Read the weapon `_buy` branch (lines 866+) and add at its top:
```python
            cap = state.max_tier_for_world(state.max_world_reached)
            if state.get_weapon_tier(wid) + 1 > cap and state.get_weapon_tier(wid) < weapons.MAX_TIER:
                app().audio.play_sfx("error")
                return
```
(`weapons` must be imported in ui.py — it is, used elsewhere; confirm.)

- [ ] **Step 5: Verify**

```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "import shop, weapons; print(shop.TIER_PRICES['rifle'][6], shop.next_tier_price('rifle', 5))"
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_shop.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_shop.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: prints the tier-6 rifle price (8500) and the tier-5→6 next price; boot `exit=124`, no traceback.

- [ ] **Step 6: Commit**
```bash
git add shop.py ui.py
git commit -m "feat: shop sells tiers 5-6 + shows world-locked weapon upgrades (#3)"
```

---

### Task 4: World-scaled coin income (`game.py`)

**Files:**
- Modify: `game.py` — add `coin_world_factor` + apply at level-end banking (the `state.add_coins(self._coins_earned)` site, ~line 2458)
- Test: `test_coin_scaling.py`

- [ ] **Step 1: Write the failing test** — create `test_coin_scaling.py`:

```python
"""test_coin_scaling.py — coin income scales by world.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_coin_scaling.py"""
import game


def test_factor_endpoints():
    assert abs(game.coin_world_factor(1) - 1.0) < 1e-9
    assert abs(game.coin_world_factor(6) - 3.0) < 1e-9


def test_factor_monotonic():
    fs = [game.coin_world_factor(w) for w in range(1, 7)]
    assert all(fs[i] < fs[i + 1] for i in range(5))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COIN SCALING TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_coin_scaling.py`
Expected: FAIL — `AttributeError: module 'game' has no attribute 'coin_world_factor'`.

- [ ] **Step 3: Add the factor + apply at banking**

In `game.py`, add a module-level function (near the other constants):
```python
def coin_world_factor(world: int) -> float:
    """Coin-income multiplier by world so income tracks rising upgrade costs:
    W1 x1.0 ... W6 x3.0."""
    return 1.0 + 0.4 * (max(1, int(world)) - 1)
```
At the level-end banking site (find `running.state.add_coins(self._coins_earned)`, ~line 2458), scale by the current world:
```python
            if self._coins_earned > 0:
                _world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD + 1
                          if running.current_level else 1)
                _banked = int(round(self._coins_earned * coin_world_factor(_world)))
                running.state.add_coins(_banked)
```
(Use `running.current_level` / `levels.LEVELS_PER_WORLD` — both already imported/available in game.py. If a `current_world` is already on the app, use that instead.)

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_coin_scaling.py`
Expected: PASS.

- [ ] **Step 5: Structural + boot**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "import game, inspect; assert 'coin_world_factor' in inspect.getsource(game.GameScreen._end_level) or 'coin_world_factor' in inspect.getsource(game.GameScreen); print('wired OK')"
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_coin.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_coin.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `wired OK`; boot `exit=124`, no traceback. (If `_end_level` isn't where banking happens, the second `or` clause over the whole class still passes — adjust the check to the actual banking method if needed.)

- [ ] **Step 6: Commit**
```bash
git add game.py test_coin_scaling.py
git commit -m "feat: coin income scales by world (#3 economy)"
```

---

### Task 5: Late-world difficulty re-tune (`levels.py`)

**Files:**
- Modify: `levels.py` — enemy-HP curve (lines ~167-172), density endpoints (lines 184-186), `boss_hp` (line ~273)
- Test: `test_progression_curve.py`

These are playtest-tunable first-pass values; the test just locks the chosen numbers so changes are deliberate.

- [ ] **Step 1: Write the failing test** — create `test_progression_curve.py`:

```python
"""test_progression_curve.py — softened late-world difficulty.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_progression_curve.py"""
import levels


def test_enemy_hp_4_is_world6_only():
    # 4-HP enemies should not appear before ~W6 (t>=0.85).
    assert levels.get_level(40)["enemy_hp"] <= 3     # ~W4 (t~0.66)
    assert levels.get_level(60)["enemy_hp"] == 4     # last


def test_density_high_end_eased():
    c = levels.get_level(60)
    assert c["formation_columns"] == 8               # was 9
    assert abs(c["rank_interval_end"] - 75.0) < 1e-6  # was 60


def test_boss_hp_eased():
    # W6 boss (index 60) hp at the new lower top end.
    assert levels.get_level(60)["boss_hp"] == int(round(2200.0))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROGRESSION CURVE TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_progression_curve.py`
Expected: FAIL (current `enemy_hp`/density/boss values differ).

- [ ] **Step 3: Soften the enemy-HP curve**

In `levels.py`, change the enemy_hp tier block (the current `1 (t<0.10)/2 (t<0.40)/3 (t<0.75)/4` from the balance pass) to push tougher HP later:
```python
            if t < 0.10:
                enemy_hp = 1
            elif t < 0.45:
                enemy_hp = 2
            elif t < 0.85:
                enemy_hp = 3
            else:
                enemy_hp = 4
```

- [ ] **Step 4: Ease the density high-end**

In `levels.py` lines 184-186 (after B they are `lerp(5,9)` / `lerp(260,120)` / `lerp(140,60)`), lower the high endpoints:
```python
            formation_columns = int(round(_lerp(5.0, 8.0, t)))
            rank_interval_start = _lerp(260.0, 120.0, t)
            rank_interval_end = _lerp(140.0, 75.0, t)
```

- [ ] **Step 5: Ease boss HP**

In `levels.py`, change the `boss_hp` lerp (line ~273) from:
```python
            boss_hp = int(round(_lerp(1100.0, 2800.0, t))) if is_boss else 0
```
to:
```python
            boss_hp = int(round(_lerp(1100.0, 2200.0, t))) if is_boss else 0
```

- [ ] **Step 6: Run to verify it passes + regression**

```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_progression_curve.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_levels.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py
```
Expected: all PASS. (W1 values from B unchanged — these edits only touch the high-end endpoints and HP thresholds; `test_early_game_levels` still holds since W1 t≈0 values are the same.)

- [ ] **Step 7: Commit**
```bash
git add levels.py test_progression_curve.py
git commit -m "balance: soften late-world HP curve, density, boss HP (#3 re-tune, playtest-tunable)"
```

---

### Task 6: Pre-world shop-nudge modal (`ui.py`, `game.py`)

**Files:**
- Modify: `ui.py` — a `WorldIntroModal` (mirror the existing `ConfirmDialog`/`_fade_in_modal` pattern)
- Modify: `game.py` — on first entry to a new world (W≥2), show it once via the `intro_seen_wN` flags

- [ ] **Step 1: Add the modal in ui.py**

Read an existing modal (e.g. `ConfirmDialog`) and `_fade_in_modal` to mirror the structure. Add a `WorldIntroModal` that shows the world number, a "tougher ahead — upgrade in the shop (weapons up to tier N, bigger squad)" message, and two buttons: **Go to Shop** (`app().go("shop")`) and **Continue** (dismiss). Fade it in via `_fade_in_modal` and play an existing cue (e.g. `ui_open`). Keep it a self-contained class with an `open()` method like the other dialogs.

- [ ] **Step 2: Trigger it once per world in game.py**

In `game.py` `_apply_level_config` (or `on_enter`, after the level/world is known), compute the world and, for W≥2 on the **first level of that world** when its `intro_seen_wN` flag is False, show the modal and set the flag:
```python
        running = ui.app()
        if running and running.state and running.current_mode == "single":
            world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD + 1
                     if running.current_level else 1)
            in_world = ((running.current_level - 1) % levels.LEVELS_PER_WORLD + 1
                        if running.current_level else 1)
            flag = "intro_seen_w{}".format(world)
            if world >= 2 and in_world == 1 and not running.state.get_setting(flag):
                running.state.set_setting(flag, True)
                ui.WorldIntroModal(world, running.state.max_tier_for_world(world)).open()
```
(Place it where the screen is built and the modal can attach — guard so it doesn't fire during multiplayer. Read `_apply_level_config`/`on_enter` to choose the exact spot.)

- [ ] **Step 3: Verify (flag logic + boot)**

```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "
import state
s = state.GameState('/tmp/sf_modal')
assert s.get_setting('intro_seen_w2') in (False, None)
s.set_setting('intro_seen_w2', True)
assert s.get_setting('intro_seen_w2') is True
print('flag logic OK')
"
SDL_AUDIODRIVER=dummy venv/bin/python -c "import ui; assert hasattr(ui, 'WorldIntroModal'); print('modal class OK')"
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_modal.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_modal.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `flag logic OK`; `modal class OK`; boot `exit=124`, no traceback.

- [ ] **Step 4: Commit**
```bash
git add ui.py game.py
git commit -m "feat: once-per-world shop-nudge modal on entering a new world (#3)"
```

---

### Task 7: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run all new + key existing suites**
```bash
for t in test_weapon_tiers test_progression_caps test_coin_scaling test_progression_curve \
         test_early_game_levels test_early_game_gates test_levels_formation test_world_scale \
         test_combat_juice test_reward_gates_label test_aim; do
  SDL_AUDIODRIVER=dummy venv/bin/python $t.py 2>&1 | tail -1
done
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual / playtest (needs a display) — the real validation**

1. Shop locks weapon upgrades above the world cap ("Reach World N"); tiers 5-6 appear and are buyable once the world is reached.
2. Squad bonus is buyable up to the per-world cap.
3. Entering W2…W6 for the first time shows the shop-nudge modal once (with a Go-to-Shop button).
4. Coins feel sufficient: by the time a world wall is hit, the player can afford the tier/squad needed.
5. **Each world W1→W6 is beatable with the tier+squad obtainable by then** — iterate the Task-5 re-tune numbers (enemy-HP thresholds, density high-end, boss HP) and the coin factor / prices until this holds. This is the core success criterion and can only be judged by playing.

---

## Self-review notes (author)

- **Spec coverage:** #1 extended tiers → Task 1. #2 per-world tier cap → Task 2 (cap) + Task 3 (shop lock/display). #3 per-world squad cap → Task 2 + Task 3 (display). #4 coin scaling → Task 4. #5 re-tune → Task 5. #6 modal → Task 6.
- **Type/name consistency:** `weapons.MAX_TIER`/`TIER_DAMAGE_MULT`; `state._LEVELS_PER_WORLD`/`SQUAD_BONUS_MAX`/`max_world_reached`/`max_tier_for_world`/`max_squad_bonus_for_world` (enforced in `upgrade_weapon_tier`/`purchase_squad_bonus`); `shop.TIER_PRICES` tiers 5-6 + `weapons.MAX_TIER` max check; `ShopItemCard(weapon_world_locked, weapon_unlock_world)`; `game.coin_world_factor`; `ui.WorldIntroModal`; `intro_seen_wN` settings (existing).
- **Testability:** tiers, caps, coin factor, curve values, modal-flag logic are unit-tested. Shop-lock rendering + modal display are verified by boot + structural checks + manual. The "beatable per world" outcome and the re-tune numbers are explicitly playtest-only (no headless difficulty oracle).
- **Ordering:** Task 1 (tiers) → Task 2 (caps use MAX_TIER) → Task 3 (shop uses caps+prices). Tasks 4, 5, 6 independent. The `_LEVELS_PER_WORLD` drift guard (Task 2 test) catches a mismatch with `levels.LEVELS_PER_WORLD`.
