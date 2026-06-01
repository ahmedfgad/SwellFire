# UI Fixes — Design

**Date:** 2026-06-01
**Status:** Approved (design); pending implementation plan
**Sub-project of:** the larger Swellfire gameplay backlog (sub-project ⑥).
Covers backlog items #3 (gate text wrap on scale), #10 (shop card text overlap),
#13 (debug-text toggle), #4 (notch/safe-area).

## Goal

Fix four UI defects that hurt readability and break on certain phones, without
changing gameplay. Keep text legible (the game is played by children) and follow
the project's visual-richness and density-independence rules.

## Scope

In scope: the four fixes below. Out of scope: every other backlog sub-project
(balance, reward gates, juice, economy).

New persisted settings: `show_debug` (bool, default False), `top_safe_inset`
(float fraction of screen height, default 0.05).

---

## #3 — Gate text must not wrap when it "pops"

**Cause.** `gates.py` `emphasize()` (gates.py:256-265) animates the primary
label's `font_size` ×1.18 when a gate pair enters the decision zone, but the
label's `text_size` box is fixed in `_sync` (gates.py:250 math expression =
`(self.width, self.height*0.46)`; gates.py:254 bonus name = `self.size`). The
larger font reflows inside the fixed box and wraps — e.g. the word gate
"Reinforce" breaks to "Reinforc" / "e".

**Fix.** Replace the font-size pulse with a **uniform scale transform** that
magnifies the already-laid-out gate as rendered pixels, so the text never
reflows:

- The text is laid out once at its base `font_size`/`text_size` (fits on one
  line / its normal layout).
- Add a `Scale` context instruction to the `Gate` widget's `canvas.before`
  (with a matching `PushMatrix` … and `PopMatrix` in `canvas.after`), with the
  scale origin at the gate's center. Because Kivy draws parent `canvas.before`
  → children → parent `canvas.after`, the transform wraps the child labels, so
  box + glyphs scale together.
- Drive the scale from a `NumericProperty` (e.g. `emph_scale`, default 1.0) that
  a bound callback writes into the `Scale` instruction. `emphasize()` animates
  that property `1.0 → 1.18 → 1.0` (same 0.22s out_quad / 0.22s in_quad timing),
  instead of touching `font_size`.

**Result.** The same "scale up and return" pop the user saw on iOS, with no
wrapping, on both math gates and word/bonus gates.

**Verify.** Headless: instantiate a `Gate` with a long bonus label
("Reinforce"), call `emphasize()`, and assert the label's `text` and the number
of rendered lines are unchanged at the animation's peak (font_size /
`text_size` untouched; only the `Scale`/`emph_scale` changed).

---

## #10 — Shop card title/description overlap

**Cause.** In the shop item row (ui.py ~1118-1159) the mid column mixes a
fixed-height title (`height=dp(28)`, ui.py:1124) with a flexible-height
description (no fixed height). When a title wraps to two lines (e.g.
"Reinforcements x 1", "Grenade x 1") it overflows the 28dp box and visually
collides with the description below. Card height is fixed at `dp(96)`
(ui.py:1042).

**Fix.**
1. Rebuild the mid column so title and description occupy **non-overlapping
   regions**: give each a height (proportional `size_hint_y`, or content-driven)
   and set each label's `text_size` to its allotted `(width, height)` with
   `valign="top"` (title) so a vertical `BoxLayout` lays them out without
   overlap. The title gets enough height for two lines.
2. **Increase the card height** modestly (from `dp(96)` to a value that fits a
   2-line title + description + the right-column price/state at the current font
   sizes — `~dp(112)`, finalized during implementation by checking the longest
   catalog labels). Text sizes are unchanged (legibility preserved); the scroll
   list just grows slightly.

Apply to all shop categories (weapons / boosters / squad) since the row builder
is shared.

**Verify.** Visual: open the shop and confirm the longest titles
("Reinforcements x 1", "Grenade x 5") sit on their own lines with the
description fully below and no overlap, across weapons/boosters/squad. (Headless
can confirm no construction error via a boot smoke check; overlap itself is a
visual check.)

---

## #13 — Toggle for FPS / enemy-count / distance debug text

**Cause.** `graphics.DebugOverlay` (graphics.py:376-410; FPS, frame ms, entity
counts incl. enemies/distance) is created and added unconditionally in `game.py`
(~625-628) and is **not** governed by `show_stats` (which only toggles the dark
band, title, and stat chips via `_apply_stats_visibility`, game.py ~3638-3654).
So the debug text is always on screen with no way to hide it.

**Fix.**
- New persisted setting **`show_debug`** in `state.py: DEFAULT_SETTINGS`,
  default **False** (hidden by default).
- New Settings toggle in `ui.py: SettingsScreen` reading/writing `show_debug`,
  styled like the existing "Stats bar" toggle, labelled **"FPS / debug info"**.
- In `game.py`, gate the `DebugOverlay`'s visibility on `show_debug`
  (set `self.debug.opacity` and stop its per-frame work when off, or skip
  `report_counts`/hide the widget). Read the setting on level enter and apply,
  same lifecycle as `show_stats`.

**Verify.** Headless: `show_debug` defaults to False; toggling persists. Boot
smoke check: with default settings the overlay is hidden; with `show_debug=True`
it shows.

---

## #4 — Notch / dynamic-island safe area

**Cause.** The always-visible progress bar (`dist_bar_holder`,
`pos_hint={"center_x":0.5,"top":0.985}`, game.py ~580-594), the top bar
(`pos_hint={"top":1.0}`, game.py ~547-558), and the coin counter/timer are all
hard-anchored to the very top of the screen. A phone notch / dynamic island in
the top center covers the progress bar and coin timer. No safe-area handling
exists anywhere in the codebase.

**Fix — adjustable top inset.**
- New persisted setting **`top_safe_inset`** (float fraction of screen height,
  default **0.05**, clamped to `[0.0, 0.12]`).
- Shift every top-anchored HUD element down by this fraction: subtract it from
  their `pos_hint` `top` values (progress bar `top: 0.985 - inset`, top bar
  `top: 1.0 - inset`, and the coin counter/timer — **the implementation plan
  enumerates the exact widgets** by reading the HUD-construction block in
  `game.py`). Use a single helper/constant so all top elements stay in sync.
- New Settings **slider** in `ui.py: SettingsScreen` for `top_safe_inset`
  (range 0 → 0.12, like the existing Volume slider), applied **live** so the
  player can dial it until their notch is clear. Re-apply on level enter.
- All offsets derive from `pos_hint` fractions (already density-independent); any
  raw-px additions wrapped in `graphics.ws()` per CLAUDE.md.

**Verify.** Headless: setting defaults to 0.05, clamps to range, persists. Boot
smoke check with inset 0 and inset 0.12 → no traceback. Visual: HUD shifts down
as the slider increases.

---

## Affected files

- `state.py` — add `show_debug` (False) and `top_safe_inset` (0.05) to
  `DEFAULT_SETTINGS`.
- `gates.py` — `Gate`: `emph_scale` property + `Scale` transform in
  canvas.before/after; rewrite `emphasize()` to animate the property.
- `ui.py` — `SettingsScreen`: "FPS / debug info" toggle + `top_safe_inset`
  slider; `ShopScreen`/row builder: mid-column rebuild + taller card height.
- `game.py` — gate `DebugOverlay` on `show_debug`; apply `top_safe_inset` to
  top-anchored HUD elements on level enter.

## Testing / verification

- Headless settings checks (defaults, clamping, persistence) via
  `SDL_AUDIODRIVER=dummy venv/bin/python -c "..."`.
- Gate no-wrap headless assertion (text + line count unchanged at emphasis peak).
- `SDL_AUDIODRIVER=dummy venv/bin/python test_world_scale.py` — density
  regression still passes.
- Boot smoke: `SDL_AUDIODRIVER=dummy timeout 8 venv/bin/python main.py` with
  default and extreme setting values — no traceback.
- Visual checks (need a display, flagged for the user): shop cards no overlap;
  gate pop no wrap; debug toggle hides/shows; HUD shifts under the slider.

## Open questions

None — approved as-is (default inset 0.05 with slider; taller cards keeping text
size; scale-transform gate pop; `show_debug` default off).
