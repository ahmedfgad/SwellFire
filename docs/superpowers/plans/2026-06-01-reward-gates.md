# Reward Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reward gates auto-activate their booster on pass (scaled by a ×N strength) instead of banking a charge, and show the booster name with its "×N" factor on a separate line.

**Architecture:** A pure `boosters.refreshed_until` helper encodes the refresh-not-rob timer rule. `gates.py` gives reward gates a ×N value (1–3, world-weighted) and renders a two-line name/×N bonus label. `game.py` splits each gate-acquirable booster into an `_apply_<b>_effect(scale)` (the work, no charge) and the existing button handler (charge check + spend), and `_on_apply_gate` calls the scaled effect directly instead of incrementing a balance. Shop charges + manual buttons are unchanged.

**Tech Stack:** Python 3, Kivy 2.3. Tests headless under `SDL_AUDIODRIVER=dummy`; pure logic (timer math, ×N, labels) is unit-tested; the GameScreen effect wiring is verified by boot smoke + the manual checklist.

---

### Task 1: `boosters.refreshed_until` (refresh-not-rob timer math)

**Files:**
- Modify: `boosters.py` — add a module-level helper
- Test: `test_reward_boosters.py`

- [ ] **Step 1: Write the failing test** — create `test_reward_boosters.py`:

```python
"""test_reward_boosters.py — refresh-not-rob timer math for timed boosters.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py"""
import boosters


def test_inactive_sets_full_scaled_duration():
    # not active (current <= now): new end = now + base*scale
    assert boosters.refreshed_until(0.0, 10.0, 3.0, 1) == 13.0
    assert boosters.refreshed_until(0.0, 10.0, 3.0, 2) == 16.0


def test_active_extends_when_new_is_longer():
    # active until 20, now 10, base 3, scale 4 -> now+12=22 > 20 -> 22
    assert boosters.refreshed_until(20.0, 10.0, 3.0, 4) == 22.0


def test_active_never_shortens():
    # active until 20, now 10, base 3, scale 1 -> now+3=13 < 20 -> keep 20
    assert boosters.refreshed_until(20.0, 10.0, 3.0, 1) == 20.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL REWARD BOOSTER TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py`
Expected: FAIL — `AttributeError: module 'boosters' has no attribute 'refreshed_until'`.

- [ ] **Step 3: Add the helper**

In `boosters.py`, add at module level (after the duration constants near the bottom):
```python
def refreshed_until(current_until: float, now: float,
                    base_duration: float, scale: int = 1) -> float:
    """New `*_active_until` for a timed booster, applying refresh-not-rob:
    a (re)activation extends the timer to `now + base_duration*scale` but never
    shortens an already-longer active window."""
    return max(current_until, now + base_duration * max(1, int(scale)))
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py`
Expected: PASS — `ALL REWARD BOOSTER TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add boosters.py test_reward_boosters.py
git commit -m "feat: boosters.refreshed_until (refresh-not-rob timer rule)"
```

---

### Task 2: ×N reward strength + two-line bonus label (gates.py)

**Files:**
- Modify: `gates.py` — `GateSpawner` (`_build_bonus_pair` ~440-448, `_pick_op` grenade entry ~478/489-492, add `_bonus_value`); `Gate` widget (`__init__` ~147-174, `_sync` ~241-254)
- Test: `test_reward_gates_label.py`

- [ ] **Step 1: Write the failing test** — create `test_reward_gates_label.py`:

```python
"""test_reward_gates_label.py — reward-gate xN strength + two-line label.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py"""
import gates


def test_bonus_value_in_range():
    sp = gates.GateSpawner(controller=None, seed=1)
    sp.world_tier = 6
    vals = {sp._bonus_value(gates.OP_FREEZE) for _ in range(200)}
    assert vals <= {1, 2, 3} and len(vals) >= 1
    sp2 = gates.GateSpawner(controller=None, seed=1)
    sp2.world_tier = 1
    assert all(sp2._bonus_value(gates.OP_FREEZE) in (1, 2, 3) for _ in range(50))


def test_build_bonus_pair_emits_xN_label():
    sp = gates.GateSpawner(controller=None, seed=3)
    sp.world_tier = 5
    sp.allowed_ops = ["reinforce", "freeze", "overdrive", "magnet"]
    sp.allowed_weapons = []
    got = False
    for _ in range(40):
        pair = sp._build_bonus_pair()
        if pair is None:
            continue
        for op, value, label in pair:
            assert value in (1, 2, 3)
            assert label == "{} x{}".format(
                gates.CONSUMABLE_BONUS[op], value), label
            got = True
    assert got, "no bonus pair produced"


def test_consumable_gate_renders_two_lines():
    g = gates.Gate("freeze", 2, "FREEZE x2")
    g.size = (120, 112)
    g.pos = (0, 0)
    # name line + factor line; factor shows the multiplier
    assert g._name_label.text == "FREEZE"
    assert "2" in g._factor_label.text
    assert g.label_text == "FREEZE x2"   # canonical ASCII preserved


def test_weapon_gate_stays_single_line():
    g = gates.Gate("weapon", "rifle", "RIFLE")
    g.size = (120, 112)
    g.pos = (0, 0)
    assert g._name_label.text == "RIFLE"
    assert getattr(g, "_factor_label", None) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL REWARD GATE LABEL TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py`
Expected: FAIL — `AttributeError: 'GateSpawner' object has no attribute '_bonus_value'` (or the two-line label asserts).

- [ ] **Step 3: Add `_bonus_value` + ×N to the spawner**

In `gates.py` `GateSpawner`, add this method (e.g. right before `_build_bonus_pair`):
```python
    def _bonus_value(self, op: str) -> int:
        """Reward-gate strength xN (1-3): rarer-higher, skewing up by world."""
        tier = self.world_tier
        if tier <= 2:
            weights = [0.80, 0.20, 0.00]
        elif tier <= 4:
            weights = [0.55, 0.33, 0.12]
        else:
            weights = [0.40, 0.35, 0.25]
        return self._rng.choices([1, 2, 3], weights=weights)[0]
```

In `_build_bonus_pair`, replace the consumable-candidate loop (lines 440-448):
```python
        for op, name in CONSUMABLE_BONUS.items():
            if op not in self.allowed_ops:
                continue
            if op == OP_GRENADE:
                if self.grenade_gates_spawned >= self.max_grenade_gates:
                    continue
                candidates.append((OP_GRENADE, 1, "GRENADE x1"))
            else:
                candidates.append((op, 1, name))
```
with:
```python
        for op, name in CONSUMABLE_BONUS.items():
            if op not in self.allowed_ops:
                continue
            if op == OP_GRENADE and self.grenade_gates_spawned >= self.max_grenade_gates:
                continue
            n = self._bonus_value(op)
            candidates.append((op, n, "{} x{}".format(name, n)))
```
(`CONSUMABLE_BONUS[OP_GRENADE]` is `"GRENADE"`, so grenade now reads `"GRENADE xN"` too — same format as before for N=1.)

In `_pick_op`, change the grenade `op_table` entry (line 478) so its values allow ×N:
```python
            OP_GRENADE: ([1, 2, 3],        lambda v: "GRENADE x{}".format(v)),
```
and right after `value = self._rng.choice(values)` (line 490), add a grenade-specific weighted pick so it matches the rarity curve:
```python
            if op == OP_GRENADE:
                value = self._bonus_value(OP_GRENADE)
```

- [ ] **Step 4: Render the two-line consumable label in the `Gate` widget**

In `gates.py` `Gate.__init__`, the bonus branch currently builds a single `_name_label`. Replace the `else:` (non-math) block (lines 164-172) with:
```python
        elif op in CONSUMABLE_BONUS:
            # Consumable reward gate: name on top, "xN" factor on its own line
            # below (amber, like the math accent) — never cram onto one line.
            self._factor_label = None
            name = CONSUMABLE_BONUS[op]
            self._name_label = Label(
                text=name, font_size=(sp(28) if len(name) <= 9 else sp(22)),
                bold=True, color=(1, 1, 1, 1), halign="center", valign="middle",
                outline_width=2, outline_color=_OUTLINE_RGBA,
            )
            self._factor_label = Label(
                text="×{}".format(int(value)), font_size=sp(26), bold=True,
                color=OP_ACCENT_RGBA, halign="center", valign="middle",
                outline_width=2, outline_color=_OUTLINE_RGBA,
            )
            self.add_widget(self._name_label)
            self.add_widget(self._factor_label)
            self._labels = [self._name_label, self._factor_label]
        else:
            fs = sp(30) if len(label_text) <= 7 else sp(24)
            self._name_label = Label(
                text=label_text, font_size=fs, bold=True, color=(1, 1, 1, 1),
                halign="center", valign="middle",
                outline_width=2, outline_color=_OUTLINE_RGBA,
            )
            self.add_widget(self._name_label)
            self._labels = [self._name_label]
```
Also, just before this branch (where `self._is_math = op in MATH_OPS` is set), initialize the attribute so non-consumable gates can be introspected safely — add after the `self._is_math = ...` line:
```python
        self._factor_label = None
```

In `Gate._sync`, the non-math branch currently positions a single `_name_label` over the whole gate (lines 251-254). Replace that `else:` block with a consumable-aware layout:
```python
        elif self._factor_label is not None:
            # Name on the top band, xN factor on the bottom band (mirrors the
            # math op/expression split so the pop-scale never reflows).
            name_h = self.height * 0.52
            self._name_label.pos = (self.x, self.y + self.height * 0.44)
            self._name_label.size = (self.width, name_h)
            self._name_label.text_size = (self.width, name_h)
            fac_h = self.height * 0.42
            self._factor_label.pos = (self.x, self.y + self.height * 0.04)
            self._factor_label.size = (self.width, fac_h)
            self._factor_label.text_size = (self.width, fac_h)
        else:
            self._name_label.pos = self.pos
            self._name_label.size = self.size
            self._name_label.text_size = self.size
```

- [ ] **Step 5: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py`
Expected: PASS — `ALL REWARD GATE LABEL TESTS PASSED`.

- [ ] **Step 6: Regression + boot smoke**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_gate_emphasis.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_rg.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_rg.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: both suites PASS; boot `exit=124`, no traceback.

- [ ] **Step 7: Commit**
```bash
git add gates.py test_reward_gates_label.py
git commit -m "feat: reward gates grant xN strength + two-line name/xN label (#15)"
```

---

### Task 3: Auto-activate scaled effects (game.py)

**Files:**
- Modify: `game.py` — `_on_apply_gate` (lines 2322-2336), and the activation methods `_detonate_grenade` (~2743), `_activate_reinforce` (~2592), `_activate_freeze` (~2616), `_activate_overdrive` (~2633), `_activate_magnet` (~2653)

The pattern: extract an `_apply_<b>_effect(scale=1)` (the work, no charge check/decrement) and make the existing handler do the charge check/guard/decrement then call it with scale 1. Gates call the effect with `int(gate.value)`.

- [ ] **Step 1: Split `reinforce` into effect + handler**

Replace `_activate_reinforce` (lines 2592-2614) with:
```python
    def _apply_reinforce_effect(self, scale: int = 1) -> None:
        """Instantly grow the squad by REINFORCE_AMOUNT * scale (no charge)."""
        if self._level_ended or self.squad_count >= MAX_SQUAD:
            return
        amount = boosters.REINFORCE_AMOUNT * max(1, int(scale))
        self.squad_count = min(MAX_SQUAD, self.squad_count + amount)
        ui.app().audio.play_sfx("reinforce")
        if self.hero is not None and self.particle_controller is not None:
            self.particle_controller.burst(
                self.hero.center_x, self.hero.center_y,
                count=20, speed=360.0, ttl=0.55, size=13.0,
                frame="runner_blue", rng=self._fire_rng,
            )
        self._float_text("+{} SQUAD!".format(amount),
                         boosters.BOOSTERS["reinforce"].hud_color)
        self._add_shake(2.0)

    def _activate_reinforce(self) -> None:
        """Burn one reinforcement kit (shop charge): instantly grow the squad."""
        if self._level_ended:
            return
        if self.reinforce_count <= 0:
            self._booster_unavailable("reinforce")
            return
        if self.squad_count >= MAX_SQUAD:
            self._booster_unavailable("reinforce", message="SQUAD FULL!")
            return
        self.reinforce_count -= 1
        self._apply_reinforce_effect(1)
```

- [ ] **Step 2: Split `freeze` (timed) into effect + handler**

Replace `_activate_freeze` (lines 2616-2631) with:
```python
    def _apply_freeze_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.freeze_active_until = boosters.refreshed_until(
            self.freeze_active_until, self._run_time,
            boosters.FREEZE_DURATION_SEC, scale)
        ui.app().audio.play_sfx("freeze")
        self._booster_burst(0.55, 0.85, 1.0)
        self._float_text("FREEZE!", boosters.BOOSTERS["freeze"].hud_color)
        self._add_shake(1.5)

    def _activate_freeze(self) -> None:
        if self._level_ended:
            return
        if self.freeze_count <= 0:
            self._booster_unavailable("freeze")
            return
        if self.freeze_active_until > self._run_time:
            return
        self.freeze_count -= 1
        self._apply_freeze_effect(1)
```

- [ ] **Step 3: Split `overdrive` (timed) into effect + handler**

Replace `_activate_overdrive` (lines 2633-2651) with:
```python
    def _apply_overdrive_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.overdrive_active_until = boosters.refreshed_until(
            self.overdrive_active_until, self._run_time,
            boosters.OVERDRIVE_DURATION_SEC, scale)
        self._fire_cooldown = 0.0
        ui.app().audio.play_sfx("overdrive")
        self._booster_burst(1.0, 0.55, 0.15)
        if self.hero is not None:
            self.hero.flash(duration=0.5, color=(1.0, 0.55, 0.10, 0.6))
        self._float_text("OVERDRIVE!", boosters.BOOSTERS["overdrive"].hud_color)
        self._add_shake(1.5)

    def _activate_overdrive(self) -> None:
        if self._level_ended:
            return
        if self.overdrive_count <= 0:
            self._booster_unavailable("overdrive")
            return
        if self.overdrive_active_until > self._run_time:
            return
        self.overdrive_count -= 1
        self._apply_overdrive_effect(1)
```

- [ ] **Step 4: Split `magnet` (timed) into effect + handler**

Read `_activate_magnet` (lines 2653-2669) to capture its full body (the part after `self.magnet_active_until = ...` — the burst/float/shake). Replace it with:
```python
    def _apply_magnet_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.magnet_active_until = boosters.refreshed_until(
            self.magnet_active_until, self._run_time,
            boosters.MAGNET_DURATION_SEC, scale)
        ui.app().audio.play_sfx("magnet")
        self._booster_burst(0.80, 0.45, 0.95)
        self._float_text("MAGNET!", boosters.BOOSTERS["magnet"].hud_color)
        self._add_shake(1.5)

    def _activate_magnet(self) -> None:
        if self._level_ended:
            return
        if self.magnet_count <= 0:
            self._booster_unavailable("magnet")
            return
        if self.magnet_active_until > self._run_time:
            return
        self.magnet_count -= 1
        self._apply_magnet_effect(1)
```
NOTE: read the existing `_activate_magnet` body first; if it has extra lines (e.g. a hero flash or specific float text), preserve them in `_apply_magnet_effect` rather than the version above. The above mirrors the freeze/overdrive shape — match the real existing juice.

- [ ] **Step 5: Split `grenade` (instant) into effect + handler**

Replace `_detonate_grenade` (lines 2743-2795) so the blast scales with `scale` (radius and damage), and the handler spends a charge:
```python
    def _apply_grenade_effect(self, scale: int = 1) -> None:
        """Detonate a grenade (no charge): kill enemies within a scaled radius."""
        if self.hero is None or self.enemy_controller is None or self._level_ended:
            return
        scale = max(1, int(scale))
        hero_cx = self.hero.center_x
        hero_cy = self.hero.center_y
        grenade_radius = graphics.ws(GRENADE_RADIUS) * (1.0 + 0.5 * (scale - 1))
        r2 = grenade_radius * grenade_radius
        ep = self.enemy_pool
        active = ep.active
        cx = ep.cx
        cy = ep.cy
        kills = 0
        for i in range(ep.capacity):
            if not active[i]:
                continue
            dx = cx[i] - hero_cx
            dy = cy[i] - hero_cy
            if dx * dx + dy * dy <= r2:
                self._spawn_death_polish(cx[i], cy[i])
                ep.release(i)
                self.enemy_controller.recycled_total += 1
                kills += 1
        if self.boss_controller is not None and self.boss is not None and self.boss.alive:
            dx = self.boss.cx - hero_cx
            dy = self.boss.cy - hero_cy
            if dx * dx + dy * dy <= r2 * 1.6 * 1.6:
                died = self.boss_controller.take_damage(20 * scale)
                if died and not self._level_ended:
                    self._end_level(won=True)
        self.kills_total += kills
        if self.particle_controller is not None:
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=24, speed=440.0, ttl=0.55,
                size=14.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=14, speed=280.0, ttl=0.70,
                size=18.0, frame="enemy_red", rng=self._fire_rng,
            )
        self._add_shake(8.0)
        ui.app().audio.play_sfx("explosion")
        self._float_text("GRENADE!", boosters.BOOSTERS["grenade"].hud_color)

    def _detonate_grenade(self) -> None:
        """Burn one grenade (shop charge) and detonate."""
        if self.hero is None or self.enemy_controller is None or self._level_ended:
            return
        if self.grenade_count <= 0:
            self._booster_unavailable("grenade")
            return
        self.grenade_count -= 1
        self._apply_grenade_effect(1)
```

- [ ] **Step 6: Auto-activate scaled effects in `_on_apply_gate`**

In `_on_apply_gate`, replace the five reward branches (lines 2322-2336) with:
```python
        elif gate.op == gates.OP_GRENADE:
            self._apply_grenade_effect(int(gate.value))
        elif gate.op == gates.OP_REINFORCE:
            self._apply_reinforce_effect(int(gate.value))
        elif gate.op == gates.OP_FREEZE:
            self._apply_freeze_effect(int(gate.value))
        elif gate.op == gates.OP_OVERDRIVE:
            self._apply_overdrive_effect(int(gate.value))
        elif gate.op == gates.OP_MAGNET:
            self._apply_magnet_effect(int(gate.value))
```

- [ ] **Step 7: Unit tests + boot smoke + structural check**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all PASS.

Structural check (the effect methods exist and the gate routes to them):
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "
import game
for m in ('_apply_grenade_effect','_apply_reinforce_effect','_apply_freeze_effect','_apply_overdrive_effect','_apply_magnet_effect'):
    assert hasattr(game.GameScreen, m), m
import inspect
src = inspect.getsource(game.GameScreen._on_apply_gate)
assert '_apply_grenade_effect' in src and '_apply_freeze_effect' in src
assert 'grenade_count +' not in src and 'freeze_count +' not in src   # no banking
print('structural OK')
"
```
Expected: prints `structural OK`.

Boot smoke:
```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_rg2.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_rg2.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 8: Commit**
```bash
git add game.py
git commit -m "feat: reward gates auto-activate scaled booster effects, no banking (#14)"
```

---

### Task 4: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run every suite**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_reward_boosters.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_gate_emphasis.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py \
 && venv/bin/python test_weapon_range.py \
 && venv/bin/python test_aim.py
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual play checks (reviewer, needs a display)**

Verify and report honestly:
1. **Auto-activation:** passing a reward gate immediately triggers the effect — grenade blast, +N·8 squad, freeze/overdrive/magnet turn on — with no charge added to the HUD button.
2. **Counter / refresh:** a timed booster's icon shows its countdown and the manual button is blocked while active; passing another gate of the same type while active refreshes (never shortens).
3. **×N label:** reward gates show the booster NAME with "×N" on a line below, scaling without wrapping (the emphasis pop scales both lines).
4. **Shop charges unchanged:** shop-bought boosters still bank and fire via the buttons.
5. **Scaling reads:** ×2/×3 gates are visibly stronger (bigger blast / longer freeze / more squad).

- [ ] **Step 4: Note any gaps**

Per CLAUDE.md, confirm each auto-activation has its sfx + visual (they reuse the existing activation juice). Note that instant boosters (grenade/reinforce) intentionally have no countdown (nothing to stay active).

---

## Self-review notes (author)

- **Spec coverage:** #14 auto-activate-not-bank → Task 3 (effect/handler split + `_on_apply_gate` routing; structural check asserts no `*_count +=` banking remains). Refresh-not-rob → Task 1 (`refreshed_until`) used by the timed effects in Task 3. Counter-while-active → existing `_sync_booster_btn` (unchanged) driven by the same `*_active_until` timers. #15 ×N + two-line label → Task 2 (spawner `_bonus_value` + canonical `"NAME xN"`; `Gate` two-line name/factor). ×N scaling → Task 3 (reinforce ·N, grenade radius/damage ·N, timed duration ·N). Shop unchanged / no state.py change → confirmed (gates no longer touch balances; handlers still spend shop charges).
- **Type/name consistency:** `boosters.refreshed_until(current, now, base, scale)`; `GateSpawner._bonus_value(op)`; `Gate._name_label`/`_factor_label`; `GameScreen._apply_{grenade,reinforce,freeze,overdrive,magnet}_effect(scale)` + the same-named `_activate_*`/`_detonate_grenade` handlers; `gates.CONSUMABLE_BONUS`, `OP_ACCENT_RGBA`, `_OUTLINE_RGBA` (existing). Consistent across tasks.
- **Testability:** timer math (Task 1) and ×N + label (Task 2, GateSpawner needs no atlas — pass `controller=None`; Gate widget builds under SDL dummy) are unit-tested; the GameScreen effect wiring (Task 3) is verified by the structural check + boot smoke + manual play, since instantiating GameScreen headlessly is impractical.
- **Ordering:** Task 1 (helper) precedes Task 3 (uses it); Task 2 (gate ×N/label) is independent; Task 3 routes gate.value (set in Task 2) to the scaled effects.
