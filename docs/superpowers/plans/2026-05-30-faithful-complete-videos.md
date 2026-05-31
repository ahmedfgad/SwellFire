# Faithful, Complete, Longer Swellfire Videos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the three `swellfire_media/` videos so they play at smooth, faithful real game-time (60 fps) and run longer, and make the autoplay video play one complete level per world start → finish (including the victory/stars screen).

**Architecture:** Capture is already real-time (`dt = 1/fps`, encode at same `fps`); raise `fps` 30 → 60 for smoothness. Add a `--playthrough` mode to `tools/capture.py` that seeds a capture-only strong squad/weapon, drives the GA autoplayer to a *genuine* level win, and keeps grabbing frames through the victory banner + result dialog. `tools/make_videos.py` switches to 6 full-level playthroughs (one regular level per world). `make_promo.py`/`make_short.py` stay montages but at 60 fps with longer windows.

**Tech Stack:** Python, Kivy (capture harness), imageio-ffmpeg (encode), PIL/numpy. Headless logic tests via `venv/bin/python`; integration smoke via `pytest tools/tests/` under Xvfb.

---

## Spec reference

`docs/superpowers/specs/2026-05-30-faithful-complete-videos-design.md`

## File map

- `tools/capture.py` — **modify**: add `seed_strong_squad()` helper, `--playthrough` arg, and playthrough drive/win-capture logic.
- `tools/make_videos.py` — **modify**: `FPS = 60`, `_segments()` → 6 full-level playthroughs, frame cap, timeout bump.
- `tools/make_promo.py` — **modify**: `FPS = 60`, longer windows.
- `tools/make_short.py` — **modify**: `FPS = 60`, longer windows.
- `tools/tests/test_capture_playthrough.py` — **create**: unit tests for `seed_strong_squad()` and the `--playthrough` argparser.
- `tools/tests/test_make_videos_segments.py` — **create**: unit test for `_segments()` level picks + `FPS`.
- `swellfire_media/README.md` — **modify**: durations, 60 fps, complete-levels note.

---

## Task 1: Strong-squad seed helper (capture-only, pure, testable)

**Files:**
- Modify: `tools/capture.py`
- Test: `tools/tests/test_capture_playthrough.py` (create)

The seed must mutate state **in memory only** (no `.save()`), so the real
`swellfire_save.json` is untouched. We therefore write directly into a
state-like object's `.data` dict rather than calling the saving setters
(`equip_weapon`, `upgrade_weapon_tier`, `set_squad_bonus` all call `self.save()`).

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_capture_playthrough.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class _FakeState:
    """Mimics state.GameState.data; .save() must NOT be called by the seed."""
    def __init__(self):
        self.data = {"equipped_weapon": "pistol",
                     "weapon_tiers": {"pistol": 1, "rifle": 1, "shotgun": 1, "sniper": 1},
                     "squad_bonus": 0}
        self.saved = False

    def save(self):
        self.saved = True


def test_seed_strong_squad_maxes_weapon_and_squad_in_memory():
    from tools.capture import seed_strong_squad
    st = _FakeState()
    seed_strong_squad(st)
    assert st.data["equipped_weapon"] == "rifle"
    assert st.data["weapon_tiers"] == {"pistol": 4, "rifle": 4, "shotgun": 4, "sniper": 4}
    assert st.data["squad_bonus"] == 6
    assert st.saved is False  # seeding must never persist to the real save


def test_seed_strong_squad_tolerates_missing_keys():
    from tools.capture import seed_strong_squad
    st = _FakeState()
    st.data = {}
    seed_strong_squad(st)
    assert st.data["equipped_weapon"] == "rifle"
    assert st.data["weapon_tiers"]["sniper"] == 4
    assert st.data["squad_bonus"] == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_capture_playthrough.py -q`
Expected: FAIL with `ImportError: cannot import name 'seed_strong_squad'`.

- [ ] **Step 3: Add the helper**

In `tools/capture.py`, after the imports block (after `from PIL import Image`,
before `_parse_size`), add:

```python
def seed_strong_squad(state):
    """Capture-only marketing seed: max every weapon tier, equip the lively
    rifle, and max the starting-squad bonus so the autoplayer reliably
    survives a full level and reaches a genuine win. Writes the in-memory
    `state.data` directly and DOES NOT call state.save() — the real
    swellfire_save.json must stay untouched by captures.
    """
    state.data["equipped_weapon"] = "rifle"
    state.data["weapon_tiers"] = {"pistol": 4, "rifle": 4, "shotgun": 4, "sniper": 4}
    state.data["squad_bonus"] = 6
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_capture_playthrough.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/capture.py tools/tests/test_capture_playthrough.py
git commit -m "capture: add capture-only strong-squad seed helper"
```

---

## Task 2: `--playthrough` CLI flag

**Files:**
- Modify: `tools/capture.py` (`_build_argparser`)
- Test: `tools/tests/test_capture_playthrough.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_capture_playthrough.py`:

```python
def test_playthrough_flag_parses():
    from tools.capture import _build_argparser
    ns = _build_argparser().parse_args(
        ["--level", "6", "--out", "x", "--playthrough"])
    assert ns.playthrough is True


def test_playthrough_defaults_false():
    from tools.capture import _build_argparser
    ns = _build_argparser().parse_args(["--level", "6", "--out", "x"])
    assert ns.playthrough is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_capture_playthrough.py -k playthrough_flag -q`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'playthrough'`.

- [ ] **Step 3: Add the flag**

In `tools/capture.py`, inside `_build_argparser`, after the `--win` argument
(before `return ap`), add:

```python
    ap.add_argument("--playthrough", action="store_true",
                    help="(level mode) seed a strong squad, drive the autoplayer "
                         "to a genuine level win, and keep capturing through the "
                         "victory banner + result dialog (full start->finish clip)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_capture_playthrough.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/capture.py tools/tests/test_capture_playthrough.py
git commit -m "capture: add --playthrough CLI flag"
```

---

## Task 3: `--playthrough` drive + win-capture logic

**Files:**
- Modify: `tools/capture.py` (`after_build`, `_drive`)

This is integration behaviour driven by Kivy's `Clock`, verified by the smoke
test in Task 7 (needs a display), not a unit test. Make the edits precisely.

- [ ] **Step 1: Seed the squad in `after_build`**

In `tools/capture.py`, inside `after_build`, immediately after the
`tutorial_seen` try/except block and BEFORE the `if args.screen is not None:`
branch, add:

```python
        if args.playthrough:
            seed_strong_squad(app.state)
```

- [ ] **Step 2: Don't stop at level-end during a playthrough**

In `_drive`, the early level-end stop currently reads:

```python
        if (not args.win and args.out is not None and args.level is not None
                and gs is not None and state["ready"] and gs._level_ended):
            _finish()
            return
```

Change the guard so a playthrough does NOT bail at `_level_ended` (it must keep
filming the victory sequence):

```python
        if (not args.win and not args.playthrough and args.out is not None
                and args.level is not None and gs is not None
                and state["ready"] and gs._level_ended):
            _finish()
            return
```

- [ ] **Step 3: Add the playthrough grab/win-capture block**

In `_drive`, the normal-capture block currently begins:

```python
        # Grab after warmup.
        if state["frame"] >= args.warmup:
```

Insert the following playthrough block IMMEDIATELY BEFORE that `# Grab after
warmup.` comment (so it runs after the sim step + `state["simt"] += DT`, and the
non-playthrough path is unchanged):

```python
        # --playthrough: film the whole level. Grab every frame after warmup;
        # once the level is genuinely won, keep stepping (on a small real delay
        # so the deferred result dialog — _open_result_dialog, ~1s real-time
        # after _end_level — actually opens) and keep grabbing until the dialog
        # has been visible for ~2s, then stop. A hard --frames cap bounds it.
        if args.playthrough and args.out is not None:
            from kivy.uix.modalview import ModalView
            if state["frame"] >= args.warmup:
                arr = grab_frame(Window)
                idx = state["frame"] - args.warmup
                os.makedirs(args.out, exist_ok=True)
                Image.fromarray(arr).save(os.path.join(args.out, "f%05d.png" % idx))
                state["frame"] += 1
                # Hard safety cap.
                if idx + 1 >= args.frames:
                    if gs is not None and not gs._level_ended:
                        print("WARNING: playthrough hit --frames cap before "
                              "level end (level %s)" % args.level)
                    _finish()
                    return
            else:
                state["frame"] += 1
            # Track the post-win victory/dialog tail.
            if gs is not None and gs._level_ended:
                modal_open = any(isinstance(c, ModalView) for c in Window.children)
                if modal_open:
                    state["modal_seen"] = True
                if state["modal_seen"]:
                    state["modal_settle"] += 1
                # ~2s of dialog at args.fps, plus require it actually opened.
                if state["modal_seen"] and state["modal_settle"] >= 2 * args.fps:
                    _finish()
                    return
                # Post-end the sim runs far faster than the real-time dialog
                # timer; step on a small real delay so that timer can elapse.
                Clock.schedule_once(_drive, 1.0 / 120.0)
                return
            Clock.schedule_once(_drive, 0)
            return

        # Grab after warmup.
        if state["frame"] >= args.warmup:
```

- [ ] **Step 4: Smoke-check syntax + argparse still import**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -c "import tools.capture; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Run the existing capture unit tests**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_capture_playthrough.py -q`
Expected: 4 passed (no regressions to the helper/flag).

- [ ] **Step 6: Commit**

```bash
git add tools/capture.py
git commit -m "capture: drive --playthrough to a genuine win + film victory tail"
```

---

## Task 4: `make_videos.py` — 60 fps, one full level per world

**Files:**
- Modify: `tools/make_videos.py`
- Test: `tools/tests/test_make_videos_segments.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_make_videos_segments.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def test_fps_is_60():
    from tools import make_videos
    assert make_videos.FPS == 60


def test_segments_one_regular_level_per_world():
    from tools import make_videos
    segs = make_videos._segments()
    levels = [s[1] for s in segs]
    assert levels == [6, 16, 26, 36, 46, 56]
    # all non-boss (boss is level 10 of each world)
    assert all(lvl % 10 != 0 for lvl in levels)


def test_segments_carry_a_safety_frame_cap():
    from tools import make_videos
    for label, level, warmup, frames in make_videos._segments():
        # 45s of play + ~3s victory tail at 60fps -> generous cap.
        assert frames >= 2800
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_make_videos_segments.py -q`
Expected: FAIL (`FPS == 30`, and `_segments()` returns 12 levels `2,4,12,14,...`).

- [ ] **Step 3: Bump FPS and timeout**

In `tools/make_videos.py`, change:

```python
FPS = 30
```
to
```python
FPS = 60
```

In `_capture_segment`, add `--playthrough` to the args and raise the timeout:

```python
def _capture_segment(level, warmup, frames, framedir, audio_json):
    args = ["--level", level, "--out", framedir, "--audio", audio_json,
            "--size", CAP, "--fps", FPS, "--warmup", warmup, "--frames", frames,
            "--playthrough"]
    subprocess.run(capture_run.capture_cmd(args), cwd=ROOT,
                   env=capture_run.capture_env(), check=True, timeout=2400)
```

- [ ] **Step 4: Rewrite `_segments()`**

Replace the whole `_segments()` function with:

```python
def _segments():
    """One full regular (non-boss) level per world, played start->finish via
    the capture's --playthrough mode. (label, level, warmup, frames-cap).
    Level 6 of each world (6,16,26,36,46,56): mid-world density, ~30s each.
    The frames value is a hard SAFETY CAP only — the capture stops at the
    genuine level-complete; this bounds a runaway. 45s + ~3s tail @60fps."""
    segs = []
    for wi in range(1, 7):
        level = (wi - 1) * 10 + 6
        label = "World {} · {}".format(wi, WORLD_NAMES[wi])
        segs.append((label, level, 60, 2880))
    return segs
```

- [ ] **Step 5: Run test to verify it passes**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/test_make_videos_segments.py -q`
Expected: 3 passed.

- [ ] **Step 6: Update the outro caption (no behaviour change, keeps copy honest)**

In `build_long`, the outro card caption is fine as-is. No edit needed. (Listed
so the reviewer doesn't expect one.)

- [ ] **Step 7: Commit**

```bash
git add tools/make_videos.py tools/tests/test_make_videos_segments.py
git commit -m "make_videos: 60fps, full-level playthrough per world"
```

---

## Task 5: `make_promo.py` & `make_short.py` — 60 fps, longer windows

**Files:**
- Modify: `tools/make_promo.py`, `tools/make_short.py`

These stay montages (no playthrough). At 60 fps the same wall-clock window needs
2× the frames, and we lengthen each window for a longer video.

- [ ] **Step 1: promo — FPS + windows + timeout**

In `tools/make_promo.py`, change `FPS = 30` to `FPS = 60`.

Replace the `WINDOWS` list with longer windows (≈6s each at 60fps = 360 frames),
and a higher warmup floor:

```python
WINDOWS = [
    (3,  60, 360, "Multiply your squad"),
    (13, 60, 360, "Swarm the desert"),
    (23, 60, 360, "Industrial firepower"),
    (33, 60, 360, "Frostbite assault"),
    (43, 60, 360, "Volcanic onslaught"),
]
```

In the `subprocess.run(... timeout=900)` call inside `build_promo`, raise the
timeout to `timeout=1800`.

- [ ] **Step 2: short — FPS + windows + timeout**

In `tools/make_short.py`, change `FPS = 30` to `FPS = 60`.

Replace `WINDOWS` with longer windows (≈7s each at 60fps = 420 frames):

```python
WINDOWS = [
    (4,  60, 420, "Grow your squad"),
    (24, 60, 420, "Open fire"),
]
```

In the `subprocess.run(... timeout=900)` call inside `build_short`, raise the
timeout to `timeout=1800`.

- [ ] **Step 3: Import sanity**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -c "from tools import make_promo, make_short; print(make_promo.FPS, make_short.FPS)"`
Expected: `60 60`

- [ ] **Step 4: Commit**

```bash
git add tools/make_promo.py tools/make_short.py
git commit -m "make_promo/short: 60fps + longer windows"
```

---

## Task 6: Smoke-test one playthrough segment (real capture, needs display)

**Files:** none (verification task)

- [ ] **Step 1: Capture a single short-cap playthrough of level 6**

This proves the autoplayer wins, the victory tail is filmed, and frames land.
Use a smaller cap so the smoke run is quick but still reaches a win on an easy
early level (level 6, ~7200px/360 ≈ 20s ≈ 1200 frames at 60fps — give headroom):

`capture_run` is a helper module (not a CLI), so invoke it the same way
`make_videos._capture_segment` does — build the argv with `capture_run.capture_cmd`
(wraps in `xvfb-run`) and run it with `capture_run.capture_env()`. Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python - <<'PY'
import subprocess
from tools import capture_run
ROOT = capture_run.ROOT
args = ["--level", 6, "--out", "/tmp/pt6", "--audio", "/tmp/pt6.json",
        "--size", "540x960", "--fps", 60, "--warmup", 60, "--frames", 1800,
        "--playthrough"]
r = subprocess.run(capture_run.capture_cmd(args), cwd=ROOT,
                   env=capture_run.capture_env(), timeout=2400)
print("exit", r.returncode)
PY
```

Expected: command exits 0; no `WARNING: playthrough hit --frames cap` line in
output (means it reached a genuine win). Inspect:
```bash
ls /tmp/pt6 | wc -l   # hundreds–~1300 frames
```

- [ ] **Step 2: Confirm the last frames show the result dialog**

Open the highest-numbered frame (e.g. `/tmp/pt6/f0XXXX.png`) and confirm it shows
the VICTORY banner / LevelResultDialog with stars. (Use the Read tool on the PNG.)
Expected: a level-complete dialog is visible — the clip ends on the win.

- [ ] **Step 3: If level 6 ends in DEFEAT or hits the cap**

Re-run with a stronger guarantee: the seed already maxes weapons + squad. If it
still loses, lower the featured level for that world in `make_videos._segments()`
(e.g. world 1 → level 4) and note it. Record any swaps in the README.

- [ ] **Step 4: Clean up**

```bash
rm -rf /tmp/pt6 /tmp/pt6.json
```

No commit (verification only).

---

## Task 7: Full build + verify all three videos

**Files:** generated `swellfire_media/*.mp4` (committed in Task 8)

- [ ] **Step 1: Build the autoplay video**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python tools/make_videos.py long`
Expected: prints per-segment progress for 6 segments, then `wrote .../swellfire_autoplay_1080p.mp4`.

- [ ] **Step 2: Build promo + short**

Run:
```bash
SDL_AUDIODRIVER=dummy venv/bin/python tools/make_promo.py
SDL_AUDIODRIVER=dummy venv/bin/python tools/make_short.py
```
Expected: each prints `wrote ...`.

- [ ] **Step 3: Probe durations + fps**

Run:
```bash
FF=$(venv/bin/python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
for f in swellfire_media/*.mp4; do echo "== $f =="; "$FF" -i "$f" 2>&1 | grep -E "Duration|Video:"; done
```
Expected: all three at `60 fps`, `1080x1920`; autoplay ≈ 3.5–4 min, promo ≈ 50–60s,
short ≈ 25–30s.

- [ ] **Step 4: Run the full media test suite**

Run: `SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tools/tests/ -q`
Expected: all pass.

---

## Task 8: Update README + commit media

**Files:**
- Modify: `swellfire_media/README.md`
- Commit: `swellfire_media/*.mp4`

- [ ] **Step 1: Update README durations + notes**

In `swellfire_media/README.md`:
- In the Contents table, update the video size/duration cells to the measured
  values from Task 7 Step 3 (autoplay ~3.5–4 min, promo ~50–60s, short ~25–30s).
- Replace the final bullet ("The long autoplay video shows 2 regular levels per
  world; ...") with:
  > The long autoplay video plays **one complete regular level per world**
  > (start → finish, including the victory/stars screen), driven by the
  > autoplayer with a capture-only strong-squad seed so it reliably wins. Boss
  > levels stay in the screenshots (the autoplayer can't reliably beat a boss).
  > All videos are captured and encoded at **60 fps** at true real game-time.

- [ ] **Step 2: Commit**

```bash
git add swellfire_media/README.md swellfire_media/swellfire_autoplay_1080p.mp4 \
        swellfire_media/swellfire_promo.mp4 swellfire_media/swellfire_short_vertical.mp4
git commit -m "media: rebuild all 3 videos at 60fps; autoplay plays full levels per world"
```

---

## Self-review notes

- **Speed (spec §Design 1):** Task 4/5 set `FPS = 60` in all three builders; capture
  derives `DT = 1/fps` and `encode_clip(fps=FPS)` already, so motion is smooth at
  true real-time. Covered.
- **Playthrough mode (spec §Design 2):** Tasks 1–3 — seed (capture-only, no save),
  natural win (no `--win` shove), film victory tail, frame cap + defeat warning. Covered.
- **One level per world (spec §Design 3):** Task 4 — levels 6,16,26,36,46,56, lower-third
  retained (unchanged `overlay_lower_third` call in `build_long`). Covered.
- **Promo/short longer + smooth (spec §Design 4):** Task 5. Covered.
- **Docs (spec §Design 5):** Task 8. Covered.
- **Verification (spec §Verification):** Task 6 (survival smoke + save-safety via
  Task 1 test), Task 7 (durations/fps re-probe, full suite). Covered.
- **Save safety:** `seed_strong_squad` writes `state.data` directly and never calls
  `.save()`; Task 1 test asserts `saved is False`. Covered.
- **Naming consistency:** `seed_strong_squad`, `args.playthrough`, `_segments()`,
  `FPS` used identically across tasks.
