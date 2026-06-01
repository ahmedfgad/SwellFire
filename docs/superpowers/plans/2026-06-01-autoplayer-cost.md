# Autoplayer Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Charge 30 coins to enable the in-game autoplayer, once per level, only on an explicit toggle — and stop autoplay from carrying across levels (no surprise charges).

**Architecture:** A `_charge_autoplayer()` helper on `GameScreen` spends `AUTOPLAYER_COST` from the persistent bank once per level (guarded by a `_auto_paid_for_level` flag); `_toggle_auto` calls it and blocks the enable on failure; `_reset` forces autoplay OFF + stops the daemon each level (removing the carry-over restart); the Auto button advertises the cost. Single-player only. `state.spend_coins`/`can_afford` already exist — no state.py change.

**Tech Stack:** Python 3, Kivy 2.3. The spend primitive + constant are unit-tested headlessly; the GameScreen wiring is verified by a structural check + boot smoke + manual play.

---

### Task 1: Charge logic in game.py

**Files:**
- Modify: `game.py` — constant (~top, near other gameplay constants); `__init__` (~line 454); `_reset` carry-over block (lines 1272-1278); `_toggle_auto` (lines 3895-3909); `_refresh_auto_button` (lines 3911-3919)
- Test: `test_autoplayer_cost.py`

- [ ] **Step 1: Write the failing test** — create `test_autoplayer_cost.py`:

```python
"""test_autoplayer_cost.py — autoplayer cost constant + spend semantics.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_autoplayer_cost.py"""
import game
import state


def test_cost_is_30():
    assert game.AUTOPLAYER_COST == 30


def test_spend_deducts_when_affordable():
    s = state.GameState("/tmp/sf_autocost_a")
    s.data["coins_balance"] = 100
    assert s.spend_coins(game.AUTOPLAYER_COST) is True
    assert s.coins_balance == 70


def test_spend_blocked_when_unaffordable():
    s = state.GameState("/tmp/sf_autocost_b")
    s.data["coins_balance"] = 10
    assert s.spend_coins(game.AUTOPLAYER_COST) is False
    assert s.coins_balance == 10


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AUTOPLAYER COST TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_autoplayer_cost.py`
Expected: FAIL — `AttributeError: module 'game' has no attribute 'AUTOPLAYER_COST'`.

- [ ] **Step 3: Add the constant**

In `game.py`, near the other gameplay constants (e.g. after the combat-juice constants block added in the prior feature, ~line 112), add:
```python
AUTOPLAYER_COST = 30   # coins charged once per level to enable the autoplayer
```

- [ ] **Step 4: Init the per-level flag in `__init__`**

In `GameScreen.__init__`, right after `self.auto_mode = False` (line 454), add:
```python
        self._auto_paid_for_level = False   # autoplayer charged this level yet?
```

- [ ] **Step 5: Add the `_charge_autoplayer` helper**

In `game.py`, add this method to `GameScreen` (place it right before `_toggle_auto`, ~line 3895):
```python
    def _charge_autoplayer(self) -> bool:
        """Spend the per-level autoplayer cost once. Returns True if autoplay
        may run this level (already paid, or just paid); False if the player
        can't afford it. Multiplayer never touches the save, so it's free there."""
        if self._auto_paid_for_level:
            return True
        running = ui.app()
        if (running is None or running.state is None
                or running.current_mode != "single"):
            self._auto_paid_for_level = True
            return True
        if running.state.spend_coins(AUTOPLAYER_COST):
            self._auto_paid_for_level = True
            self._float_text("-{} c".format(AUTOPLAYER_COST), (1.0, 0.45, 0.40, 1.0))
            running.audio.play_sfx("purchase")
            return True
        # Can't afford — feedback, no enable.
        self._float_text("NEED {} COINS".format(AUTOPLAYER_COST),
                         (1.0, 0.45, 0.40, 1.0))
        running.audio.play_sfx("error")
        return False
```

- [ ] **Step 6: Charge on toggle-on in `_toggle_auto`**

Replace the whole `_toggle_auto` body (lines 3900-3909) with:
```python
        if not self.auto_mode:
            # Turning autoplay ON costs coins (once per level); block if broke.
            if not self._charge_autoplayer():
                return
            self.auto_mode = True
            self._refresh_auto_button()
            if self.auto is None:
                self.auto = autoplay.AutoPlayer(self)
            if not self._level_ended and not self.paused:
                self.auto.start()
        else:
            self.auto_mode = False
            self._refresh_auto_button()
            if self.auto is not None:
                self.auto.stop()
```

- [ ] **Step 7: No carry-over in `_reset`**

Replace the carry-over block in `_reset` (lines 1272-1278):
```python
        # If auto-play was on for the previous level, keep it on for this
        # one — restart the GA daemon now that the world is reset.
        self._refresh_auto_button()
        if self.auto_mode:
            if self.auto is None:
                self.auto = autoplay.AutoPlayer(self)
            self.auto.start()
```
with:
```python
        # Autoplay never carries across levels — each level starts OFF so the
        # player is never charged the per-level cost by surprise. They must
        # re-enable (and re-pay) it explicitly via the Auto button.
        self.auto_mode = False
        self._auto_paid_for_level = False
        if self.auto is not None:
            self.auto.stop()
        self._refresh_auto_button()
```

- [ ] **Step 8: Show the cost on the Auto button**

In `_refresh_auto_button`, change the `else` (off) branch (lines 3917-3919) from:
```python
        else:
            self.auto_btn.text = "Auto: Off"
            self.auto_btn.bg = [0.45, 0.45, 0.5, 1]
```
to:
```python
        else:
            self.auto_btn.text = "Auto ({}c)".format(AUTOPLAYER_COST)
            self.auto_btn.bg = [0.45, 0.45, 0.5, 1]
```

- [ ] **Step 9: Run the unit test + structural check + boot smoke**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_autoplayer_cost.py`
Expected: PASS — `ALL AUTOPLAYER COST TESTS PASSED`.

Structural check:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "
import game, inspect
assert game.AUTOPLAYER_COST == 30
assert hasattr(game.GameScreen, '_charge_autoplayer')
t = inspect.getsource(game.GameScreen._toggle_auto)
assert '_charge_autoplayer' in t
r = inspect.getsource(game.GameScreen._reset)
assert 'self.auto_mode = False' in r and 'AutoPlayer' not in r.split('never carries')[-1]
print('structural OK')
"
```
Expected: prints `structural OK`.

Boot smoke:
```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_ac.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_ac.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback referencing our files.

- [ ] **Step 10: Commit**
```bash
git add game.py test_autoplayer_cost.py
git commit -m "feat: autoplayer costs 30 coins/level, no carry-over (#17)"
```

---

### Task 2: Cost notice on the AutoPlayer settings screen

**Files:**
- Modify: `ui.py` — `AutoPlayerScreen.build` (after the `intro` label, ~line 2014)

- [ ] **Step 1: Add the notice**

In `ui.py` `AutoPlayerScreen.build`, right after `box.add_widget(intro)` (line 2014), add:
```python
        cost_note = Label(
            text="Using auto-play costs {} coins per level.".format(
                game.AUTOPLAYER_COST),
            font_size=sp(14), size_hint_y=None, height=INFO_HEIGHT,
            color=[1.0, 0.85, 0.35, 1.0], halign="center", valign="middle")
        cost_note.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(cost_note)
```

> `ui.py` must reference `game.AUTOPLAYER_COST`. Check `ui.py`'s imports: if `game` is **not** already imported there (ui is imported BY game, so a top-level `import game` in ui.py risks a circular import), do NOT add a top-level import. Instead do a **local import inside `build`**: `import game` as the first line of the `build` method body, OR hardcode the integer with a comment `# = game.AUTOPLAYER_COST`. Prefer the local import inside `build` (runs after both modules are loaded, so no circular-import problem). Confirm the boot smoke passes.

- [ ] **Step 2: Boot smoke**

```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_ac2.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_ac2.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback. (Confirms no circular-import breakage from referencing `game` in `ui.py`.)

- [ ] **Step 3: Commit**
```bash
git add ui.py
git commit -m "feat: autoplayer settings screen shows the per-level cost (#17)"
```

---

### Task 3: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the suites**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_autoplayer_cost.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && venv/bin/python test_aim.py
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual checks (reviewer, needs a display)**

Verify and report honestly:
1. **No carry-over:** finish a level with Auto on → the next level starts with Auto **Off** (button reads `Auto (30c)`), no coins deducted on entry.
2. **Charge on enable:** with ≥30 coins, tapping Auto deducts 30 (red `-30 c` float + sfx) and starts it; toggling off then on again **in the same level** is free.
3. **Can't afford:** with <30 coins, tapping Auto does nothing but the `error` cue + `NEED 30 COINS`; button stays Off; balance unchanged.
4. **Settings notice:** the AutoPlayer settings screen shows "Using auto-play costs 30 coins per level."
5. **Multiplayer:** versus play is unaffected (no charge, save untouched).

- [ ] **Step 4: Note the CoinTex follow-up**

Confirm in the report that CoinTex (#17's "apply similar") is **not** done here (separate repo) and remains an open task to do against that codebase with a cost re-derived from its smaller economy.

---

## Self-review notes (author)

- **Spec coverage:** 30/level → `AUTOPLAYER_COST` (Task 1 step 3). No carry-over → Task 1 step 7 (`_reset` forces off). Charge only on explicit toggle, once per level → Task 1 steps 5/6 (`_charge_autoplayer` + `_auto_paid_for_level` reset in step 7). Can't-afford keeps it off → step 5/6 (return False blocks enable). Button shows cost → step 8. Spend from persistent bank → `state.spend_coins` (step 5). SP-only → `current_mode != "single"` guard (step 5). Settings notice → Task 2. CoinTex out of scope → Task 3 step 4 note.
- **Type/name consistency:** `game.AUTOPLAYER_COST`; `GameScreen._auto_paid_for_level`; `GameScreen._charge_autoplayer()`; `state.spend_coins`/`coins_balance` (existing); float color `(1.0, 0.45, 0.40, 1.0)`; sfx `purchase`/`error` (both registered). Consistent across tasks.
- **Testability:** spend semantics + constant unit-tested (Task 1); GameScreen wiring via structural check + boot + manual (instantiating the screen headlessly is impractical). Circular-import risk in Task 2 explicitly handled (local import inside `build`).
- **Ordering:** Task 1 (core, incl. constant) precedes Task 2 (which references `game.AUTOPLAYER_COST`).
