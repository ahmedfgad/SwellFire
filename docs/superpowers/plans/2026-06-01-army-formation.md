# Army-Formation Combat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace free-roaming chase enemies on normal levels with an army that marches straight down the lane in a grid of ranks, engaged inside a per-weapon kill-zone shown by a visible range line, with continuous rising difficulty.

**Architecture:** A new `FormationSpawner` (entities.py) spawns enemies as distance-cadence ranks across fixed columns with `chase=0` (straight-down). Enemies' existing `update()` already moves straight down when chase is 0 — no movement-code change. A per-weapon `range_frac` (weapons.py) defines the kill-zone; `game.py` computes `weapon_range_px`, draws a `RangeLine` (graphics.py) at it, gates auto-aim (via the existing `find_nearest_threat` band) and despawns projectiles at the line (`ProjectileController.kill_line_y`). Boss levels bypass all of this (unlimited range; boss must stay hittable).

**Tech Stack:** Python 3, Kivy 2.3. Density via `graphics.ws()`. Tests headless under `SDL_AUDIODRIVER=dummy`; fakes used for pools/controllers.

**Supersedes:** the #16 varied-Y spawn + appearance poof (enemies now enter from the top in formation).

---

### Task 1: Per-weapon `range_frac`

**Files:**
- Modify: `weapons.py` — `Weapon` dataclass (lines 17-28) + `WEAPONS` (34-57)
- Test: `test_weapon_range.py`

- [ ] **Step 1: Write the failing test** — create `test_weapon_range.py`:

```python
"""test_weapon_range.py — per-weapon kill-zone fraction.
Run: venv/bin/python test_weapon_range.py  (pure)"""
import weapons


def test_every_weapon_has_a_range_frac():
    for wid in ("pistol", "rifle", "shotgun", "sniper"):
        rf = weapons.get(wid).range_frac
        assert 0.0 < rf <= 0.6, (wid, rf)


def test_range_frac_ordering_matches_niches():
    rf = lambda w: weapons.get(w).range_frac
    assert rf("sniper") > rf("rifle") >= rf("pistol") > rf("shotgun")
    assert rf("sniper") <= 0.5   # capped below the top of the lane


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL WEAPON RANGE TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python test_weapon_range.py`
Expected: FAIL — `AttributeError: 'Weapon' object has no attribute 'range_frac'`.

- [ ] **Step 3: Add the field and values**

In `weapons.py`, add a field to the `Weapon` dataclass (after `frame: str`, line 28):
```python
    range_frac: float = 0.33  # kill-zone reach as a fraction of the play field
```
Then set it per weapon in `WEAPONS` (add `range_frac=...` to each entry):
- pistol: `range_frac=0.33`
- rifle: `range_frac=0.33`
- shotgun: `range_frac=0.25`
- sniper: `range_frac=0.50`

For example the rifle entry becomes:
```python
    "rifle": Weapon(
        id="rifle",   name="Rifle",
        fire_rate=7.0, damage=1, projectiles_per_shot=1,
        spread_deg=4.0, projectile_speed=980.0, projectile_size=12.0,
        ttl=0.70, frame="projectile", range_frac=0.33,
    ),
```
Do the same for pistol (0.33), shotgun (0.25), sniper (0.50).

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python test_weapon_range.py`
Expected: PASS — `ALL WEAPON RANGE TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add weapons.py test_weapon_range.py
git commit -m "feat: per-weapon range_frac for the kill-zone"
```

---

### Task 2: `RangeLine` widget

**Files:**
- Modify: `graphics.py` — add class after `AimReticle` (~line 910)

- [ ] **Step 1: Add the widget**

First, ensure `from kivy.properties import NumericProperty` is imported at the top of `graphics.py` (the gate's `emph_scale` work added it project-wide, but it's in `gates.py`; check `graphics.py`'s imports and add it if absent). Then, after the `AimReticle` class ends (before `class ParticleBurst`), add:

```python
class RangeLine(Widget):
    """A horizontal 'engagement line' drawn across the lane at the current
    weapon's max reach. Its Y tweens (via the `line_y` NumericProperty) when the
    weapon — hence range — changes, so the player can read how far their shots
    reach. Drawn in ``canvas`` like the other HUD auras.

    Animating a Kivy NumericProperty (not a plain attribute) is what lets
    `Animation(line_y=...)` work — mirrors the gate `emph_scale` pattern.
    """

    line_y = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0.0
        with self.canvas:
            self._glow_color = Color(1.0, 0.85, 0.30, 0.18)
            self._glow = Line(width=6.0)
            self._line_color = Color(1.0, 0.88, 0.40, 0.85)
            self._line = Line(width=2.0)
        self._x1 = 0.0
        self._x2 = 0.0
        self._anim = None
        self.bind(line_y=lambda *_: self._redraw())

    def _redraw(self):
        y = self.line_y
        self._glow.points = [self._x1, y, self._x2, y]
        self._line.points = [self._x1, y, self._x2, y]

    def set_line(self, x1, x2, y, animate=True):
        self._x1, self._x2 = x1, x2
        if animate and self.opacity > 0.0 and y != self.line_y:
            if self._anim is not None:
                self._anim.cancel(self)
            self._anim = Animation(line_y=y, duration=0.18, t="out_quad")
            self._anim.start(self)
        else:
            self.line_y = y
            self._redraw()   # ensure redraw even if the value didn't change

    def show(self):
        self.opacity = 1.0

    def hide(self):
        self.opacity = 0.0
```

- [ ] **Step 2: Smoke-check**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "import graphics; r=graphics.RangeLine(); r.set_line(0,400,300,animate=False); r.show(); r.hide(); print('RangeLine OK')"
```
Expected: prints `RangeLine OK` (no exception). `Color`, `Line`, `Animation`, `Widget` are already imported in graphics.py; add only `NumericProperty` if missing (the smoke check will surface a NameError if so).

- [ ] **Step 3: Commit**
```bash
git add graphics.py
git commit -m "feat: RangeLine widget (weapon kill-zone indicator)"
```

---

### Task 3: `FormationSpawner`

**Files:**
- Modify: `entities.py` — add class after `EnemySpawner` (~line 312)
- Test: `test_formation_spawner.py`

- [ ] **Step 1: Write the failing test** — create `test_formation_spawner.py`:

```python
"""test_formation_spawner.py — rank/column formation spawning.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py"""
import entities


class _FakeCtrl:
    def __init__(self):
        self.calls = []
    def spawn(self, x, y, w, h, frame, hp, speed, chase, enemy_type):
        self.calls.append(dict(x=x, y=y, w=w, h=h, frame=frame, hp=hp,
                               speed=speed, chase=chase, enemy_type=enemy_type))
        return len(self.calls) - 1


def _fs(seed=1):
    ctrl = _FakeCtrl()
    fs = entities.FormationSpawner(ctrl, seed=seed)
    fs.columns = 5
    fs.rank_interval_px = 100.0
    fs.enemy_hp = 2
    fs.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
    fs.reset_per_level(0.0)
    return fs, ctrl


def test_no_rank_before_interval():
    fs, ctrl = _fs()
    fs.update(50.0, 0.0, 0.0, 400.0, 1000.0)
    assert ctrl.calls == []


def test_one_rank_per_interval_crossed():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    assert len(ctrl.calls) == 5            # one rank = 5 columns
    fs.update(320.0, 0.0, 0.0, 400.0, 1000.0)
    assert len(ctrl.calls) == 15           # +2 ranks (200, 300)


def test_enemies_have_no_chase_and_spawn_at_top():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    ys = {c["y"] for c in ctrl.calls}
    assert all(c["chase"] == 0.0 for c in ctrl.calls)
    assert len(ys) == 1 and next(iter(ys)) > 1000.0   # one rank, above top edge


def test_columns_are_distinct_and_in_bounds():
    fs, ctrl = _fs()
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    xs = sorted(c["x"] for c in ctrl.calls)
    assert len(set(xs)) == 5
    assert xs[0] > 0.0 and xs[-1] < 400.0


def test_hp_uses_curve_and_scale():
    fs, ctrl = _fs()
    fs.hp_scale = 1.0
    fs.update(100.0, 0.0, 0.0, 400.0, 1000.0)
    assert ctrl.calls[0]["hp"] == 2        # grunt hp_mult 1.0 * enemy_hp 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL FORMATION SPAWNER TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py`
Expected: FAIL — `AttributeError: module 'entities' has no attribute 'FormationSpawner'`.

- [ ] **Step 3: Implement `FormationSpawner`**

In `entities.py`, immediately after the `EnemySpawner` class ends (before `# --- projectile controller ---`, ~line 313), add:

```python
class FormationSpawner:
    """Spawns enemies as ranks (rows) marching straight down a column grid.

    Distance-driven: a new rank spawns each time the world has scrolled
    ``rank_interval_px`` further, so ranks stay evenly spaced into a grid
    regardless of frame rate (mirrors the gate spawner's distance cadence).
    Enemies spawn at the top edge with ``chase=0`` — they descend straight
    down and never steer toward the hero. Archetype mix and HP mirror
    EnemySpawner (per-world ``spawn_table`` + ``enemy_hp`` * ``hp_scale``);
    tougher types render bigger via the same HP-size factor.
    """

    EDGE = 40.0          # world-px inset from each rail
    SPAWN_ABOVE_TOP = 30.0

    def __init__(self, controller: "EnemyController", seed: int | None = None):
        self.controller = controller
        self._rng = random.Random(seed)
        self.columns = 6
        self.rank_interval_px = 160.0
        self.enemy_speed = 220.0
        self.enemy_hp = 1
        self.hp_scale = 1.0
        self.spawn_table: list[tuple[int, float]] = [(TYPE_GRUNT, 1.0)]
        self._last_spawn_distance = 0.0

    def reset_per_level(self, distance: float) -> None:
        self._last_spawn_distance = distance

    def update(self, distance: float, x_min: float, y_min: float,
               x_max: float, y_max: float) -> int:
        """Spawn one rank for each ``rank_interval_px`` crossed since the last.
        Returns the number of ranks spawned this call."""
        if self.rank_interval_px <= 0.0:
            return 0
        ranks = 0
        while distance - self._last_spawn_distance >= self.rank_interval_px:
            self._last_spawn_distance += self.rank_interval_px
            self._spawn_rank(x_min, y_min, x_max, y_max)
            ranks += 1
        return ranks

    def _column_xs(self, x_min: float, x_max: float, size: float) -> list[float]:
        edge = graphics.ws(self.EDGE)
        lo = x_min + size * 0.5 + edge
        hi = x_max - size * 0.5 - edge
        n = max(1, int(self.columns))
        if n == 1:
            return [(lo + hi) * 0.5]
        step = (hi - lo) / (n - 1)
        return [lo + i * step for i in range(n)]

    def _pick_type(self) -> int:
        total = sum(w for _, w in self.spawn_table) or 1.0
        r = self._rng.uniform(0.0, total)
        cum = 0.0
        for t, w in self.spawn_table:
            cum += w
            if r <= cum:
                return t
        return self.spawn_table[-1][0] if self.spawn_table else TYPE_GRUNT

    def _spawn_rank(self, x_min: float, y_min: float,
                    x_max: float, y_max: float) -> None:
        spawn_y = y_max + graphics.ws(self.SPAWN_ABOVE_TOP)
        base_size = graphics.ws(float(ARCHETYPES[TYPE_GRUNT]["size"]))
        for cx in self._column_xs(x_min, x_max, base_size):
            enemy_type = self._pick_type()
            arch = ARCHETYPES[enemy_type]
            hp = max(1, int(round(self.enemy_hp * arch["hp_mult"] * self.hp_scale)))
            size = graphics.ws(float(arch["size"])) * min(1.6, 1.0 + 0.12 * (hp - 1))
            speed = graphics.ws(self.enemy_speed) * arch["speed_mult"]
            self.controller.spawn(
                cx, spawn_y, size, size, arch["frame"],
                hp=hp, speed=speed, chase=0.0, enemy_type=enemy_type,
            )
```

> `random`, `graphics`, `ARCHETYPES`, `TYPE_GRUNT` are already imported/defined at the top of `entities.py`.

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py`
Expected: PASS — `ALL FORMATION SPAWNER TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add entities.py test_formation_spawner.py
git commit -m "feat: FormationSpawner — distance-cadence ranks, straight-down (no chase)"
```

---

### Task 4: Projectile kill-line despawn

**Files:**
- Modify: `entities.py` — `ProjectileController.__init__` (~line 349) and `update` (~line 371-391)
- Test: `test_projectile_killline.py`

- [ ] **Step 1: Write the failing test** — create `test_projectile_killline.py`:

```python
"""test_projectile_killline.py — projectiles stop at the kill line.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_projectile_killline.py"""
import entities


class _FakePool:
    def __init__(self, n):
        self.capacity = n
        self.active = [True] * n
        self.cx = [0.0] * n
        self.cy = [0.0] * n
        self.vx = [0.0] * n
        self.vy = [0.0] * n
        self.released = []
    def release(self, i):
        self.active[i] = False
        self.released.append(i)


def _pc(cys):
    pool = _FakePool(len(cys))
    pc = entities.ProjectileController(pool)
    for i, cy in enumerate(cys):
        pool.cy[i] = cy
        pc.ttl[i] = 1.0           # alive (so ttl<=0 doesn't release)
    return pc, pool


def test_projectile_past_kill_line_is_released():
    pc, pool = _pc([600.0, 400.0])
    pc.kill_line_y = 500.0
    pc.update(0.0, -1e6, -1e6, 1e6, 1e6)   # dt=0, huge bounds
    assert not pool.active[0]               # 600 > 500 → released
    assert pool.active[1]                   # 400 < 500 → kept


def test_none_kill_line_keeps_everything():
    pc, pool = _pc([600.0, 400.0])
    pc.kill_line_y = None
    pc.update(0.0, -1e6, -1e6, 1e6, 1e6)
    assert pool.active[0] and pool.active[1]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PROJECTILE KILLLINE TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_projectile_killline.py`
Expected: FAIL — `AttributeError: 'ProjectileController' object has no attribute 'kill_line_y'` (or the released assertion fails).

- [ ] **Step 3: Implement**

In `entities.py` `ProjectileController.__init__`, after `self.recycled_total = 0` (line 358), add:
```python
        # When set (non-boss levels), projectiles that travel past this Y
        # (the weapon's kill-zone line) are released so shots visibly stop at
        # the line and can't reach the far army. None = unlimited (boss/MP).
        self.kill_line_y = None
```

In `ProjectileController.update`, change the expire condition (lines 387-389) from:
```python
            if (ttl[i] <= 0.0
                    or cx[i] < x_min - margin or cx[i] > x_max + margin
                    or cy[i] < y_min - margin or cy[i] > y_max + margin):
```
to:
```python
            if (ttl[i] <= 0.0
                    or (self.kill_line_y is not None and cy[i] > self.kill_line_y)
                    or cx[i] < x_min - margin or cx[i] > x_max + margin
                    or cy[i] < y_min - margin or cy[i] > y_max + margin):
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_projectile_killline.py`
Expected: PASS — `ALL PROJECTILE KILLLINE TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add entities.py test_projectile_killline.py
git commit -m "feat: projectile kill-line despawn for the kill-zone"
```

---

### Task 5: Formation params in levels.py

**Files:**
- Modify: `levels.py` — `build_levels` cfg dict (add keys near line 290-309)
- Test: `test_levels_formation.py`

- [ ] **Step 1: Write the failing test** — create `test_levels_formation.py`:

```python
"""test_levels_formation.py — per-level formation params.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py"""
import levels


def test_formation_keys_present():
    cfg = levels.get_level(1)
    for k in ("formation_columns", "rank_interval_start", "rank_interval_end"):
        assert k in cfg, k


def test_ranks_get_denser_toward_end_of_level():
    cfg = levels.get_level(1)
    # Smaller interval = denser. End interval < start interval.
    assert cfg["rank_interval_end"] < cfg["rank_interval_start"]


def test_later_worlds_are_denser_or_wider():
    early = levels.get_level(1)
    late = levels.get_level(55)   # W6
    assert (late["formation_columns"] >= early["formation_columns"]
            and late["rank_interval_end"] <= early["rank_interval_end"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL LEVELS FORMATION TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py`
Expected: FAIL — `KeyError`/`assert "formation_columns" in cfg`.

- [ ] **Step 3: Compute + add the params**

In `levels.py` `build_levels`, inside the per-level loop, after `enemy_chase_max = _lerp(...)` (line 174) add:
```python
            # Army-formation params. Columns widen and ranks tighten with the
            # global ramp `t`, so later worlds field a denser army; within a
            # level the spawner tightens the interval further (game.py ramps
            # start→end by distance progress).
            formation_columns = int(round(_lerp(5.0, 7.0, t)))
            rank_interval_start = _lerp(240.0, 150.0, t)
            rank_interval_end = _lerp(150.0, 90.0, t)
```
Then add them to the level cfg dict (in the `levels[index] = { ... }` literal, near line 300-309, alongside `"allowed_enemy_types": allowed_enemy_types,`):
```python
                "formation_columns": formation_columns,
                "rank_interval_start": rank_interval_start,
                "rank_interval_end": rank_interval_end,
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py`
Expected: PASS — `ALL LEVELS FORMATION TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add levels.py test_levels_formation.py
git commit -m "feat: per-level army-formation params (columns, rank interval)"
```

---

### Task 6: Wire the formation + kill-zone into game.py

**Files:**
- Modify: `game.py` — controller creation (~838-840), `__init__` state (~348), `_apply_level_config` (~1280-1347), `_update` spawn block (~1740-1782), reticle block (~1690-1703), fire-tick targeting (~1931-1938), projectile update (~2008), `_update_weapon_range` (new), range-line widget creation (~near hero/reticle creation), weapon-gate swap (~2260), layout/reset (~1216)

This is the integration task. Do the steps in order; run the smoke check at the end.

- [ ] **Step 1: `__init__` state + range-line + formation spawner fields**

In `GameScreen.__init__`, near the aim state (after `self.aim_reticle = None`, ~line 354), add:
```python
        self.range_line = None               # weapon kill-zone indicator
        self.formation_spawner = None        # army-formation rank spawner
        self._weapon_range_px = None         # None = unlimited (boss/MP)
        self._rank_interval_start = 200.0
        self._rank_interval_end = 120.0
```

- [ ] **Step 2: Create the formation spawner + range line where the enemy controller is built**

In `game.py`, right after `self.enemy_spawner = entities.EnemySpawner(self.enemy_controller, self._atlas)` (line 840), add:
```python
            self.formation_spawner = entities.FormationSpawner(self.enemy_controller)
```

Then where the `aim_reticle` widget is created and added to the stage (search for `self.aim_reticle = graphics.AimReticle(`), add right after it is added to the stage:
```python
        if self.range_line is None:
            self.range_line = graphics.RangeLine(size_hint=(None, None), size=(1, 1))
            self.stage.add_widget(self.range_line)
```

- [ ] **Step 3: Add `_update_weapon_range`**

In `game.py`, add this method to `GameScreen` (place it right after `_apply_level_config`):
```python
    def _update_weapon_range(self) -> None:
        """Recompute the kill-zone for the current weapon and push it to the
        projectile controller + range-line widget. Non-boss only; boss levels
        keep unlimited range so the squad can hit the far boss."""
        if self.stage is None or self.hero is None:
            return
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        hero_y = sy + sh * HERO_BOTTOM_FRAC
        field_h = (sy + sh) - hero_y
        is_boss = bool(self.level_config and self.level_config.get("boss"))
        if is_boss:
            self._weapon_range_px = None
        else:
            frac = weapons.get(self.current_weapon_id).range_frac
            self._weapon_range_px = frac * field_h
        kill_y = None if self._weapon_range_px is None else hero_y + self._weapon_range_px
        if self.projectile_controller is not None:
            self.projectile_controller.kill_line_y = kill_y
        if self.range_line is not None:
            if kill_y is None:
                self.range_line.hide()
            else:
                self.range_line.show()
                self.range_line.set_line(sx, sx + sw, kill_y)
```

- [ ] **Step 4: Configure the formation spawner in `_apply_level_config`**

In `_apply_level_config`, find the `hp_scale` block added in the balance pass (the `if self.enemy_spawner is not None:` block that sets `self.enemy_spawner.hp_scale = ...`). Right after it, add:
```python
        # Configure the army-formation spawner (non-boss spawn source).
        if self.formation_spawner is not None:
            fs = self.formation_spawner
            fs.columns = int(cfg.get("formation_columns", 6))
            self._rank_interval_start = cfg.get("rank_interval_start", 200.0)
            self._rank_interval_end = cfg.get("rank_interval_end", 120.0)
            fs.enemy_speed = cfg["enemy_speed"]
            fs.enemy_hp = cfg["enemy_hp"]
            fs.hp_scale = self.enemy_spawner.hp_scale if self.enemy_spawner else 1.0
            if cfg.get("boss"):
                fs.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
            else:
                fs.spawn_table = [
                    (entities.TYPE_NAMES[name], weight)
                    for name, weight in cfg["allowed_enemy_types"]
                ]
            fs.reset_per_level(self.distance)
        self._update_weapon_range()
```

- [ ] **Step 5: Replace the spawn block in `_update`**

In `_update`, replace the **entire** old spawn-rate block + the `enemy_spawner.tick(...)` call (the block from `base_interval = self.level_config["enemy_spawn_interval"]` through `self.enemy_spawner.tick(dt, x_min, y_min, x_max, y_max)`, lines ~1745-1771) with:
```python
            # Army formation: ranks spawn on a distance cadence, tightening
            # within the level (denser toward the end). Boss levels spawn no
            # ranks — the boss controller owns minions.
            if (self.formation_spawner is not None
                    and not self.level_config.get("boss")):
                if self.distance_goal > 0:
                    progress = min(1.0, self.distance / self.distance_goal)
                else:
                    progress = 0.0
                self.formation_spawner.rank_interval_px = graphics.ws(
                    self._rank_interval_start
                    + (self._rank_interval_end - self._rank_interval_start) * progress)
                self.formation_spawner.update(
                    self.distance, x_min, y_min, x_max, y_max)
```

> Keep the `enemy_controller.update(...)` movement call that follows it (it now moves the formation straight down because `chase=0`). The `enemy_spawner` object is left in place but no longer ticked on normal levels; boss levels never used it for spawning (the boss controller does).

- [ ] **Step 6: Range-gate auto-aim targeting (non-boss)**

In the fire tick, in the non-boss `else` branch, replace the `find_nearest_enemy` call (lines 1932-1938) with a range-banded `find_nearest_threat`:
```python
                    else:
                        _rng_px = (self._weapon_range_px
                                   if self._weapon_range_px is not None
                                   else graphics.ws(99999.0))
                        _ti = entities.find_nearest_threat(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller, _rng_px)
                        if _ti >= 0:
                            target_x = self.enemy_pool.cx[_ti]
                            target_y = self.enemy_pool.cy[_ti]
                            has_target = True
```

- [ ] **Step 7: Clamp the manual reticle to the kill-zone**

In the `_update` reticle block, find the manual-human branch that sets the reticle lead (the two `graphics.ws(RETICLE_LEAD_DIST)` uses near lines 1693 and 1702). Replace the lead distance expression `graphics.ws(RETICLE_LEAD_DIST)` in BOTH places with a helper that caps to the weapon range:
```python
                    _lead = (self._weapon_range_px
                             if self._weapon_range_px is not None
                             else graphics.ws(RETICLE_LEAD_DIST))
```
…and use `_lead` where `graphics.ws(RETICLE_LEAD_DIST)` was. (Compute `_lead` once at the top of the `if self._aim_mode == "manual"` block so both the auto_mode fallback and the steering branch use it.)

- [ ] **Step 8: Recompute range on weapon-gate swap**

In `game.py`, find the gate-effect code that swaps the weapon (`self.current_weapon_id = gate.value`, line 2260). Right after it, add:
```python
                self._update_weapon_range()
```
(Match the surrounding indentation — it's inside the gate-apply method.)

- [ ] **Step 9: Recompute range on layout/reset**

In `_reset`, after the hero position is established (after `self._reticle_x = hero_cx` / the aim-state reset block, ~line 1220), add:
```python
        self._update_weapon_range()
```

- [ ] **Step 10: Unit tests + boot smoke**

Run:
```bash
venv/bin/python test_weapon_range.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_projectile_killline.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all print their PASS lines.

Boot smoke:
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_af.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_af.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback referencing our files.

- [ ] **Step 11: Commit**
```bash
git add game.py
git commit -m "feat: wire army formation + per-weapon kill-zone + range line into game loop"
```

---

### Task 7: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run every suite**
```bash
venv/bin/python test_weapon_range.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_projectile_killline.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py \
 && venv/bin/python test_weapons_balance.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_levels_balance.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_spawner_balance.py \
 && venv/bin/python test_aim.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_boss_targeting.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_gate_emphasis.py
```
Expected: all PASS (prior-feature suites must not regress).

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual play checks (reviewer, needs a display)**

Verify and report honestly what was/wasn't checked:
1. **Formation:** enemies march **straight down** in a grid of ranks/columns; they do NOT veer toward the player.
2. **Kill-zone:** the army is visible filling the lane above the range line; nothing dies above the line; shots visibly stop at the line.
3. **Range line:** visible, and **moves** when a weapon gate (or shop equip) changes the weapon; sniper line highest, shotgun lowest.
4. **Difficulty:** continuous pressure from the start, rising toward the end and across worlds; no easy early stretch.
5. **Boss levels:** unchanged — boss is hittable (no kill-zone cap), minions behave as before.
6. **Perf:** frame rate holds in dense late levels (use the FPS overlay).

- [ ] **Step 4: Note gaps**

Per CLAUDE.md, confirm the weapon-swap range-line move has its tween + sfx, and note anything left un-juiced or any perf concern (rank interval / columns are the tuning knobs).

---

## Self-review notes (author)

- **Spec coverage:** A formation+straight-down → Task 3 (`chase=0`) + Task 6 step 5 (drive it) + the existing `update()` (no change needed). B kill-zone + range line → Task 1 (`range_frac`), Task 2 (`RangeLine`), Task 4 (projectile despawn), Task 6 steps 3/6/7/8 (compute, target-gate, reticle clamp, weapon-swap). C difficulty pacing → Task 5 (params) + Task 6 step 5 (within-level ramp). D win/attrition unchanged (no task needed; movement + win logic untouched). E perf → bounded columns/interval; Task 7 step 3/4 checks. Boss bypass → Task 6 step 3 (`is_boss` → None). Supersede #16 → Task 6 step 5 stops ticking `enemy_spawner` (the varied-Y/poof path) on normal levels.
- **Type/name consistency:** `weapons.Weapon.range_frac`; `graphics.RangeLine.set_line/show/hide` + `line_y` NumericProperty; `entities.FormationSpawner(controller, seed)` with `.columns/.rank_interval_px/.enemy_speed/.enemy_hp/.hp_scale/.spawn_table/.reset_per_level/.update`; `ProjectileController.kill_line_y`; `entities.find_nearest_threat(cx, cy, controller, max_front)` (existing); `entities.TYPE_NAMES` (existing); `GameScreen._weapon_range_px/_update_weapon_range/range_line/formation_spawner/_rank_interval_start/_rank_interval_end`. Consistent across tasks.
- **Testability:** FormationSpawner + ProjectileController tested with fake controllers/pools (no atlas needed); `_spawn_rank`/`update` use `graphics.ws` so run under SDL dummy. RangeLine smoke-checked. game.py integration verified by suites + boot.
- **Ordering:** Tasks 1-5 are independent and precede Task 6 (which wires them). Task 6 reuses the balance-pass `hp_scale` and the existing `find_nearest_threat` / `TYPE_NAMES`. The RangeLine `NumericProperty` note in Task 2 must be honored or the tween will not animate.
