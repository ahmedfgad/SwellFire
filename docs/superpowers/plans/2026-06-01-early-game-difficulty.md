# Early-Game Difficulty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make World 1 beatable by a fresh, un-upgraded player — bigger starting squad, softer early density, stronger growth multipliers, and a guaranteed growth gate at the start of every level.

**Architecture:** Tuning in `levels.py` (non-boss `starting_squad` = 4+world; lower the low-end of the three density lerps) and `gates.py` (MUL pool gains ×3; the opening gate pair of each level reuses the existing `force_safe` gain-pair path via a per-level pair counter).

**Tech Stack:** Python 3, Kivy 2.3. Values are tunable; tests assert the W1 numbers + the ×3 availability + the first-pair-gain invariant (with fakes, headless).

---

### Task 1: levels.py — starting squad + softer W1 density

**Files:**
- Modify: `levels.py` — density lerps (lines 184-186), non-boss `starting_squad` (line 285 + comment 279-284)
- Test: `test_early_game_levels.py`

- [ ] **Step 1: Write the failing test** — create `test_early_game_levels.py`:

```python
"""test_early_game_levels.py — W1 onboarding tuning.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_levels.py"""
import levels


def test_w1_starting_squad_is_5():
    assert levels.get_level(1)["starting_squad"] == 5      # W1-L1, non-boss


def test_starting_squad_grows_by_world():
    assert levels.get_level(11)["starting_squad"] == 6     # W2-L1
    assert levels.get_level(51)["starting_squad"] == 10    # W6-L1


def test_w1_density_softened():
    c = levels.get_level(1)
    assert c["formation_columns"] == 5                     # was 6
    assert abs(c["rank_interval_start"] - 260.0) < 1e-6    # was 220
    assert abs(c["rank_interval_end"] - 140.0) < 1e-6      # was 120


def test_late_density_unchanged():
    c = levels.get_level(60)                                # W6 last, t=1
    assert c["formation_columns"] == 9
    assert abs(c["rank_interval_start"] - 120.0) < 1e-6
    assert abs(c["rank_interval_end"] - 60.0) < 1e-6


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL EARLY GAME LEVELS TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_levels.py`
Expected: FAIL — `test_w1_starting_squad_is_5` (currently 1) and the density asserts.

- [ ] **Step 3: Soften the density lerps**

In `levels.py`, change lines 184-186 from:
```python
            formation_columns = int(round(_lerp(6.0, 9.0, t)))
            rank_interval_start = _lerp(220.0, 120.0, t)
            rank_interval_end = _lerp(120.0, 60.0, t)
```
to:
```python
            formation_columns = int(round(_lerp(5.0, 9.0, t)))
            rank_interval_start = _lerp(260.0, 120.0, t)
            rank_interval_end = _lerp(140.0, 60.0, t)
```

- [ ] **Step 4: Bump the non-boss starting squad**

In `levels.py`, change the non-boss `starting_squad` (line 285) from:
```python
                starting_squad = world
```
to:
```python
                starting_squad = 4 + world
```
And update the now-stale comment just above it (lines 279-284) so it reads, e.g.:
```python
                # Non-boss starting squad = 4 + world: W1=5, W2=6, ... W6=10.
                # A squad of 5 gives a brand-new player enough muzzles to clear
                # the front rank and reach the first gates (W1 used to start at 1
                # and die before gate 2). The sub-linear fire cap (22) means the
                # higher-world bumps mostly absorb attrition rather than add
                # firepower. The persistent shop squad_bonus stacks on top.
```

- [ ] **Step 5: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_levels.py`
Expected: PASS — `ALL EARLY GAME LEVELS TESTS PASSED`.

- [ ] **Step 6: Regression**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_balance.py && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py`
Expected: all PASS. (`test_levels_formation` asserts end<start and later-worlds-denser — still true: W1 start 260 > end 140; late cols 9 ≥ early 5; late end 60 ≤ early 140.)

- [ ] **Step 7: Commit**
```bash
git add levels.py test_early_game_levels.py
git commit -m "balance: W1 starts squad 5 (4+world) + softer early density (#2)"
```

---

### Task 2: gates.py — ×3 multiplier + first-pair gain bias

**Files:**
- Modify: `gates.py` — MUL pool (`_pick_op` op_table, ~line 511); `GateSpawner.__init__` (~line 397), `reset_per_level` (lines 400-404), `tick` `force_safe` (line 436) + a pair counter
- Test: `test_early_game_gates.py`

- [ ] **Step 1: Write the failing test** — create `test_early_game_gates.py`:

```python
"""test_early_game_gates.py — x3 multiplier + first-pair-gain bias.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py"""
import gates


def test_mul_pool_includes_3():
    sp = gates.GateSpawner(controller=None, seed=1)
    sp.world_tier = 1
    vals = set()
    for _ in range(300):
        op, value, label = sp._pick_op(exclude_op=None, allowed=["mul"])
        vals.add(value)
    assert vals == {2, 3}   # MUL can now be x2 or x3


class _RecCtrl:
    def __init__(self):
        self.pairs = []
    def spawn_pair(self, a, b):
        self.pairs.append((a, b))


def _first_pair_ops(seed):
    sp = gates.GateSpawner(controller=_RecCtrl(), seed=seed)
    sp.allowed_ops = ["mul", "add", "sub", "div"]
    sp.interval_px = 100.0
    sp.reset_per_level()
    sp.tick(10_000.0, 0.0, 400.0, 1000.0)   # well past _next_distance → spawns
    a, b = sp.controller.pairs[-1]
    return {a[4], b[4]}                       # index 4 = op in the spawn tuple


def test_first_pair_offers_a_gain_across_seeds():
    gains = {gates.OP_MUL, gates.OP_ADD}
    for seed in range(30):
        assert _first_pair_ops(seed) & gains, seed   # always a gain in the opener


def test_pair_counter_advances():
    sp = gates.GateSpawner(controller=_RecCtrl(), seed=1)
    sp.allowed_ops = ["mul", "add", "sub", "div"]
    sp.interval_px = 100.0
    sp.reset_per_level()
    assert sp._pairs_spawned == 0
    sp.tick(10_000.0, 0.0, 400.0, 1000.0)
    assert sp._pairs_spawned == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL EARLY GAME GATES TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py`
Expected: FAIL — `test_mul_pool_includes_3` (currently `{2}`) and/or `_pairs_spawned` attribute missing.

- [ ] **Step 3: Add ×3 to the MUL pool**

In `gates.py` `_pick_op`, change the MUL op_table entry (~line 511) from:
```python
            OP_MUL:     ([2],              lambda v: "x{}".format(v)),
```
to:
```python
            OP_MUL:     ([2, 3],           lambda v: "x{}".format(v)),
```

- [ ] **Step 4: Add the per-level pair counter**

In `gates.py` `GateSpawner.__init__`, near `self.grenade_gates_spawned = 0` (line 398), add:
```python
        self._pairs_spawned = 0   # pairs emitted this level (first-pair gain bias)
```
In `reset_per_level` (lines 400-404), add to the resets:
```python
        self._pairs_spawned = 0
```

- [ ] **Step 5: Bias the first pair to a gain + count pairs**

In `gates.py` `tick`, change the `force_safe` line (436) from:
```python
        force_safe = self.consecutive_misses >= self.PITY_AFTER_MISSES
```
to (the opening pair of every level also forces a gain pair):
```python
        force_safe = (self.consecutive_misses >= self.PITY_AFTER_MISSES
                      or self._pairs_spawned == 0)
```
Then, right after the `self.controller.spawn_pair(...)` call (after line 455, before `return True`), add:
```python
        self._pairs_spawned += 1
```

- [ ] **Step 6: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py`
Expected: PASS — `ALL EARLY GAME GATES TESTS PASSED`.

- [ ] **Step 7: Regression + boot smoke**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_gate_emphasis.py
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_eg.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_eg.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: both suites PASS; boot `exit=124`, no traceback.

- [ ] **Step 8: Commit**
```bash
git add gates.py test_early_game_gates.py
git commit -m "balance: MUL x3 available + first gate pair guarantees a gain (#2)"
```

---

### Task 3: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the suites**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_levels.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_balance.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual checks (reviewer, needs a display)**

Verify and report honestly:
1. A **fresh save** (reset progress) can clear **W1-L1 → W1-L10** — including the old L8 trap — **without buying any upgrades**. Squad starts at 5.
2. The **opening gate** of each level always offers a growth option (×2/×3 or +N), never a shrink-only opener.
3. W1 reads as fair onboarding (not a walkover, not a wall); W2–W3 still ramp up noticeably.

- [ ] **Step 4: Note**

These are tuning values; record that the full beatable-with-available-power re-tune (the W4 wall) is sub-project **C** next.

---

## Self-review notes (author)

- **Spec coverage:** (1) starting squad 4+world → Task 1 step 4. (2) softer W1 density → Task 1 step 3 (low-end lerp endpoints lowered, high-end kept — `test_late_density_unchanged` guards the late game). (3) MUL ×3 → Task 2 step 3. (4) first-pair gain bias → Task 2 steps 4-5 (reuses the existing `force_safe` gain-pair path via `_pairs_spawned`). 
- **Type/name consistency:** `levels` cfg keys `starting_squad`/`formation_columns`/`rank_interval_start`/`rank_interval_end` (existing); `GateSpawner._pairs_spawned`; `_pick_op` op_table MUL `[2,3]`; `force_safe` reuse. The first-pair spawn tuple is `(x, y, w, h, op, value, label)` so op is index 4 (matches `spawn_pair` args at gates.py:452-455).
- **Testability:** levels values are pure cfg reads; the gate ×3 and first-pair bias use a fake recording controller + seeded RNG (no atlas/widgets), headless under SDL dummy. Formation/balance regressions guard that the late-game density and the formation invariants still hold.
- **Ordering:** Tasks 1 and 2 are independent; either order works. Task 3 verifies both.
