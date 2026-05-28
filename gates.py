"""Gate spawn + pass-through detection.

A `Gate` is a colored translucent rectangle with a label that scrolls
down the road with the world. Two gates per pair, side by side, and the
player chooses one to pass through.

`GateController.update()` is the gameplay tick that:
    1. advances each gate downward at the world's scroll speed,
    2. fires `on_apply(gate)` the first time the hero crosses a pair
       (or marks the pair "missed" if the hero is between the two gates
       when the pair crosses past),
    3. recycles off-screen pairs.

Lane gravity (M4) reads the active pair's X positions from
`GateController.active_lane_centers(hero_cy)`, so the hero gently
snaps toward the nearer gate when the player isn't actively dragging.

Effects applied here in M7:
    * `OP_MUL` ×N           — squad_count = min(MAX, squad_count * N)
    * `OP_ADD` +N           — squad_count = min(MAX, squad_count + N)
    * `OP_SUB` -N           — squad_count = max(1,   squad_count - N)
    * `OP_WEAPON` <wid>     — current_weapon_id = <wid>

M8 will render the squad as a Mesh-batched runner crowd; M7's
gate effects already drive the integer squad_count so the renderer
just has to follow it.
"""

from __future__ import annotations

import random

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.widget import Widget


# --- op tags -------------------------------------------------------------

OP_MUL = "mul"
OP_ADD = "add"
OP_SUB = "sub"
OP_DIV = "div"          # divide squad by N (÷2, ÷4) — devastating at low squad
OP_WEAPON = "weapon"
OP_GRENADE = "grenade"


# Translucent op colors so the gate reads even against bright backgrounds.
OP_COLORS: dict[str, tuple[float, float, float, float]] = {
    OP_MUL:     (0.18, 0.78, 0.40, 0.78),    # green
    OP_ADD:     (0.20, 0.55, 0.95, 0.78),    # blue
    OP_SUB:     (0.85, 0.30, 0.30, 0.78),    # red
    OP_DIV:     (0.85, 0.30, 0.65, 0.82),    # magenta — distinguishes from SUB
    OP_WEAPON:  (1.00, 0.74, 0.20, 0.82),    # yellow
    OP_GRENADE: (0.20, 0.85, 0.92, 0.80),    # cyan — feels distinct from the squad/weapon ops
}


# --- gate widget ---------------------------------------------------------

class Gate(Widget):
    """One gate panel — translucent op-tinted rectangle + label."""

    def __init__(self, op: str, value, label_text: str, **kwargs):
        super().__init__(**kwargs)
        self.op = op
        self.value = value
        self.label_text = label_text
        self.consumed = False        # True once a gate in the pair fires
        self.missed = False          # True if pair scrolled past without entering
        self.selected = False        # True if THIS gate was the one picked

        color = OP_COLORS[op]
        with self.canvas.before:
            self._color = Color(*color)
            self._bg = RoundedRectangle(radius=[dp(12)])
            self._border_color = Color(1, 1, 1, 0.85)
            self._border = Line(rounded_rectangle=[0, 0, 0, 0, dp(12)], width=2.0)
            # A second "selection glow" border drawn underneath; invisible
            # by default, lit up on selection so the chosen gate reads from
            # a glance even after the hero has scrolled past it.
            self._glow_color = Color(1, 1, 1, 0.0)
            self._glow = Line(rounded_rectangle=[0, 0, 0, 0, dp(14)], width=6.0)

        self._label = Label(
            text=label_text, font_size=sp(30), bold=True, color=(1, 1, 1, 1),
            halign="center", valign="middle",
        )
        self.add_widget(self._label)
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = [self.x, self.y, self.width, self.height, dp(12)]
        # Glow sits slightly outside the gate so it reads as a halo.
        self._glow.rounded_rectangle = [
            self.x - dp(4), self.y - dp(4),
            self.width + dp(8), self.height + dp(8), dp(14),
        ]
        self._label.pos = self.pos
        self._label.size = self.size
        self._label.text_size = self.size

    def mark_consumed(self, dim: bool = True) -> None:
        """Mark this gate as part of a resolved pair.

        The *non*-picked gate in a pair fades to 30 % so the player sees the
        choice was made; the picked gate uses `mark_selected()` instead so
        it stays vivid and gains a glow.
        """
        self.consumed = True
        if dim:
            self._color.a = 0.30      # fade so the player sees they took it
            self._border_color.a = 0.30

    def mark_selected(self) -> None:
        """Highlight this gate as the player's pick — bright glow + bigger
        label so the choice is unambiguous from any distance."""
        self.consumed = True
        self.selected = True
        # Keep / boost the panel color and add a contrasting yellow halo.
        self._color.a = min(1.0, OP_COLORS[self.op][3] + 0.18)
        self._border_color.rgba = (1.0, 0.92, 0.35, 1.0)
        self._glow_color.rgba = (1.0, 0.92, 0.35, 0.85)
        # Slightly larger label so even at small panel size the picked gate
        # reads "this one".
        try:
            from kivy.metrics import sp as _sp
            self._label.font_size = _sp(34)
            self._label.bold = True
        except Exception:
            pass


# --- spawner -------------------------------------------------------------

class GateSpawner:
    """Spawns gate pairs at a fixed distance interval."""

    INTERVAL_PX = 600.0          # distance between pairs
    GATE_HEIGHT = 88.0
    GATE_GAP_PX = 64.0           # gap between the two gates so the choice
                                 # reads visually — was 24 px, which looked
                                 # like one wide panel from a distance
    LATERAL_MARGIN = 18.0        # gap between outer gate edge and rail

    # Default allowed ops + weapons — game.GameScreen overrides per level (M9).
    DEFAULT_OPS = [OP_MUL, OP_ADD, OP_SUB, OP_DIV, OP_WEAPON, OP_GRENADE]
    DEFAULT_WEAPONS = ["rifle", "shotgun", "sniper"]
    # "Pity gate" floor — after this many consecutive misses, the spawner
    # forces the next pair to contain at least one MUL or ADD (safe choice).
    # Keeps a player who missed gates by RNG from falling into an
    # unrecoverable squad=1 spiral.
    PITY_AFTER_MISSES = 2

    def __init__(self, controller: "GateController", seed: int | None = None):
        self.controller = controller
        self._rng = random.Random(seed)
        self.interval_px = self.INTERVAL_PX
        # First gate should arrive before the first wave of enemies reaches
        # the squad — otherwise late-world levels are unplayable at squad=1.
        # 200 px = ~0.55 s of scroll; gate then takes ~1.3 s to travel to the
        # hero, so it lands at ~1.85 s — just under the first attrition.
        self._next_distance = 200.0
        self.allowed_ops: list[str] = list(self.DEFAULT_OPS)
        self.allowed_weapons: list[str] = list(self.DEFAULT_WEAPONS)
        # Pity-gate tracking: GateController updates this counter whenever a
        # pair scrolls past with neither gate consumed (miss).
        self.consecutive_misses = 0
        # Per-level cap on grenade gates so they stay a rare resource.
        # Game.GameScreen sets this from the level config on entry, and
        # `reset_per_level()` zeros the counter that tracks how many have
        # spawned so far.
        self.max_grenade_gates = 0
        self.grenade_gates_spawned = 0

    def reset_per_level(self) -> None:
        """Call at level start. Resets per-run counters that track
        rare-resource emission and the pity-gate floor."""
        self.grenade_gates_spawned = 0
        self.consecutive_misses = 0

    def tick(self, distance: float, x_min: float, x_max: float, y_top: float) -> bool:
        """Spawn a pair when the run has advanced past the next interval.

        Returns True if a pair was spawned this tick (useful for tests).
        """
        if distance < self._next_distance:
            return False
        self._next_distance += self.interval_px

        road_w = x_max - x_min
        gate_w = (road_w - self.LATERAL_MARGIN * 2 - self.GATE_GAP_PX) * 0.5
        gate_h = self.GATE_HEIGHT
        left_x = x_min + self.LATERAL_MARGIN
        right_x = left_x + gate_w + self.GATE_GAP_PX

        # Pity floor: if the player has missed the last few pairs, force at
        # least one safe op (MUL or ADD) so they can recover.
        force_safe = self.consecutive_misses >= self.PITY_AFTER_MISSES
        if force_safe:
            safe_pool = [op for op in (OP_MUL, OP_ADD) if op in self.allowed_ops]
            if not safe_pool:
                safe_pool = [OP_MUL, OP_ADD]   # never let pity become a no-op
            op_a = self._rng.choice(safe_pool)
            # Reuse the regular value-pick path by going through _pick_op
            # with a constrained op list.
            saved_ops = self.allowed_ops
            self.allowed_ops = [op_a]
            op_a, value_a, label_a = self._pick_op(exclude_op=None)
            self.allowed_ops = saved_ops
            # Reset the counter so we don't keep stacking pity gates.
            self.consecutive_misses = 0
        else:
            op_a, value_a, label_a = self._pick_op(exclude_op=None)
        op_b, value_b, label_b = self._pick_op(exclude_op=op_a)
        self.controller.spawn_pair(
            (left_x,  y_top, gate_w, gate_h, op_a, value_a, label_a),
            (right_x, y_top, gate_w, gate_h, op_b, value_b, label_b),
        )
        return True

    def _pick_op(self, exclude_op: str | None):
        """Pick an op + value + display label. Avoids a pair with two
        identical ops, which would be a non-choice for the player.

        Reward magnitudes are intentionally tight: ×2 only (no ×3), ADD
        capped at 7, SUB up to 7, GRENADE always 1. The cumulative effect
        across many gates makes the level passable; no single gate carries
        the run.

        `grenade` is hard-capped per level via `max_grenade_gates` so
        grenades stay a rare resource. Once the cap is hit, the spawner
        retries with grenade removed from the pool.
        """
        op_table = {
            OP_MUL:     ([2],              lambda v: "x{}".format(v)),
            OP_ADD:     ([3, 5, 7],        lambda v: "+{}".format(v)),
            OP_SUB:     ([2, 3, 5, 7],     lambda v: "-{}".format(v)),
            OP_DIV:     ([2, 4],           lambda v: "/{}".format(v)),
            OP_WEAPON:  (self.allowed_weapons or self.DEFAULT_WEAPONS,
                         lambda v: v.upper()),
            OP_GRENADE: ([1],              lambda v: "GRENADE x{}".format(v)),
        }
        allowed = [op for op in self.allowed_ops if op != exclude_op and op in op_table]
        if not allowed:
            allowed = [op for op in self.DEFAULT_OPS if op != exclude_op]
        # Grenade cap enforcement.
        if self.grenade_gates_spawned >= self.max_grenade_gates and OP_GRENADE in allowed:
            allowed = [op for op in allowed if op != OP_GRENADE] or allowed
        op = self._rng.choice(allowed)
        values, fmt = op_table[op]
        value = self._rng.choice(values)
        if op == OP_GRENADE:
            self.grenade_gates_spawned += 1
        return op, value, fmt(value)


# --- controller ----------------------------------------------------------

class GateController:
    """Tracks live gate pairs and runs the pass-through tick."""

    DESPAWN_BELOW_PX = 80.0    # pair removed once it scrolls this far past the floor

    def __init__(self, stage_widget):
        self.stage = stage_widget
        self.pairs: list[list[Gate]] = []
        self.spawned_total = 0
        self.applied_total = 0
        self.missed_total = 0

    # GameScreen calls this via GateSpawner.tick.
    def spawn_pair(self, spec_a: tuple, spec_b: tuple) -> None:
        def _make(spec: tuple) -> Gate:
            x, y, w, h, op, value, label = spec
            gate = Gate(op, value, label,
                        size_hint=(None, None), size=(w, h), pos=(x, y))
            self.stage.add_widget(gate)
            return gate

        self.pairs.append([_make(spec_a), _make(spec_b)])
        self.spawned_total += 1

    def update(self, dt: float, scroll_speed: float,
               hero_cx: float, hero_cy: float, on_apply, on_miss=None) -> None:
        """Scroll all gates down; fire `on_apply(gate)` on cross-through.

        Optional `on_miss()` is invoked once per pair that scrolls past
        without the hero entering either gate (used by the pity-gate
        spawner so two missed pairs in a row force a safe next gate).
        """
        drop = scroll_speed * dt
        to_remove: list[list[Gate]] = []
        for pair in self.pairs:
            for g in pair:
                g.y -= drop

            pair_consumed = any(g.consumed for g in pair)
            if not pair_consumed:
                # The pair's logical Y line is the bottom edge — the moment
                # the gate panel has scrolled to the hero's row.
                pair_line_y = pair[0].y + pair[0].height * 0.5
                if pair_line_y <= hero_cy + pair[0].height * 0.25:
                    # Pass-through window. Find which gate (if any) the hero
                    # is inside.
                    picked: Gate | None = None
                    for g in pair:
                        if g.x <= hero_cx <= g.x + g.width:
                            picked = g
                            break
                    if picked is not None:
                        picked.mark_selected()
                        # Fade the *other* gate so the picked one is the
                        # obvious one — at a glance the player can see which
                        # they took even after both have scrolled past.
                        for g in pair:
                            if g is not picked:
                                g.mark_consumed(dim=True)
                        self.applied_total += 1
                        on_apply(picked)
                        # Reset the pity counter — the player succeeded.
                        # (Spawner is the canonical owner; controller writes
                        # through it so the next spawn knows about the success.)
                    else:
                        # Hero went through the gap between the two gates
                        # (or off to one side). Pair is missed.
                        for g in pair:
                            g.mark_consumed(dim=True)
                        self.missed_total += 1
                        if on_miss is not None:
                            on_miss()

            if pair[0].y + pair[0].height < self.stage.y - self.DESPAWN_BELOW_PX:
                to_remove.append(pair)

        for pair in to_remove:
            for g in pair:
                if g.parent:
                    g.parent.remove_widget(g)
            self.pairs.remove(pair)

    def active_lane_centers(self, hero_cy: float) -> list[float]:
        """X centers of the nearest *unconsumed* pair above the hero.

        Used by `game.GameScreen` to drive `lane_gravity_target` — once a
        pair is approaching, the hero softly snaps toward the nearer gate
        whenever the player isn't actively dragging.
        """
        nearest = None
        nearest_y = float("inf")
        for pair in self.pairs:
            if all(g.consumed for g in pair):
                continue
            pair_y = pair[0].y
            if pair_y > hero_cy and pair_y < nearest_y:
                nearest_y = pair_y
                nearest = pair
        if nearest is None:
            return []
        return [g.x + g.width * 0.5 for g in nearest]

    def clear(self) -> None:
        """Drop all live gate widgets — called on level end / screen leave."""
        for pair in self.pairs:
            for g in pair:
                if g.parent:
                    g.parent.remove_widget(g)
        self.pairs.clear()
