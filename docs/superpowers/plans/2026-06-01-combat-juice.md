# Combat Juice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add gate squad-change popups, aggregated score-from-kill popups, and rate-limited smash/hit combat SFX — without spam in dense formations.

**Architecture:** A pure `combat_juice.py` holds the score table + cue/throttle helpers (unit-testable, no Kivy). `entities.resolve_projectile_collisions` gains an optional `on_hit` callback for non-lethal contacts. `game.py` shows per-gate delta popups, accumulates per-kill score and flushes one popup per window, and drives a single rate-limited combat-SFX channel (death-priority). `tools/gen_sfx.py` + `audio.py` add `smash` and `enemy_hit` cues.

**Tech Stack:** Python 3, Kivy 2.3. Pure logic (score/cue/throttle) and the collision `on_hit` are unit-tested headlessly with fakes; the GameScreen wiring is verified by a structural check + boot smoke + manual play.

---

### Task 1: `combat_juice.py` pure helpers

**Files:**
- Create: `combat_juice.py`
- Test: `test_combat_juice.py`

`combat_juice.py` imports nothing from Kivy/entities so it stays pure; its `SCORE_PER_KILL` keys are the `entities.TYPE_*` int values (a test asserts they match, catching drift).

- [ ] **Step 1: Write the failing test** — create `test_combat_juice.py`:

```python
"""test_combat_juice.py — pure combat-feedback helpers.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py
(pure helpers need no SDL; the mapping check imports entities under SDL dummy.)"""
import combat_juice


def test_score_for_kill_by_type():
    # grunt=0:10, tank=1:50, bomber=2:25, splitter=3:20, swarmer=4:8
    assert combat_juice.score_for_kill(0) == 10
    assert combat_juice.score_for_kill(1) == 50
    assert combat_juice.score_for_kill(4) == 8
    assert combat_juice.score_for_kill(999) == 10   # unknown → default 10


def test_combat_cue_prefers_kill():
    assert combat_juice.combat_cue(True, True) == "smash"
    assert combat_juice.combat_cue(True, False) == "smash"
    assert combat_juice.combat_cue(False, True) == "enemy_hit"
    assert combat_juice.combat_cue(False, False) is None


def test_sfx_due_respects_interval():
    assert combat_juice.sfx_due(now=1.0, last=0.90, interval=0.07) is True
    assert combat_juice.sfx_due(now=1.0, last=0.95, interval=0.07) is False


def test_score_table_keys_match_entity_types():
    import entities
    assert set(combat_juice.SCORE_PER_KILL) == {
        entities.TYPE_GRUNT, entities.TYPE_TANK, entities.TYPE_BOMBER,
        entities.TYPE_SPLITTER, entities.TYPE_SWARMER,
    }


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COMBAT JUICE TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'combat_juice'`.

- [ ] **Step 3: Create `combat_juice.py`**

```python
"""combat_juice.py — pure helpers for combat feedback (no Kivy import).

Holds the per-kill score table and the combat-SFX cue/throttle logic so they
can be unit-tested without a display. The SCORE_PER_KILL keys are the
entities.TYPE_* int values (0=grunt, 1=tank, 2=bomber, 3=splitter, 4=swarmer);
a test asserts they stay in sync with entities.
"""

# enemy_type int -> score awarded per kill (tunable first pass).
SCORE_PER_KILL = {
    0: 10,   # grunt
    1: 50,   # tank
    2: 25,   # bomber
    3: 20,   # splitter
    4: 8,    # swarmer
}


def score_for_kill(enemy_type: int) -> int:
    """Score awarded for killing `enemy_type` (default 10 for unknown)."""
    return SCORE_PER_KILL.get(int(enemy_type), 10)


def combat_cue(had_kill: bool, had_hit: bool):
    """Which combat sfx to play this window: death takes priority over hit.
    Returns "smash", "enemy_hit", or None."""
    if had_kill:
        return "smash"
    if had_hit:
        return "enemy_hit"
    return None


def sfx_due(now: float, last: float, interval: float) -> bool:
    """True if at least `interval` seconds have passed since the last play."""
    return (now - last) >= interval
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py`
Expected: PASS — `ALL COMBAT JUICE TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add combat_juice.py test_combat_juice.py
git commit -m "feat: combat_juice pure helpers (score table, cue, throttle)"
```

---

### Task 2: `smash` + `enemy_hit` SFX cues

**Files:**
- Modify: `tools/gen_sfx.py` — `GENERATORS` dict (~line 129-169)
- Modify: `audio.py` — `SFX_FILES` (~line 30-57)
- Generated: `assets/sfx/smash.wav`, `assets/sfx/enemy_hit.wav`
- Test: `test_combat_sfx_files.py`

- [ ] **Step 1: Add the builders**

In `tools/gen_sfx.py`, add to the `GENERATORS` dict (before the closing `}`):
```python
    # Enemy smash (death): low square crunch + filtered noise burst.
    "smash.wav": lambda: mix(
        tone(110, 0.18, kind="square", release=0.16),
        noise(0.18, smooth=3, release=0.16)),
    # Enemy hit (non-lethal): short mid thud, quick decay.
    "enemy_hit.wav": lambda: mix(
        sweep(220, 120, 0.09, kind="square", release=0.07),
        noise(0.07, smooth=2, release=0.06)),
```

- [ ] **Step 2: Register the cue names in audio.py**

In `audio.py` `SFX_FILES`, add (e.g. after the `"magnet"` entry):
```python
    "smash":          "smash.wav",        # enemy death crunch (rate-limited)
    "enemy_hit":      "enemy_hit.wav",    # non-lethal enemy impact (rate-limited)
```

- [ ] **Step 3: Generate the wavs**

Run: `venv/bin/python tools/gen_sfx.py`
Expected: it writes all sfx wavs (look for `smash.wav` and `enemy_hit.wav` in the output / under `assets/sfx/`). Confirm both files now exist:
```bash
ls -1 assets/sfx/smash.wav assets/sfx/enemy_hit.wav
```

- [ ] **Step 4: Write the verification test** — create `test_combat_sfx_files.py`:

```python
"""test_combat_sfx_files.py — the new combat cues exist + are registered.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_combat_sfx_files.py"""
import os
import audio


def test_cues_registered():
    assert audio.SFX_FILES.get("smash") == "smash.wav"
    assert audio.SFX_FILES.get("enemy_hit") == "enemy_hit.wav"


def test_wav_files_exist():
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ("smash.wav", "enemy_hit.wav"):
        path = os.path.join(here, "assets", "sfx", fn)
        assert os.path.exists(path) and os.path.getsize(path) > 0, path


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COMBAT SFX FILE TESTS PASSED")
```

- [ ] **Step 5: Run the test**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_combat_sfx_files.py`
Expected: PASS — `ALL COMBAT SFX FILE TESTS PASSED`.

- [ ] **Step 6: Commit** (include the generated wavs — they ship as runtime assets)
```bash
git add tools/gen_sfx.py audio.py assets/sfx/smash.wav assets/sfx/enemy_hit.wav test_combat_sfx_files.py
git commit -m "feat: smash + enemy_hit combat SFX cues (#7)"
```

---

### Task 3: `on_hit` callback in the collision pass

**Files:**
- Modify: `entities.py` — `resolve_projectile_collisions` (lines 1081-1147)
- Test: `test_collision_on_hit.py`

- [ ] **Step 1: Write the failing test** — create `test_collision_on_hit.py`:

```python
"""test_collision_on_hit.py — on_hit fires for non-lethal contacts only.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py"""
import entities


class _Pool:
    def __init__(self, n):
        self.capacity = n
        self.active = [True] * n
        self.cx = [0.0] * n
        self.cy = [0.0] * n
        self.hw = [10.0] * n
        self.released = []
    def release(self, i):
        self.active[i] = False
        self.released.append(i)


class _PC:   # projectile controller stand-in
    def __init__(self, n, damage):
        self.pool = _Pool(n)
        self.damage = [damage] * n
        self.owner = bytearray(n)
        self.recycled_total = 0


class _EC:   # enemy controller stand-in
    def __init__(self, hps):
        n = len(hps)
        self.pool = _Pool(n)
        self.hp = list(hps)
        self.type = [0] * n           # all grunts (TYPE_GRUNT)
        self.recycled_total = 0


class _Grid:
    def clear(self): pass
    def insert_pool(self, pool): self._pool = pool
    def query(self, x, y, r):
        return [i for i in range(self._pool.capacity) if self._pool.active[i]]


def _run(enemy_hp, damage):
    pc = _PC(1, damage)
    ec = _EC([enemy_hp])
    # projectile and enemy at the same point so they collide.
    kills, hits = [], []
    entities.resolve_projectile_collisions(
        pc, ec, _Grid(),
        on_kill=lambda hx, hy, t, o: kills.append(t),
        on_hit=lambda hx, hy, t, o: hits.append(t),
    )
    return kills, hits


def test_non_lethal_hit_fires_on_hit_only():
    kills, hits = _run(enemy_hp=2, damage=1)   # survives
    assert kills == [] and hits == [0]


def test_lethal_hit_fires_on_kill_only():
    kills, hits = _run(enemy_hp=1, damage=1)   # dies
    assert kills == [0] and hits == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COLLISION ON_HIT TESTS PASSED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py`
Expected: FAIL — `TypeError: resolve_projectile_collisions() got an unexpected keyword argument 'on_hit'`.

- [ ] **Step 3: Add the `on_hit` param + non-lethal call**

In `entities.py`, change the signature (lines 1081-1086) from:
```python
def resolve_projectile_collisions(
    projectile_controller: ProjectileController,
    enemy_controller: EnemyController,
    grid: SpatialGrid,
    on_kill,
) -> int:
```
to:
```python
def resolve_projectile_collisions(
    projectile_controller: ProjectileController,
    enemy_controller: EnemyController,
    grid: SpatialGrid,
    on_kill,
    on_hit=None,
) -> int:
```

Then in the collision body, change the kill block (lines 1134-1146) from:
```python
                if e_hp[ei] <= 0:
                    hit_x = e_cx[ei]
                    hit_y = e_cy[ei]
                    enemy_type = int(e_type[ei])
                    killer = int(p_owner[pi])
                    ep.release(ei)
                    enemy_controller.recycled_total += 1
                    on_kill(hit_x, hit_y, enemy_type, killer)
                    kills += 1
                break   # projectile consumed
```
to:
```python
                if e_hp[ei] <= 0:
                    hit_x = e_cx[ei]
                    hit_y = e_cy[ei]
                    enemy_type = int(e_type[ei])
                    killer = int(p_owner[pi])
                    ep.release(ei)
                    enemy_controller.recycled_total += 1
                    on_kill(hit_x, hit_y, enemy_type, killer)
                    kills += 1
                elif on_hit is not None:
                    # Non-lethal contact (enemy survived) — signal for the
                    # rate-limited hit SFX.
                    on_hit(e_cx[ei], e_cy[ei], int(e_type[ei]), int(p_owner[pi]))
                break   # projectile consumed
```

- [ ] **Step 4: Run to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py`
Expected: PASS — `ALL COLLISION ON_HIT TESTS PASSED`.

- [ ] **Step 5: Commit**
```bash
git add entities.py test_collision_on_hit.py
git commit -m "feat: on_hit callback for non-lethal projectile contacts"
```

---

### Task 4: Wire the juice into game.py

**Files:**
- Modify: `game.py` — imports (~line 35); tuning constants (~line 60); `__init__` state (~near other run state); level reset (`_reset` ~1215 / level-start); `_on_apply_gate` (~2293); `_on_kill` + the `resolve_projectile_collisions` call (~2068-2096); `_update` throttles (after collisions ~2096)

- [ ] **Step 1: Import + constants**

In `game.py` add to the sibling imports (near `import boosters`):
```python
import combat_juice
```
Near the other tuning constants (after the manual-aim block ~line 60), add:
```python
# --- combat juice (#1/#2/#7) ---------------------------------------------
COMBAT_SFX_INTERVAL = 0.07      # min seconds between combat sfx (~14/sec cap)
SCORE_POPUP_INTERVAL = 0.35     # seconds between aggregated score popups
SCORE_POPUP_OFFSET = 80.0       # world-px above the squad for the score popup
SCORE_COLOR = (0.95, 0.96, 1.0, 1.0)        # white/silver — distinct from coins
GATE_GAIN_COLOR = (0.55, 0.80, 1.0, 1.0)    # squad blue (gate gain)
GATE_LOSS_COLOR = (1.0, 0.42, 0.40, 1.0)    # red (gate loss)
GATE_WEAPON_COLOR = (1.0, 0.80, 0.30, 1.0)  # weapon amber
```

- [ ] **Step 2: `__init__` state**

In `GameScreen.__init__`, near the other run-state fields (e.g. after `self._coins_earned`/`_coin_remainder` are set, or alongside `self._run_time` init), add:
```python
        # Combat-juice runtime state.
        self.score_total = 0
        self._pending_score = 0
        self._had_kill_this_frame = False
        self._had_hit_this_frame = False
        self._last_combat_sfx = 0.0
        self._last_score_popup = 0.0
```

- [ ] **Step 3: Reset on level start**

In the level-start path where `self._run_time` / coin accumulators are reset (search for where `self._run_time = 0.0` is set on entering a level, near `_reset`/`_apply_level_config`), add:
```python
        self._pending_score = 0
        self._last_combat_sfx = 0.0
        self._last_score_popup = 0.0
        self._had_kill_this_frame = False
        self._had_hit_this_frame = False
```
(`score_total` persists across the run if you want a running total; reset it too if score should be per-level — set `self.score_total = 0` here for per-level scoring.)

- [ ] **Step 4: Gate-delta popups in `_on_apply_gate`**

In `_on_apply_gate`, capture the squad count BEFORE the op chain. Right after the coin-reward lines and before `if gate.op == gates.OP_MUL:` (line 2305), add:
```python
        _prev_squad = self.squad_count
```
Then AFTER the whole `if/elif` op chain (after the `OP_MAGNET` branch ends, ~line 2336, before the audio/particle block at ~2337), add:
```python
        # Squad-change popup (distinct from coins): every gate gets feedback.
        if gate.op in (gates.OP_MUL, gates.OP_ADD, gates.OP_SUB, gates.OP_DIV):
            _sym = {gates.OP_MUL: "×", gates.OP_ADD: "+",
                    gates.OP_SUB: "−", gates.OP_DIV: "÷"}[gate.op]
            _delta = self.squad_count - _prev_squad
            _color = GATE_GAIN_COLOR if _delta >= 0 else GATE_LOSS_COLOR
            self._float_text("{}{}".format(_sym, int(gate.value)), _color)
        elif gate.op == gates.OP_WEAPON:
            self._float_text("{}!".format(str(gate.value).upper()),
                             GATE_WEAPON_COLOR)
        # Reward gates pop their own booster float-text from the effect calls.
```

- [ ] **Step 5: Score + kill/hit flags in the collision callbacks**

In the `_on_kill` closure (lines 2072-2093), inside the `if killer == 0:` block (after `_self.kills_total += 1`, line 2083), add:
```python
                    _self._pending_score += combat_juice.score_for_kill(enemy_type)
                    _self.score_total += combat_juice.score_for_kill(enemy_type)
                    _self._had_kill_this_frame = True
```

Then change the `resolve_projectile_collisions` call (lines 2094-2096) to pass an `on_hit`:
```python
            def _on_hit(hx, hy, etype, owner, _self=self):
                if owner == 0:
                    _self._had_hit_this_frame = True
            entities.resolve_projectile_collisions(
                self.projectile_controller, self.enemy_controller, self.grid,
                _on_kill, on_hit=_on_hit,
            )
```

- [ ] **Step 6: Throttled flush in `_update`**

In `_update`, right AFTER the projectile-vs-boss collision block (after the `_on_boss_hit` handling, ~line 2107+ where the boss collision resolves) and before the HUD sync, add:
```python
            # Combat SFX — one rate-limited cue per window, death-priority.
            _cue = combat_juice.combat_cue(self._had_kill_this_frame,
                                           self._had_hit_this_frame)
            if _cue is not None and combat_juice.sfx_due(
                    self._run_time, self._last_combat_sfx, COMBAT_SFX_INTERVAL):
                ui.app().audio.play_sfx(_cue)
                self._last_combat_sfx = self._run_time
            self._had_kill_this_frame = False
            self._had_hit_this_frame = False

            # Aggregated score popup — one Label per window, never per kill.
            if (self._run_time - self._last_score_popup >= SCORE_POPUP_INTERVAL):
                if self._pending_score > 0 and self.hero is not None:
                    self._float_text(
                        "+{}".format(self._pending_score), SCORE_COLOR,
                        cx=self.hero.center_x,
                        cy=self.hero.center_y + graphics.ws(SCORE_POPUP_OFFSET))
                    self._pending_score = 0
                self._last_score_popup = self._run_time
```
Match the indentation of the surrounding `_update` body (this sits inside the same block as the collision resolution). Confirm `ui`, `graphics`, `combat_juice` are imported (they are / Task step 1).

- [ ] **Step 7: Unit tests + structural check + boot smoke**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_combat_sfx_files.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py
```
Expected: all PASS.

Structural check:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python -c "
import game, inspect
src = inspect.getsource(game.GameScreen._on_apply_gate)
assert 'GATE_GAIN_COLOR' in src and '_prev_squad' in src
k = inspect.getsource(game.GameScreen._update)
assert 'combat_cue' in k and '_pending_score' in k
print('structural OK')
"
```
Expected: prints `structural OK`.

Boot smoke:
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_cj.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_cj.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback referencing our files.

- [ ] **Step 8: Commit**
```bash
git add game.py
git commit -m "feat: gate-delta + aggregated score popups + rate-limited combat SFX (#1/#2/#7)"
```

---

### Task 5: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Run every suite**
```bash
SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_combat_sfx_files.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_collision_on_hit.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_reward_gates_label.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_formation_spawner.py \
 && SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py \
 && venv/bin/python test_aim.py
```
Expected: all PASS (prior-feature suites must not regress).

- [ ] **Step 2: Boot smoke**
```bash
SDL_AUDIODRIVER=dummy timeout 10 venv/bin/python main.py >/tmp/sf_final.log 2>&1; echo "exit=$?"; grep -iE "traceback" /tmp/sf_final.log | grep -ivE "xclip|xsel|clipboard|ffpyplayer" | head
```
Expected: `exit=124`, no traceback.

- [ ] **Step 3: Manual play + audio checks (reviewer, needs a display + sound)**

Verify and report honestly:
1. **#1:** every gate shows a delta popup — math gates `×2`/`+5`/`−3`/`÷2` in blue (gain) or red (loss); weapon gates the weapon name in amber; reward gates their booster text. Colors are clearly not coin-gold.
2. **#2:** a white `+N` score popup appears above the squad periodically (not per kill) and never floods the screen in dense formations.
3. **#7:** `smash` plays on deaths and `enemy_hit` on non-lethal hits, both **capped** (no machine-gun audio) when a whole rank dies at once; death audio takes priority.
4. No frame-rate dip from the popups/SFX in dense W5/W6 levels.

- [ ] **Step 4: Note gaps**

Per CLAUDE.md, confirm nothing meaningful is silent and the rate limits feel right (the `COMBAT_SFX_INTERVAL` / `SCORE_POPUP_INTERVAL` constants are the dials).

---

## Self-review notes (author)

- **Spec coverage:** #1 gate popups → Task 4 step 4 (math delta blue/red + weapon amber; reward gates already pop). #2 score popups → Task 1 (score table) + Task 4 steps 5/6 (accumulate + aggregated flush, white, above squad). #7 SFX → Task 2 (smash/enemy_hit cues) + Task 3 (on_hit) + Task 4 steps 5/6 (flags + death-priority rate-limited channel). Spam-control: aggregation (score) + throttle (sfx) — central per spec.
- **Type/name consistency:** `combat_juice.SCORE_PER_KILL / score_for_kill / combat_cue / sfx_due`; sfx names `smash` / `enemy_hit` (consistent across gen_sfx, audio, combat_cue, and game playback); `resolve_projectile_collisions(..., on_kill, on_hit=None)`; GameScreen `score_total / _pending_score / _had_kill_this_frame / _had_hit_this_frame / _last_combat_sfx / _last_score_popup`; constants `COMBAT_SFX_INTERVAL / SCORE_POPUP_INTERVAL / SCORE_POPUP_OFFSET / SCORE_COLOR / GATE_GAIN_COLOR / GATE_LOSS_COLOR / GATE_WEAPON_COLOR`.
- **Testability:** score/cue/throttle pure (Task 1); on_hit via fakes (Task 3); sfx files via existence+registration (Task 2); GameScreen wiring via structural check + boot + manual (Task 4) since instantiating the screen headlessly is impractical.
- **Ordering:** Task 1 (helpers) + Task 2 (cues) + Task 3 (on_hit) are independent and precede Task 4 (wires all three). gate popups reuse the existing `_float_text`; no pooling added (gate = per-event, score = per-window).
