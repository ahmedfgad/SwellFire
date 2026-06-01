# Quick Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prettify the manual-aim line into a fading laser beam (#1), and size boss-spawned minions to match normal enemies (#4).

**Architecture:** Extract the HP→size factor into a shared `entities.hp_size_factor(hp)` used by both enemy spawners and (newly) the boss minions, fixing the boss minions' hardcoded small size. Replace `AimReticle`'s single flat line with a 5-segment beam whose alpha fades toward the reticle.

**Tech Stack:** Python 3, Kivy 2.3. Pure helper is unit-tested; the beam is headless-smoke-tested (fade direction asserted); boss-minion size is verified via the shared helper test + boot.

---

### Task 1: `entities.hp_size_factor` (shared, DRY)

**Files:**
- Modify: `entities.py` — add `hp_size_factor`; replace the two inline factors (line 303 in `EnemySpawner._spawn_one`, line 417 in `FormationSpawner._spawn_rank`)
- Test: `test_hp_size_factor.py`

- [ ] **Step 1: Write the failing test** — create `test_hp_size_factor.py`:

```python
"""test_hp_size_factor.py — HP-based enemy size factor.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_hp_size_factor.py"""
import entities


def test_one_hp_is_no_growth():
    assert entities.hp_size_factor(1) == 1.0


def test_scales_with_hp():
    assert abs(entities.hp_size_factor(4) - 1.36) < 1e-9   # 1 + 0.12*3


def test_caps_at_1_6():
    assert entities.hp_size_factor(50) == 1.6
    assert entities.hp_size_factor(8) == min(1.6, 1.0 + 0.12 * 7)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL HP SIZE FACTOR TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_hp_size_factor.py`
Expected: FAIL — `AttributeError: module 'entities' has no attribute 'hp_size_factor'`.

- [ ] **Step 3: Add the helper**

In `entities.py`, add this near the top (after the imports / `ARCHETYPES`, module level):
```python
def hp_size_factor(hp: int) -> float:
    """Sprite-size multiplier for a tougher enemy: bigger HP reads bigger,
    capped so even a tank stays imposing rather than absurd. Shared by the
    enemy spawners and the boss minions so sizing is consistent everywhere."""
    return min(1.6, 1.0 + 0.12 * (int(hp) - 1))
```

Then replace the inline factor at **line 303** (`EnemySpawner._spawn_one`):
```python
        size *= min(1.6, 1.0 + 0.12 * (hp - 1))
```
with:
```python
        size *= hp_size_factor(hp)
```

And at **line 417** (`FormationSpawner._spawn_rank`):
```python
            size = graphics.ws(float(arch["size"])) * min(1.6, 1.0 + 0.12 * (hp - 1))
```
with:
```python
            size = graphics.ws(float(arch["size"])) * hp_size_factor(hp)
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_hp_size_factor.py`
Expected: PASS — `ALL HP SIZE FACTOR TESTS PASSED`.

- [ ] **Step 5: Regression — formation spawner unchanged**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_spawner_balance.py && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py`
Expected: both print their PASS lines (the factor is identical, just relocated — the tougher-enemy-is-bigger tests must still hold).

- [ ] **Step 6: Commit**
```bash
git add entities.py test_hp_size_factor.py
git commit -m "refactor: extract entities.hp_size_factor (shared by spawners)"
```

---

### Task 2: Boss minions sized like normal enemies (#4)

**Files:**
- Modify: `boss.py` — `_volley` (line 190), `_stream_one` (line 219)

Both methods already do `import entities as ent` locally, so `ent.ARCHETYPES` / `ent.TYPE_GRUNT` / `ent.hp_size_factor` are available.

- [ ] **Step 1: Fix the grunt-minion size in `_volley`**

In `boss.py` `_volley`, change (line 190):
```python
        minion_sz = graphics.ws(44.0)
```
to:
```python
        minion_sz = (graphics.ws(float(ent.ARCHETYPES[ent.TYPE_GRUNT]["size"]))
                     * ent.hp_size_factor(self.minion_hp))
```
(The phase-2 tank minion below already uses the proper tank archetype size — leave it. The minions keep their `"enemy_red"` frame.)

- [ ] **Step 2: Fix the grunt-minion size in `_stream_one`**

In `boss.py` `_stream_one`, change (line 219):
```python
        minion_sz = graphics.ws(44.0)
```
to:
```python
        minion_sz = (graphics.ws(float(ent.ARCHETYPES[ent.TYPE_GRUNT]["size"]))
                     * ent.hp_size_factor(self.minion_hp))
```

- [ ] **Step 3: Structural + boot smoke**

Confirm no `ws(44.0)` minion size remains and boss imports cleanly:
```bash
grep -n "ws(44.0)" boss.py || echo "no hardcoded 44 minion size remaining"
SDL_AUDIODRIVER=dummy venv/bin/python -c "import boss, entities; print('boss imports OK')"
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_boss.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_boss.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: the grep prints "no hardcoded 44 minion size remaining" (or nothing matched); `boss imports OK`; boot `exit=124`, no traceback.

- [ ] **Step 4: Commit**
```bash
git add boss.py
git commit -m "fix: boss minions sized like normal grunts (grunt size x hp_size_factor) (#4)"
```

---

### Task 3: `AimReticle` fading beam (#1)

**Files:**
- Modify: `graphics.py` — `AimReticle.__init__` / `set_endpoints` / `set_locked` (lines 861-893)
- Test: `test_aim_beam.py`

- [ ] **Step 1: Write the failing test** — create `test_aim_beam.py`:

```python
"""test_aim_beam.py — the aim line is a fading multi-segment beam.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_aim_beam.py"""
import graphics


def test_beam_has_segments_and_fades_toward_reticle():
    r = graphics.AimReticle()
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    assert len(r._segs) == graphics.AimReticle.SEGMENTS == 5
    a_squad = r._seg_colors[0].rgba[3]
    a_reticle = r._seg_colors[-1].rgba[3]
    assert a_squad > a_reticle   # brightest at the squad, fades to the reticle


def test_lock_turns_beam_red():
    r = graphics.AimReticle()
    r.set_locked(True)
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    # red hue: red channel high, blue channel low on the (visible) squad segment
    rr, gg, bb, aa = r._seg_colors[0].rgba
    assert rr > 0.9 and bb < 0.5
    r.set_locked(False)
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    assert r._seg_colors[0].rgba[2] > 0.8   # back to cyan (blue high)


def test_show_hide_run():
    r = graphics.AimReticle()
    r.set_endpoints(0.0, 0.0, 0.0, 300.0)
    r.show()
    r.hide()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AIM BEAM TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_aim_beam.py`
Expected: FAIL — `AttributeError: 'AimReticle' object has no attribute '_segs'` (or `SEGMENTS`).

- [ ] **Step 3: Replace the single line with a segmented beam**

In `graphics.py` `AimReticle`, add a class attribute next to `R` (line 859):
```python
    SEGMENTS = 5
    BEAM_ALPHA = 0.45   # brightest (squad-end) segment alpha
```

In `__init__`, replace the single-line creation (lines 867-868):
```python
            self._line_color = Color(0.55, 0.88, 1.0, 0.30)
            self._line = Line(width=1.6)
```
with a segment list (brightest, widest at the squad end; thinner toward the reticle):
```python
            self._seg_colors = []
            self._segs = []
            n = self.SEGMENTS
            for i in range(n):
                self._seg_colors.append(Color(0.55, 0.88, 1.0, 0.0))
                # width tapers ~2.0 (squad) -> ~1.0 (reticle)
                w = 2.0 - 1.0 * (i / (n - 1))
                self._segs.append(Line(width=max(1.0, w)))
```
Then add an instance field at the end of `__init__` (after `self._sx = ...`):
```python
        self._base_rgb = (0.55, 0.88, 1.0)   # cyan; set red while locked
```

- [ ] **Step 4: Recompute segment points + fade in `set_endpoints`**

Replace `set_endpoints` (lines 876-880) with:
```python
    def set_endpoints(self, sx, sy, rx, ry):
        self._sx, self._sy, self._rx, self._ry = sx, sy, rx, ry
        n = self.SEGMENTS
        r, g, b = self._base_rgb
        for i in range(n):
            t0 = i / n
            t1 = (i + 1) / n
            x0 = sx + (rx - sx) * t0
            y0 = sy + (ry - sy) * t0
            x1 = sx + (rx - sx) * t1
            y1 = sy + (ry - sy) * t1
            self._segs[i].points = [x0, y0, x1, y1]
            # Alpha fades from BEAM_ALPHA at the squad end toward ~0 at the reticle.
            self._seg_colors[i].rgba = (r, g, b, self.BEAM_ALPHA * (1.0 - i / n))
        self._ring.circle = (rx, ry, self._r)
        self._dot.circle = (rx, ry, self._r * 0.28)
```

- [ ] **Step 5: Update `set_locked` to swap the beam hue**

Replace `set_locked` (lines 882-893) with:
```python
    def set_locked(self, locked: bool):
        if locked == self._locked:
            return
        self._locked = locked
        if locked:
            self._ring_color.rgba = (1.0, 0.35, 0.30, 1.0)
            self._ring.width = 3.0
            self._base_rgb = (1.0, 0.40, 0.35)
        else:
            self._ring_color.rgba = (0.55, 0.88, 1.0, 0.95)
            self._ring.width = 2.2
            self._base_rgb = (0.55, 0.88, 1.0)
        # Beam hue is re-applied from _base_rgb on the next set_endpoints (called
        # every frame), so segments pick up the new color with their fade intact.
```

- [ ] **Step 6: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_aim_beam.py`
Expected: PASS — `ALL AIM BEAM TESTS PASSED`.

- [ ] **Step 7: Boot smoke**

```bash
SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py >/tmp/sf_beam.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_beam.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback. (game.py calls `set_endpoints`/`set_locked`/`show`/`hide` unchanged — the public interface is preserved.)

- [ ] **Step 8: Commit**
```bash
git add graphics.py test_aim_beam.py
git commit -m "feat: manual-aim line is a fading laser beam (#1)"
```

---

### Task 4: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the suites**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_hp_size_factor.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_aim_beam.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_spawner_balance.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py \
 && venv/bin/python test_aim.py
```
Expected: all PASS.

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual checks (reviewer, needs a display)**

1. **#1:** in manual aim, the squad→reticle line is a tapered beam, brightest near the squad and fading toward the reticle; it turns red when the reticle is locked on a target.
2. **#4:** on a boss level (try W2 and one other world), the boss's spawned minions are the **same size** as normal grunts (no longer tiny); a tougher minion (higher boss-minion HP in late worlds) reads a bit bigger.

---

## Self-review notes (author)

- **Spec coverage:** #1 fading beam → Task 3 (5 segments, alpha fade, red on lock; public interface `set_endpoints`/`set_locked`/`show`/`hide` preserved so game.py is untouched). #4 boss-minion size → Task 1 (`hp_size_factor`) + Task 2 (boss `_volley` + `_stream_one` use grunt size × factor; tank minion already correct; red frame kept). DRY refactor of the inline factor → Task 1 (both entities sites). 
- **Type/name consistency:** `entities.hp_size_factor(hp)` used in entities (×2 sites) + boss (×2 sites); `AimReticle.SEGMENTS`/`BEAM_ALPHA`/`_segs`/`_seg_colors`/`_base_rgb`; `set_endpoints`/`set_locked`/`show`/`hide` signatures unchanged.
- **Testability:** `hp_size_factor` pure unit test; beam headless smoke (fade-direction + lock-hue assertions); boss-minion size via the helper test + boot (boss spawning isn't headless-instantiable). Formation regression run to confirm the refactor is behavior-preserving.
- **Ordering:** Task 1 (helper) precedes Task 2 (boss uses it). Task 3 (beam) is independent.
