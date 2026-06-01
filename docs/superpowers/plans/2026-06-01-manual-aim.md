# Manual Aim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in **Manual aim** mode where dragging steers the squad *and* tilts its firing direction (converging on a reticle), plus fix boss-level targeting so the squad shoots the adds, and make the autoplayer aim at monsters in manual mode.

**Architecture:** A new pure-math module `aim.py` (no Kivy import, fully unit-testable) computes the trailing aim-lead, the firing angle off vertical, and the reticle point. `game.py` reads a persisted `aim_mode` setting, drives the aim-lead from the existing steering target each frame, renders an `AimReticle` widget, and selects the fire target accordingly. Boss-level auto-targeting gains a "shoot the close add, else the boss" rule via a new `entities.find_nearest_threat`. The in-game GA autoplayer is unchanged — when it drives in manual mode, `game.py` simply points the reticle at the auto-aim target.

**Tech Stack:** Python 3, Kivy 2.3, existing pooled-entity / TextureSprite rendering. Density independence via `graphics.ws()`.

**Terminology (avoid confusing the two):**
- `aim_mode` — the *setting*, `"auto"` (auto-target) or `"manual"` (player-aimed). New.
- `self.auto_mode` — the *autoplayer* (GA daemon) being on/off. Existing.

---

### Task 1: `aim.py` pure-math module

**Files:**
- Create: `aim.py`
- Test: `test_aim.py`

All inputs are already-scaled world px; callers wrap raw constants in `graphics.ws()` before passing them in. `aim.py` imports only `math`, so its tests need no display and no SDL.

- [ ] **Step 1: Write the failing test**

Create `test_aim.py`:

```python
"""test_aim.py — pure-math checks for manual aim. Run:
    venv/bin/python test_aim.py
No display / SDL needed (aim.py imports only math)."""
import math

import aim


def approx(a, b, eps=1e-6):
    return abs(a - b) <= eps


def test_update_aim_lead_eases_toward_target():
    # Half-way ease in one step when ease*dt == 0.5.
    assert approx(aim.update_aim_lead(0.0, 100.0, dt=0.5, ease=1.0), 50.0)


def test_update_aim_lead_clamps_overshoot():
    # ease*dt > 1 must not overshoot past the target.
    assert approx(aim.update_aim_lead(0.0, 100.0, dt=1.0, ease=10.0), 100.0)


def test_aim_angle_zero_offset_is_straight_up():
    assert approx(aim.aim_angle(0.0, 220.0, math.radians(35)), 0.0)


def test_aim_angle_saturates_at_max():
    full = 220.0
    mx = math.radians(35)
    assert approx(aim.aim_angle(full, full, mx), mx)
    assert approx(aim.aim_angle(2 * full, full, mx), mx)      # clamped
    assert approx(aim.aim_angle(-2 * full, full, mx), -mx)    # clamped negative


def test_aim_angle_linear_in_between():
    full = 200.0
    mx = math.radians(40)
    assert approx(aim.aim_angle(100.0, full, mx), mx * 0.5)


def test_reticle_point_straight_up():
    rx, ry = aim.reticle_point(50.0, 10.0, 0.0, 300.0)
    assert approx(rx, 50.0) and approx(ry, 310.0)


def test_reticle_point_tilts_right_for_positive_angle():
    rx, ry = aim.reticle_point(0.0, 0.0, math.radians(90), 300.0)
    # 90deg off vertical => straight right: rx=+300, ry=0
    assert approx(rx, 300.0) and approx(ry, 0.0, eps=1e-4)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AIM TESTS PASSED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python test_aim.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'aim'`.

- [ ] **Step 3: Write minimal implementation**

Create `aim.py`:

```python
"""aim.py — pure manual-aim math (no Kivy import, unit-testable).

Manual aim couples the squad's firing direction to steering motion: a
trailing "aim lead" point eases toward the player's steering target; the
horizontal gap between them (how far the player is currently reaching)
maps to a firing angle off vertical. Hold still and the lead catches up,
so the aim self-centers to straight-up.

All inputs are in already-scaled world px; callers wrap raw constants in
graphics.ws() before calling. Angles are radians measured off straight-up,
positive to the right.
"""

import math


def update_aim_lead(lead_x: float, target_x: float, dt: float,
                    ease: float) -> float:
    """Ease the trailing aim-lead point toward the steering target.

    `ease` is a per-second rate; the step is clamped to [0, 1] so a large
    `dt` (or a stall) can't overshoot the target.
    """
    k = ease * dt
    if k > 1.0:
        k = 1.0
    elif k < 0.0:
        k = 0.0
    return lead_x + (target_x - lead_x) * k


def aim_angle(offset_px: float, full_px: float, max_rad: float) -> float:
    """Map a horizontal lead offset (px) to a firing angle off vertical.

    Linear until |offset| reaches `full_px`, then saturates at ±`max_rad`.
    """
    if full_px <= 0.0:
        return 0.0
    t = offset_px / full_px
    if t > 1.0:
        t = 1.0
    elif t < -1.0:
        t = -1.0
    return t * max_rad


def reticle_point(hero_x: float, muzzle_y: float, angle_rad: float,
                  lead_dist: float):
    """The convergence point the guns aim at: `lead_dist` ahead of the
    muzzle along `angle_rad` (measured off straight-up, +right)."""
    rx = hero_x + math.sin(angle_rad) * lead_dist
    ry = muzzle_y + math.cos(angle_rad) * lead_dist
    return rx, ry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python test_aim.py`
Expected: PASS — prints `ALL AIM TESTS PASSED`.

- [ ] **Step 5: Commit**

```bash
git add aim.py test_aim.py
git commit -m "feat: aim.py pure manual-aim math + tests"
```

---

### Task 2: `aim_mode` setting

**Files:**
- Modify: `state.py:10-31` (DEFAULT_SETTINGS)

- [ ] **Step 1: Add the default setting**

In `state.py`, inside `DEFAULT_SETTINGS`, add after the `"show_stats": False,` line (currently line 16):

```python
    # Aiming: "auto" = squad auto-targets (default, easy); "manual" = the
    # player tilts the squad's fire by steering (challenge mode). See aim.py.
    "aim_mode": "auto",
```

- [ ] **Step 2: Verify it loads**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "import state; s=state.GameState(); print(s.get_setting('aim_mode'))"
```
Expected: prints `auto`.

- [ ] **Step 3: Commit**

```bash
git add state.py
git commit -m "feat: add aim_mode setting (default auto)"
```

---

### Task 3: `entities.find_nearest_threat` (boss-add fix helper)

**Files:**
- Modify: `entities.py` (add function right after `find_nearest_enemy`, ~line 528)
- Test: `test_boss_targeting.py`

A "threat" is the nearest living enemy *within* a front-distance band ahead of the hero. On boss levels the fire tick will prefer a close add over the boss so adds get cleared instead of slipping into the squad.

- [ ] **Step 1: Write the failing test**

Create `test_boss_targeting.py`:

```python
"""test_boss_targeting.py — find_nearest_threat band logic.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py"""
import entities


class _Pool:
    def __init__(self, xs, ys, act):
        self.cx = list(xs)
        self.cy = list(ys)
        self.active = list(act)
        self.capacity = len(xs)


class _Ctrl:
    def __init__(self, pool):
        self.pool = pool


def test_no_enemy_in_band_returns_minus1():
    # one enemy, but it's 500 above; band is 300 => out of band.
    ctrl = _Ctrl(_Pool([100.0], [500.0], [True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == -1


def test_enemy_in_band_is_returned():
    ctrl = _Ctrl(_Pool([100.0], [200.0], [True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == 0


def test_picks_closest_in_band():
    # idx0 at front 250, idx1 at front 80 => idx1 wins.
    ctrl = _Ctrl(_Pool([100.0, 130.0], [250.0, 80.0], [True, True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == 1


def test_ignores_inactive_and_behind():
    # idx0 inactive, idx1 behind the hero (below) => none qualify.
    ctrl = _Ctrl(_Pool([100.0, 100.0], [50.0, -10.0], [False, True]))
    assert entities.find_nearest_threat(100.0, 0.0, ctrl, 300.0) == -1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL BOSS TARGETING TESTS PASSED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py`
Expected: FAIL — `AttributeError: module 'entities' has no attribute 'find_nearest_threat'`.

- [ ] **Step 3: Write the implementation**

In `entities.py`, immediately after the `find_nearest_enemy` function (after line 528, before `fire_weapon`), add:

```python
def find_nearest_threat(hero_cx: float, hero_cy: float,
                        enemy_controller: EnemyController,
                        max_front: float) -> int:
    """Nearest living enemy ahead of the hero AND within `max_front` px.

    Used on boss levels: the boss's adds drift down the road, and we want
    the squad to clear an add that has come close (a real threat to the
    squad) rather than dumping every shot into the boss while adds slip
    through. Returns -1 when no enemy is inside the band.
    """
    pool = enemy_controller.pool
    active = pool.active
    cx = pool.cx
    cy = pool.cy
    best_idx = -1
    best_front = float("inf")
    for i in range(pool.capacity):
        if not active[i]:
            continue
        front = cy[i] - hero_cy            # ahead of hero = positive
        if front < 0.0 or front > max_front:
            continue
        score = front + abs(cx[i] - hero_cx) * 0.30
        if score < best_front:
            best_front = score
            best_idx = i
    return best_idx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py`
Expected: PASS — prints `ALL BOSS TARGETING TESTS PASSED`.

- [ ] **Step 5: Commit**

```bash
git add entities.py test_boss_targeting.py
git commit -m "feat: entities.find_nearest_threat for boss-add targeting"
```

---

### Task 4: `AimReticle` widget

**Files:**
- Modify: `graphics.py` (add class after `ShieldAura`, ~line 850)

A canvas widget: a faint aim line from the squad up to a pulsing reticle ring. `set_endpoints(sx, sy, rx, ry)` positions it each frame; `set_locked(bool)` turns the ring red (target under reticle) vs cyan. `show()/hide()` toggle a gentle pulse, mirroring `ShieldAura`.

- [ ] **Step 1: Add the widget**

In `graphics.py`, after the `ShieldAura` class ends (line 849, before `class ParticleBurst`), add:

```python
class AimReticle(Widget):
    """Manual-aim reticle: a faint line from the squad up to a pulsing ring
    at the convergence point. Cyan normally, red + thicker when a target is
    under it. Drawn in ``canvas`` (no stage depth issue — it sits above the
    road like the shield aura). Position via ``set_endpoints`` each frame.
    """

    R = 16.0   # ring radius in logical px (caller may pass ws()-scaled size)

    def __init__(self, radius: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        self._r = radius if radius is not None else self.R
        self._locked = False
        with self.canvas:
            self._line_color = Color(0.55, 0.88, 1.0, 0.30)
            self._line = Line(width=1.6)
            self._ring_color = Color(0.55, 0.88, 1.0, 0.95)
            self._ring = Line(width=2.2)
            self._dot_color = Color(0.85, 0.97, 1.0, 0.9)
            self._dot = Line(width=1.4)
        self._anim = None
        self._sx = self._sy = self._rx = self._ry = 0.0

    def set_endpoints(self, sx, sy, rx, ry):
        self._sx, self._sy, self._rx, self._ry = sx, sy, rx, ry
        self._line.points = [sx, sy, rx, ry]
        self._ring.circle = (rx, ry, self._r)
        self._dot.circle = (rx, ry, self._r * 0.28)

    def set_locked(self, locked: bool):
        if locked == self._locked:
            return
        self._locked = locked
        if locked:
            self._ring_color.rgba = (1.0, 0.35, 0.30, 1.0)
            self._line_color.rgba = (1.0, 0.45, 0.40, 0.45)
            self._ring.width = 3.0
        else:
            self._ring_color.rgba = (0.55, 0.88, 1.0, 0.95)
            self._line_color.rgba = (0.55, 0.88, 1.0, 0.30)
            self._ring.width = 2.2

    def show(self):
        self.opacity = 1.0
        if self._anim is None:
            anim = (Animation(a=0.55, duration=0.5, t="in_out_sine")
                    + Animation(a=0.98, duration=0.5, t="in_out_sine"))
            anim.repeat = True
            anim.start(self._ring_color)
            self._anim = anim

    def hide(self):
        self.opacity = 0.0
        if self._anim is not None:
            self._anim.cancel(self._ring_color)
            self._anim = None
```

- [ ] **Step 2: Smoke-check it imports and instantiates**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "import graphics; r=graphics.AimReticle(); r.set_endpoints(0,0,10,300); r.set_locked(True); r.show(); r.hide(); print('AimReticle OK')"
```
Expected: prints `AimReticle OK` (no exception).

> Note: `Color`, `Line`, `Animation`, `Widget` are already imported at the top of `graphics.py` (used by `ShieldAura`). If the smoke check raises `NameError`, add the missing import next to the existing graphics-instruction imports — do not duplicate.

- [ ] **Step 3: Commit**

```bash
git add graphics.py
git commit -m "feat: AimReticle widget for manual aim"
```

---

### Task 5: Wire manual aim into `game.py`

**Files:**
- Modify: `game.py` — constants block (~line 52), imports (~line 35), `GameScreen.__init__` aim state (~line 329), `_reset` (~line 1181), hero-creation (~line 918), `_update` reticle block (~line 1609), fire tick (~line 1811-1864)

This is the integration task. Do the steps in order and run the manual smoke check at the end.

- [ ] **Step 1: Import `aim` and add tuning constants**

In `game.py`, find the existing `import` block that pulls in sibling modules (where `autoplay`, `boosters`, `entities`, `weapons` are imported, ~line 35) and add:

```python
import aim
```

Then near the other world-px constants (right after `HERO_BOTTOM_FRAC = 0.16`, line 52), add:

```python
# --- manual aim tuning (world-px; wrapped in graphics.ws() at use) ---------
AIM_LEAD_EASE = 7.0           # per-sec ease of the trailing aim-lead point
AIM_OFFSET_FULL = 220.0       # lead-gap (px) that maps to the max tilt angle
AIM_MAX_DEG = 35.0            # max firing tilt off vertical
RETICLE_LEAD_DIST = 360.0     # px ahead of the muzzle the reticle sits
BOSS_ADD_THREAT_FRONT = 360.0 # px band: shoot an add this close, else the boss
```

And just below them:

```python
import math as _math_aim
AIM_MAX_RAD = _math_aim.radians(AIM_MAX_DEG)
```

> `game.py` already imports `math` at top; if so, use `math.radians(AIM_MAX_DEG)` directly and skip the `_math_aim` alias. Check the top of the file first.

- [ ] **Step 2: Initialize aim state in `__init__`**

In `GameScreen.__init__`, right after `self._hero_target_x = 0.0` (line 329), add:

```python
        # Manual-aim runtime state (see aim.py). _aim_mode is cached per
        # level in _reset; the reticle/auto target are recomputed each frame.
        self._aim_mode = "auto"
        self._aim_lead_x = 0.0
        self._aim_angle = 0.0
        self._reticle_x = 0.0
        self._reticle_y = 0.0
        self._auto_target = None       # (x, y) stashed by the fire tick for #9
        self.aim_reticle = None
```

- [ ] **Step 3: Create the reticle widget at hero creation**

In `_build_level_widgets` (or wherever the hero is created), right after the hero is added to the stage (`self.stage.add_widget(self.hero)`, line 918), add:

```python
        if self.aim_reticle is None:
            self.aim_reticle = graphics.AimReticle(
                radius=graphics.ws(graphics.AimReticle.R),
                size_hint=(None, None), size=(1, 1),
            )
            self.stage.add_widget(self.aim_reticle)
```

- [ ] **Step 4: Cache mode + reset aim state in `_reset`**

In `_reset`, inside the `if self.hero is not None:` block, right after `self._hero_target_x = hero_cx` (line 1181), add:

```python
            self._aim_lead_x = hero_cx
            self._aim_angle = 0.0
            self._reticle_x = hero_cx
        running_app = ui.app()
        self._aim_mode = (running_app.state.get_setting("aim_mode")
                          if running_app and running_app.state else "auto")
        self._auto_target = None
        if self.aim_reticle is not None:
            self.aim_reticle.hide()
```

- [ ] **Step 5: Update the reticle each frame in `_update`**

In `_update`, right after the hero motion block sets `self.hero.center_x` and `self.hero.y` (after line 1613, where `bob` is applied), add:

```python
            # Manual-aim reticle. In manual mode + human control, the reticle
            # is driven by the trailing aim-lead (aim follows steering). In
            # manual mode while the autoplayer drives, it follows the auto-aim
            # target stashed by the fire tick (#9 — show where the GA aims).
            if self._aim_mode == "manual" and self.aim_reticle is not None:
                muzzle_y = self.hero.center_y + graphics.ws(MUZZLE_OFFSET_Y)
                if self.auto_mode:
                    if self._auto_target is not None:
                        rx, ry = self._auto_target
                    else:
                        rx = self.hero.center_x
                        ry = muzzle_y + graphics.ws(RETICLE_LEAD_DIST)
                else:
                    self._aim_lead_x = aim.update_aim_lead(
                        self._aim_lead_x, self._hero_target_x, dt, AIM_LEAD_EASE)
                    offset = self._hero_target_x - self._aim_lead_x
                    self._aim_angle = aim.aim_angle(
                        offset, graphics.ws(AIM_OFFSET_FULL), AIM_MAX_RAD)
                    rx, ry = aim.reticle_point(
                        self.hero.center_x, muzzle_y, self._aim_angle,
                        graphics.ws(RETICLE_LEAD_DIST))
                self._reticle_x, self._reticle_y = rx, ry
                self.aim_reticle.set_endpoints(
                    self.hero.center_x, muzzle_y, rx, ry)
                self.aim_reticle.show()
            elif self.aim_reticle is not None:
                self.aim_reticle.hide()
```

> `dt` is the `_update` argument and `MUZZLE_OFFSET_Y` is the module constant already used at line 1830 — both are in scope here.

- [ ] **Step 6: Select the fire target by mode (and apply the boss-add fix)**

In the fire tick, replace the target-selection block (lines 1812-1826, from the comment `# On boss levels aim at the boss itself...` through the `else: has_target = False`) with:

```python
                manual_human = (self._aim_mode == "manual"
                                and not self.auto_mode)
                if manual_human:
                    # Player-aimed: fire at the reticle the _update block set.
                    target_x, target_y, has_target = (
                        self._reticle_x, self._reticle_y, True)
                else:
                    # Auto-aim (also used when the GA autoplayer drives, even
                    # in manual mode — it aims at monsters per #9). On boss
                    # levels prefer a close add over the boss so adds get
                    # cleared instead of slipping into the squad (#5).
                    target_x = target_y = 0.0
                    has_target = False
                    if self.boss is not None and self.boss.alive:
                        _ti = entities.find_nearest_threat(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller,
                            graphics.ws(BOSS_ADD_THREAT_FRONT))
                        if _ti >= 0:
                            target_x = self.enemy_pool.cx[_ti]
                            target_y = self.enemy_pool.cy[_ti]
                        else:
                            target_x, target_y = self.boss.cx, self.boss.cy
                        has_target = True
                    else:
                        _ti = entities.find_nearest_enemy(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller)
                        if _ti >= 0:
                            target_x = self.enemy_pool.cx[_ti]
                            target_y = self.enemy_pool.cy[_ti]
                            has_target = True
                    # Stash for the reticle when the GA drives in manual mode.
                    self._auto_target = (target_x, target_y) if has_target else None
```

- [ ] **Step 7: Lock the reticle when a target is under it**

Still in the fire tick, inside the `if has_target:` block, right before `entities.fire_from_positions(` (line 1860), add a lock cue when in manual mode:

```python
                    if self._aim_mode == "manual" and self.aim_reticle is not None:
                        # Lock-flash the reticle if an enemy sits near the
                        # convergence point (clear "you will hit this" cue).
                        near = entities.find_nearest_threat(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller,
                            graphics.ws(RETICLE_LEAD_DIST * 1.4))
                        locked = False
                        if self.boss is not None and self.boss.alive:
                            locked = abs(target_x - self._reticle_x) < graphics.ws(60.0)
                        elif near >= 0:
                            locked = (abs(self.enemy_pool.cx[near] - target_x)
                                      < graphics.ws(60.0))
                        self.aim_reticle.set_locked(locked)
```

> For `manual_human`, `target_x/target_y` *is* the reticle point, so the lock test compares the nearest enemy to that point. For the GA-in-manual case the reticle equals `_auto_target`, so `target_x == _reticle_x` and it locks whenever there's a target — correct.

- [ ] **Step 8: Run the unit tests (regression — nothing should break)**

Run:
```bash
venv/bin/python test_aim.py && SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all three print their PASS lines.

- [ ] **Step 9: Smoke-check the game boots**

Run:
```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py; echo "exit=$?"
```
Expected: window opens without traceback; `exit=124` (killed by timeout) is success. Any Python traceback in output is a failure — fix before committing.

- [ ] **Step 10: Commit**

```bash
git add game.py
git commit -m "feat: wire manual aim, reticle, and boss-add targeting into game loop"
```

---

### Task 6: Settings — Auto/Manual toggle

**Files:**
- Modify: `ui.py:1684-1759` (`SettingsScreen`)

`aim_mode` is a string, not a bool, so it needs its own toggle handler (the existing `_toggle` flips booleans).

- [ ] **Step 1: Add the button in `build`**

In `SettingsScreen.build`, right after the `self.stats_btn` is added (after line 1703), add:

```python
        self.aim_btn = StyledButton(size_hint_y=None, height=BTN_HEIGHT)
        self.aim_btn.bind(on_release=lambda *_: self._toggle_aim_mode())
        box.add_widget(self.aim_btn)
```

- [ ] **Step 2: Add the toggle handler and label refresh**

In `SettingsScreen`, add this method after `_toggle` (after line 1759):

```python
    def _toggle_aim_mode(self):
        running = app()
        cur = running.state.get_setting("aim_mode")
        running.state.set_setting("aim_mode", "manual" if cur == "auto" else "auto")
        running.audio.play_sfx("ui_tap")
        self._refresh_labels()
```

> If `"ui_tap"` is not a registered SFX name, use whatever the other settings buttons play, or drop the `play_sfx` line — check `audio.py: SFX_FILES`. Buttons may already play a tap sound via `StyledButton`; if so, omit `play_sfx` to avoid a double cue.

Then in `_refresh_labels`, at the end (after line 1752), add:

```python
        mode = running.state.get_setting("aim_mode")
        manual = (mode == "manual")
        self.aim_btn.text = "Aiming: {}".format("Manual" if manual else "Auto")
        self.aim_btn.bg = [0.85, 0.55, 0.2, 1] if manual else [0.2, 0.6, 0.7, 1]
```

- [ ] **Step 3: Smoke-check the settings screen**

Run:
```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py; echo "exit=$?"
```
Then describe to the reviewer: the change is verified visually by opening Settings and toggling **Aiming: Auto ↔ Manual**. (Headless can't click; the boot smoke check confirms no import/build error.)

- [ ] **Step 4: Commit**

```bash
git add ui.py
git commit -m "feat: Settings toggle for Auto/Manual aiming"
```

---

### Task 7: Investigate boss "faster firing" (#6)

**Files:**
- Read-only investigation; no code change unless a real multiplier is found.

- [ ] **Step 1: Search for any boss-only fire-rate change**

Run:
```bash
grep -n "fire_cooldown\|fire_rate\|OVERDRIVE_FIRE\|is_boss\|boss" game.py | grep -i "fire\|cooldown\|rate"
```
And review the fire tick (game.py:1809-1867). Confirm `self._fire_cooldown = 1.0 / weapon.fire_rate` is the only cadence source and that no boss branch divides it (only Overdrive does, which is not boss-specific).

- [ ] **Step 2: Record the finding**

If no boss-only multiplier exists (expected): append a short note to the design doc's section F documenting that the faster feel is perceptual (head-start squad + convergence), no code change. If a real multiplier IS found, STOP and report it to the reviewer with the file:line before changing anything — removing it may interact with boss HP tuning (`BOSS_TARGET_SECONDS`).

- [ ] **Step 3: Commit (doc only, if a note was added)**

```bash
git add docs/superpowers/specs/2026-06-01-manual-aim-design.md
git commit -m "docs: record boss fire-rate investigation (#6) finding"
```

---

### Task 8: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full unit-test set**

Run:
```bash
venv/bin/python test_aim.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke check**

Run:
```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py; echo "exit=$?"
```
Expected: no traceback; `exit=124`.

- [ ] **Step 3: Manual play check (reviewer, needs a display)**

Verify, and report honestly what was and wasn't checked:
1. **Auto mode unchanged:** default game plays as before; guns auto-target.
2. **Manual mode:** set Settings → Aiming: Manual. Reticle + aim line visible; dragging tilts the reticle; bullets converge on it; reticle locks red over an enemy; releasing recenters aim to straight-up.
3. **Boss level (Auto mode):** the squad now shoots adds that come close instead of letting them pass into the squad.
4. **Autoplayer in Manual mode:** turn on Auto (autoplayer); the reticle follows monsters/boss while it steers for gates.

- [ ] **Step 4: Note any un-juiced gaps**

Per CLAUDE.md, state explicitly what was left without visual/audio feedback (planned: no per-shot aim SFX by design; lock cue is visual-only). Confirm nothing else silent was introduced.

---

## Self-review notes (author)

- **Spec coverage:** #8 manual aim → Tasks 1,2,4,5,6. #5 boss-add fix → Tasks 3,5(step6). #6 investigation → Task 7. #9 autoplayer aiming → Task 5 (steps 5–6, `_auto_target` + GA-in-manual path). Default Auto → Task 2. Self-centering aim → Task 1 + Task 5 step 5. Reticle juice/lock → Tasks 4 + 5 step 7. Density (`ws`) → applied at every world-px use in Task 5.
- **Type/name consistency:** `aim.update_aim_lead / aim.aim_angle / aim.reticle_point`, `entities.find_nearest_threat`, `graphics.AimReticle` (`.set_endpoints/.set_locked/.show/.hide`), `self._aim_mode/_aim_lead_x/_aim_angle/_reticle_x/_reticle_y/_auto_target/aim_reticle`, setting key `"aim_mode"` — all used consistently across tasks.
- **Open assumptions to verify during build (flagged inline):** `math` already imported in game.py (Task 5 step 1); `Color/Line/Animation` imported in graphics.py (Task 4 step 2); SFX name for the toggle (Task 6 step 2). Each step says what to do if the assumption is wrong.
