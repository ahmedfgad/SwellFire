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
    * `OP_WEAPON` <wid>     — switch when the candidate is not a downgrade

M8 will render the squad as a Mesh-batched runner crowd; M7's
gate effects already drive the integer squad_count so the renderer
just has to follow it.
"""

from __future__ import annotations

import random

from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivy.graphics import Color, Line, RoundedRectangle, PushMatrix, PopMatrix, Scale
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from . import graphics


# --- op tags -------------------------------------------------------------

OP_MUL = "mul"
OP_ADD = "add"
OP_SUB = "sub"
OP_DIV = "div"          # divide squad by N (÷2, ÷4) — devastating at low squad
OP_WEAPON = "weapon"
OP_GRENADE = "grenade"
# Consumable-bonus gate ops (each grants one charge of the matching booster,
# collected now and used later — same model as the grenade gate). shield is
# shop-only and is intentionally NOT a gate op.
OP_REINFORCE = "reinforce"
OP_FREEZE = "freeze"
OP_OVERDRIVE = "overdrive"
OP_MAGNET = "magnet"

# Squad-altering "math" ops vs one-off "bonus" pickups. A gate pair is drawn
# entirely from one group: an equation/atomic-math gate always faces another
# math gate (a real ×2-vs-+5 decision), and bonus gates (weapon + the
# consumable boosters) form their own occasional bonus pairs — never a
# math-gate-vs-trivial-gate non-choice.
MATH_OPS = (OP_MUL, OP_ADD, OP_SUB, OP_DIV)
BONUS_OPS = (OP_WEAPON, OP_GRENADE, OP_REINFORCE, OP_FREEZE,
             OP_OVERDRIVE, OP_MAGNET)
# Consumable bonus ops that grant a charge of a booster, with the gate label.
# (weapon is handled separately — its value is a weapon id, not a charge.)
CONSUMABLE_BONUS = {
    OP_GRENADE:   "GRENADE",
    OP_REINFORCE: "REINFORCE",
    OP_FREEZE:    "FREEZE",
    OP_OVERDRIVE: "OVERDRIVE",
    OP_MAGNET:    "MAGNET",
}

# Leading-operator glyphs — proper math symbols read far faster than the ASCII
# "x", "-", "/" the label strings carry. The label_text stays ASCII (synced to
# the multiplayer client, used by gameplay logic); only the *display* is pretty.
OP_GLYPH = {OP_MUL: "×", OP_ADD: "+", OP_SUB: "−", OP_DIV: "÷"}
# In-expression ASCII operator -> display glyph.
_EXPR_GLYPH = {"+": "+", "-": "−", "*": "×", "/": "÷"}
# Operators get a single bright accent so the eye segments operands from
# operators instantly; operands stay white.
OP_ACCENT_HEX = "ffcf33"                       # amber, for markup
OP_ACCENT_RGBA = (1.0, 0.81, 0.20, 1.0)        # amber, for plain Color
_OUTLINE_RGBA = (0.0, 0.0, 0.0, 1.0)           # dark outline for legibility


# Translucent op colors so the gate reads even against bright backgrounds.
OP_COLORS: dict[str, tuple[float, float, float, float]] = {
    OP_MUL:     (0.18, 0.78, 0.40, 0.78),    # green
    OP_ADD:     (0.20, 0.55, 0.95, 0.78),    # blue
    OP_SUB:     (0.85, 0.30, 0.30, 0.78),    # red
    OP_DIV:     (0.85, 0.30, 0.65, 0.82),    # magenta — distinguishes from SUB
    OP_WEAPON:  (1.00, 0.74, 0.20, 0.82),    # yellow
    OP_GRENADE: (0.20, 0.85, 0.92, 0.80),    # cyan — feels distinct from the squad/weapon ops
    OP_REINFORCE: (0.40, 0.90, 0.45, 0.82),  # green — squad recovery
    OP_FREEZE:    (0.45, 0.80, 1.00, 0.82),  # icy blue
    OP_OVERDRIVE: (1.00, 0.55, 0.20, 0.82),  # orange — rapid fire
    OP_MAGNET:    (0.80, 0.45, 0.95, 0.82),  # purple — economy
}


# --- gate widget ---------------------------------------------------------

class Gate(Widget):
    """One gate panel — translucent op-tinted rectangle + label."""

    # Drives the emphasis pop (see emphasize()). Animating a scale transform
    # instead of font_size means the text is laid out once and never reflows.
    emph_scale = NumericProperty(1.0)

    def __init__(self, op: str, value, label_text: str, **kwargs):
        super().__init__(**kwargs)
        self.op = op
        self.value = value
        self.label_text = label_text
        self.consumed = False        # True once a gate in the pair fires (HOST/p1's view)
        self.missed = False          # True if pair scrolled past without entering
        self.selected = False        # True if THIS gate was the one picked (p1)
        # M13 — versus. Independent per-player flags so each player's
        # interaction with the gate doesn't affect the other. p1 = host,
        # p2 = client. ``consumed_by_p2`` was previously
        # ``opponent_consumed``; renamed for symmetry. Visual marking
        # on the host's widget still tracks p1; the per-player snapshot
        # sends p2's flags separately so the client can render its own
        # consumed/selected visual independently.
        self.consumed_by_p2 = False
        self.selected_by_p2 = False

        color = OP_COLORS[op]
        with self.canvas.before:
            # Uniform pop transform (origin set to the gate centre in _sync).
            PushMatrix()
            self._scale = Scale(x=1.0, y=1.0, z=1.0)
            self._color = Color(*color)
            self._bg = RoundedRectangle(radius=[dp(12)])
            self._border_color = Color(1, 1, 1, 0.85)
            self._border = Line(rounded_rectangle=[0, 0, 0, 0, dp(12)], width=2.0)
            # A second "selection glow" border drawn underneath; invisible
            # by default, lit up on selection so the chosen gate reads from
            # a glance even after the hero has scrolled past it.
            self._glow_color = Color(1, 1, 1, 0.0)
            self._glow = Line(rounded_rectangle=[0, 0, 0, 0, dp(14)], width=6.0)

        with self.canvas.after:
            PopMatrix()
        self.bind(emph_scale=self._on_emph_scale)

        # Emphasis pulse fires once as the pair nears the decision zone.
        self._emphasized = False

        # Math gates render as two lines — a big operator glyph on top and
        # the value/expression below — so "which operation" reads instantly
        # and only the arithmetic is left to the player. Bonus gates
        # (weapon / grenade) are not arithmetic, so they render as one
        # centered name label.
        self._is_math = op in MATH_OPS
        self._factor_label = None
        if self._is_math:
            self._op_label = Label(
                text=OP_GLYPH.get(op, "?"), font_size=sp(40), bold=True,
                color=OP_ACCENT_RGBA, halign="center", valign="middle",
                outline_width=2, outline_color=_OUTLINE_RGBA,
            )
            body = self._strip_leading_op(label_text)
            self._expr_label = Label(
                text=self._pretty_expr(body), markup=True,
                font_size=self._expr_font_size(body), bold=True,
                color=(1, 1, 1, 1), halign="center", valign="middle",
                outline_width=2, outline_color=_OUTLINE_RGBA,
            )
            self.add_widget(self._op_label)
            self.add_widget(self._expr_label)
            self._labels = [self._op_label, self._expr_label]
        elif op in CONSUMABLE_BONUS:
            # Consumable reward gate: name on top, "xN" factor on its own line
            # below (amber, like the math accent) — never cram onto one line.
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
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    # --- display helpers -------------------------------------------------

    @staticmethod
    def _strip_leading_op(label_text: str) -> str:
        """Drop the leading op symbol the spawner prepends ("x", "+", "-",
        "/") so only the value/expression remains; the operator is shown
        separately as the big top glyph."""
        if label_text and label_text[0] in "x+-/":
            return label_text[1:]
        return label_text

    @staticmethod
    def _pretty_expr(body: str) -> str:
        """Turn an ASCII expression body into spaced, glyph-and-color markup.

        Strips one redundant outer paren wrap, swaps ``* / -`` for ``× ÷ −``,
        spaces operands apart, and tints every operator amber so the eye
        segments structure at a glance. Operands stay white (the Label's base
        color). ``+5`` -> ``5``; ``(1+4+3)`` -> ``1 + 4 + 3``;
        ``((4+2-4)*1)`` -> ``( 4 + 2 − 4 ) × 1``.
        """
        if len(body) >= 2 and body[0] == "(" and body[-1] == ")":
            depth = 0
            wraps = True
            for i, ch in enumerate(body):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0 and i != len(body) - 1:
                        wraps = False
                        break
            if wraps:
                body = body[1:-1]
        out = []
        for ch in body:
            if ch in _EXPR_GLYPH:
                out.append(" [color={}][b]{}[/b][/color] ".format(
                    OP_ACCENT_HEX, _EXPR_GLYPH[ch]))
            elif ch in "()":
                out.append(" {} ".format(ch))
            else:
                out.append(ch)
        return " ".join("".join(out).split())

    @staticmethod
    def _expr_font_size(body: str):
        n = len(body)
        if n <= 2:
            return sp(34)
        if n <= 5:
            return sp(30)
        if n <= 9:
            return sp(26)
        return sp(22)

    def _sync(self, *_):
        self._scale.origin = (self.center_x, self.center_y)
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = [self.x, self.y, self.width, self.height, dp(12)]
        # Glow sits slightly outside the gate so it reads as a halo.
        self._glow.rounded_rectangle = [
            self.x - dp(4), self.y - dp(4),
            self.width + dp(8), self.height + dp(8), dp(14),
        ]
        if self._is_math:
            # Operator on the top band, expression on the bottom band.
            op_h = self.height * 0.50
            self._op_label.pos = (self.x, self.y + self.height * 0.46)
            self._op_label.size = (self.width, op_h)
            self._op_label.text_size = (self.width, op_h)
            expr_h = self.height * 0.46
            self._expr_label.pos = (self.x, self.y + self.height * 0.02)
            self._expr_label.size = (self.width, expr_h)
            self._expr_label.text_size = (self.width, expr_h)
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

    def _on_emph_scale(self, _widget, value):
        self._scale.x = value
        self._scale.y = value

    def emphasize(self) -> None:
        """One-shot attention cue as the pair enters the decision zone: a
        gentle scale pop. Fires once per gate. Scaling (not font_size) means
        the text never reflows/wraps when it grows."""
        if self._emphasized or self.consumed:
            return
        self._emphasized = True
        (Animation(emph_scale=1.18, duration=0.22, t="out_quad")
         + Animation(emph_scale=1.0, duration=0.22, t="in_quad")).start(self)

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
            for lbl in self._labels:
                lbl.opacity = 0.45

    def mark_selected(self) -> None:
        """Highlight this gate as the player's pick — bright glow + bigger
        label so the choice is unambiguous from any distance."""
        self.consumed = True
        self.selected = True
        # Keep / boost the panel color and add a contrasting yellow halo.
        self._color.a = min(1.0, OP_COLORS[self.op][3] + 0.18)
        self._border_color.rgba = (1.0, 0.92, 0.35, 1.0)
        self._glow_color.rgba = (1.0, 0.92, 0.35, 0.85)
        # Cancel any in-flight emphasis pulse, then keep the picked gate
        # enlarged via the scale transform — NOT font_size, which would reflow
        # and wrap the label text (see emphasize()).
        Animation.cancel_all(self, "emph_scale")
        self.emph_scale = 1.14


# --- spawner -------------------------------------------------------------

class GateSpawner:
    """Spawns gate pairs at a fixed distance interval."""

    INTERVAL_PX = 600.0          # distance between pairs
    GATE_HEIGHT = 112.0          # taller so the two-line op/expression layout
                                 # and the larger type read at a glance
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
    # Chance a (non-pity) pair is a weapon/grenade "bonus" pair rather than a
    # math pair — kept low so most pairs are mental-math decisions. Bonus
    # pairs only spawn when ≥2 distinct bonus choices are actually available
    # (and within the grenade cap); otherwise the pair falls back to math.
    BONUS_PAIR_CHANCE = 0.12

    def __init__(self, controller: "GateController", seed: int | None = None):
        self.controller = controller
        self._rng = random.Random(seed)
        # interval_px and _next_distance live in the (density-scaled) scroll
        # distance domain — see graphics.world_scale(). Scaling keeps gate
        # cadence (gates per level) identical to the density-1.0 build.
        # game.GameScreen overrides interval_px from the level cfg (already
        # scaled at that assignment site).
        self.interval_px = graphics.ws(self.INTERVAL_PX)
        # First gate should arrive before the first wave of enemies reaches
        # the squad — otherwise late-world levels are unplayable at squad=1.
        # 200 px = ~0.55 s of scroll; gate then takes ~1.3 s to travel to the
        # hero, so it lands at ~1.85 s — just under the first attrition.
        self._next_distance = graphics.ws(200.0)
        self.allowed_ops: list[str] = list(self.DEFAULT_OPS)
        self.allowed_weapons: list[str] = list(self.DEFAULT_WEAPONS)
        # World tier (1..6) drives the *equation difficulty* on gate labels.
        # The numeric effect is unchanged — only the *expression* shown to
        # the player gets harder per world (W1 = "+5", W6 = "+(2*3-1)").
        # game.py sets this from the level's world on entry. Default 1 = plain.
        self.world_tier = 1
        # Pity-gate tracking: GateController updates this counter whenever a
        # pair scrolls past with neither gate consumed (miss).
        self.consecutive_misses = 0
        # Per-level cap on grenade gates so they stay a rare resource.
        # Game.GameScreen sets this from the level config on entry, and
        # `reset_per_level()` zeros the counter that tracks how many have
        # spawned so far.
        self.max_grenade_gates = 0
        self.grenade_gates_spawned = 0
        self._pairs_spawned = 0   # pairs emitted this level (first-pair gain bias)

    def reset_per_level(self) -> None:
        """Call at level start. Resets per-run counters that track
        rare-resource emission and the pity-gate floor."""
        self.grenade_gates_spawned = 0
        self.consecutive_misses = 0
        self._pairs_spawned = 0

    def tick(self, distance: float, x_min: float, x_max: float, y_top: float) -> bool:
        """Spawn a pair when the run has advanced past the next interval.

        Returns True if a pair was spawned this tick (useful for tests).
        """
        if distance < self._next_distance:
            return False
        self._next_distance += self.interval_px

        road_w = x_max - x_min
        # Gate box height/gap/margins are world-px tuned at density 1.0; scale
        # them so the box matches its sp()-sized equation labels (which already
        # scale with density) — otherwise the two-line equation overflows a
        # fixed-px box on a Retina screen. No-op at density 1.0.
        lateral_margin = graphics.ws(self.LATERAL_MARGIN)
        gate_gap = graphics.ws(self.GATE_GAP_PX)
        gate_w = (road_w - lateral_margin * 2 - gate_gap) * 0.5
        gate_h = graphics.ws(self.GATE_HEIGHT)
        left_x = x_min + lateral_margin
        right_x = left_x + gate_w + gate_gap

        # Math ops always pair with math ops (a real ×2-vs-+5 decision);
        # weapon/grenade gates form their own occasional bonus pairs and never
        # sit opposite a math gate.
        math_pool = [op for op in self.allowed_ops if op in MATH_OPS]
        if len(math_pool) < 2:
            math_pool = [OP_MUL, OP_ADD, OP_SUB]

        # Pity floor: if the player has missed the last few pairs, force a
        # math pair with at least one safe op (MUL or ADD) so they recover.
        opening_pair = self._pairs_spawned == 0
        launch_pair = self._pairs_spawned < 3
        force_safe = (self.consecutive_misses >= self.PITY_AFTER_MISSES
                      or launch_pair)
        if force_safe:
            if launch_pair and OP_MUL in self.allowed_ops:
                # Three dependable launch multipliers let active players reach
                # sustainable firepower before formation pressure peaks. Only
                # the opener is x3; the next two use the regular x2 value.
                safe_pool = [OP_MUL]
            else:
                safe_pool = [op for op in (OP_MUL, OP_ADD) if op in self.allowed_ops] \
                    or [OP_MUL, OP_ADD]
            op_a, value_a, label_a = self._pick_op(exclude_op=None, allowed=safe_pool)
            if opening_pair and op_a == OP_MUL:
                value_a = 3
                label_a = self._equation_label(op_a, value_a)
            op_b, value_b, label_b = self._pick_op(exclude_op=op_a, allowed=math_pool)
            self.consecutive_misses = 0
        else:
            bonus_pair = None
            if self._rng.random() < self.BONUS_PAIR_CHANCE:
                bonus_pair = self._build_bonus_pair()
            if bonus_pair is not None:
                (op_a, value_a, label_a), (op_b, value_b, label_b) = bonus_pair
            else:
                op_a, value_a, label_a = self._pick_op(exclude_op=None, allowed=math_pool)
                op_b, value_b, label_b = self._pick_op(exclude_op=op_a, allowed=math_pool)
                if op_a in (OP_SUB, OP_DIV) and op_b in (OP_SUB, OP_DIV):
                    growth_ops = [op for op in (OP_MUL, OP_ADD) if op in math_pool]
                    if growth_ops:
                        op_a, value_a, label_a = self._pick_op(
                            exclude_op=op_b, allowed=growth_ops)
        self.controller.spawn_pair(
            (left_x,  y_top, gate_w, gate_h, op_a, value_a, label_a),
            (right_x, y_top, gate_w, gate_h, op_b, value_b, label_b),
        )
        self._pairs_spawned += 1
        return True

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

    def _build_bonus_pair(self):
        """Build two distinct weapon/grenade specs, or None if fewer than two
        bonus choices are available (e.g. one weapon and the grenade cap hit).

        Distinctness is by (op, value): weapon-vs-weapon with different ids is
        a real "which gun" choice; weapon-vs-grenade is "gun or a grenade".
        """
        candidates: list[tuple] = []
        # Consumable boosters — one charge each. Grenade keeps its per-level
        # cap; the others are uncapped (the per-pair rarity + shop economy
        # keep them scarce).
        for op, name in CONSUMABLE_BONUS.items():
            if op not in self.allowed_ops:
                continue
            if op == OP_GRENADE and self.grenade_gates_spawned >= self.max_grenade_gates:
                continue
            n = self._bonus_value(op)
            candidates.append((op, n, "{} x{}".format(name, n)))
        if OP_WEAPON in self.allowed_ops:
            for w in (self.allowed_weapons or self.DEFAULT_WEAPONS):
                candidates.append((OP_WEAPON, w, w.upper()))
        if len(candidates) < 2:
            return None
        a, b = self._rng.sample(candidates, 2)
        for spec in (a, b):
            if spec[0] == OP_GRENADE:
                self.grenade_gates_spawned += 1
        return a, b

    def _pick_op(self, exclude_op: str | None, allowed: "list[str] | None" = None):
        """Pick an op + value + display label from ``allowed`` (defaults to
        the spawner's full pool). Avoids repeating ``exclude_op`` so a pair is
        always a genuine choice. Math ops get an equation label; bonus ops a
        literal one.

        Reward magnitudes are intentionally tight: regular MUL is ×2 (the
        opening launch gate is the sole ×3), ADD scales from 3–7 in W1 to
        8–16 in W5/W6, SUB reaches 7, and DIV uses /2 or /4. Cumulative choices
        carry the run without making later random multipliers explosive.
        """
        if self.world_tier <= 2:
            add_values = [3, 5, 7]
        elif self.world_tier <= 4:
            add_values = [5, 8, 12]
        else:
            add_values = [8, 12, 16]
        op_table = {
            OP_MUL:     ([2],              lambda v: "x{}".format(v)),
            OP_ADD:     (add_values,       lambda v: "+{}".format(v)),
            OP_SUB:     ([2, 3, 5, 7],     lambda v: "-{}".format(v)),
            OP_DIV:     ([2, 4],           lambda v: "/{}".format(v)),
            OP_WEAPON:  (self.allowed_weapons or self.DEFAULT_WEAPONS,
                         lambda v: v.upper()),
            OP_GRENADE: ([1, 2, 3],        lambda v: "GRENADE x{}".format(v)),
        }
        pool = allowed if allowed is not None else self.allowed_ops
        cand = [op for op in pool if op != exclude_op and op in op_table]
        if not cand:
            cand = [op for op in pool if op in op_table] or [OP_MUL, OP_ADD]
        # Grenade cap enforcement (only matters if grenade is in the pool).
        if (self.grenade_gates_spawned >= self.max_grenade_gates
                and OP_GRENADE in cand and len(cand) > 1):
            cand = [op for op in cand if op != OP_GRENADE]
        op = self._rng.choice(cand)
        values, fmt = op_table[op]
        if op == OP_GRENADE:
            value = self._bonus_value(OP_GRENADE)
        else:
            value = self._rng.choice(values)
        if op == OP_GRENADE:
            self.grenade_gates_spawned += 1
        # M14 — for value-bearing ops (mul/add/sub/div) replace the plain
        # number with an expression that *evaluates* to the same value.
        # The numeric effect of the gate is unchanged; only the label
        # gets harder to parse as the player advances through worlds.
        # WEAPON / GRENADE stay literal — those gate's "value" is a tag
        # (weapon id / 1) not a number a player would do arithmetic on.
        if op in (OP_MUL, OP_ADD, OP_SUB, OP_DIV):
            label = self._equation_label(op, value)
        else:
            label = fmt(value)
        return op, value, label

    # --- equation-label generator (M14) ---------------------------------

    def _equation_label(self, op: str, value: int) -> str:
        """Wrap ``value`` in an expression of increasing complexity based
        on ``self.world_tier``.

        The expression's *result* equals ``value`` so all downstream
        gate-effect code (squad multiplication, addition, etc.) keeps
        working unchanged — only the visible label gets longer. W1
        prints the raw number; W6 prints multi-op compositions like
        ``+(2*3-1)``.
        """
        op_sym = {OP_MUL: "x", OP_ADD: "+", OP_SUB: "-", OP_DIV: "/"}[op]
        tier = self.world_tier
        if tier <= 1:
            return "{}{}".format(op_sym, value)
        expr = self._compose_expression(value, tier)
        if expr is None:
            return "{}{}".format(op_sym, value)
        # Wrap in parens so the op symbol still reads left-of-expression.
        return "{}({})".format(op_sym, expr)

    def _compose_expression(self, target: int, tier: int) -> str | None:
        """Build a small arithmetic expression that evaluates to ``target``.

        Difficulty (tier):
            2 — single two-operand op (a+b, a-b, a*b)
            3 — adds division-friendly pairs (a*b, a*b/c)
            4 — three-term mixes (a+b-c, a*b+c)
            5 — four-term mixes
            6 — four-term + parenthesised inner
        """
        rng = self._rng
        if target == 0:
            return None
        # tier 2: two-operand decompositions
        if tier == 2:
            forms = []
            for a in range(1, target + 1):
                forms.append(("+", a, target - a))
            for a in range(target + 1, target + 6):
                forms.append(("-", a, a - target))
            # only multiplicative if target factorises cleanly
            for a in range(2, target + 1):
                if target % a == 0 and a != target:
                    forms.append(("*", a, target // a))
            forms = [f for f in forms
                     if 1 <= f[1] <= 9 and 1 <= f[2] <= 9]
            if not forms:
                return None
            op_sym, a, b = rng.choice(forms)
            return "{}{}{}".format(a, op_sym, b)
        # tier 3: prefer mul where possible, else add
        if tier == 3:
            options = []
            for a in range(2, 10):
                if target % a == 0 and 1 <= target // a <= 9 and a != target:
                    options.append("{}*{}".format(a, target // a))
            for a in range(1, min(target, 9)):
                b = target - a
                if 1 <= b <= 9:
                    options.append("{}+{}".format(a, b))
            for a in range(target + 1, target + 8):
                b = a - target
                if 1 <= a <= 12 and 1 <= b <= 9:
                    options.append("{}-{}".format(a, b))
            if not options:
                return None
            return rng.choice(options)
        # tier 4: three-term mixes (a+b-c, a*b-c, a+b*c)
        if tier == 4:
            forms = []
            for _ in range(80):
                a, b, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(1, 9)
                if a + b - c == target and a + b - c > 0:
                    forms.append("{}+{}-{}".format(a, b, c))
                if a * b - c == target and a * b - c > 0 and a * b <= 81:
                    forms.append("{}*{}-{}".format(a, b, c))
                if a + b * c == target and b * c <= 81:
                    forms.append("{}+{}*{}".format(a, b, c))
            if not forms:
                return self._compose_expression(target, 3)
            return rng.choice(forms)
        # tier 5: four-term mixes
        if tier == 5:
            forms = []
            for _ in range(120):
                a, b, c, d = (rng.randint(1, 9), rng.randint(2, 9),
                              rng.randint(1, 9), rng.randint(1, 6))
                if a + b * c - d == target and 0 < a + b * c - d:
                    forms.append("{}+{}*{}-{}".format(a, b, c, d))
                if a * b + c - d == target and 0 < a * b + c - d:
                    forms.append("{}*{}+{}-{}".format(a, b, c, d))
            if not forms:
                return self._compose_expression(target, 4)
            return rng.choice(forms)
        # tier 6+: include a parenthesised sub-expression
        forms = []
        for _ in range(160):
            a, b, c, d = (rng.randint(2, 9), rng.randint(2, 9),
                          rng.randint(1, 9), rng.randint(1, 6))
            inner = a + b
            if (inner - c) * d == target and 0 < (inner - c):
                forms.append("({}+{}-{})*{}".format(a, b, c, d))
            if a * (b + c) - d == target and (b + c) <= 18:
                forms.append("{}*({}+{})-{}".format(a, b, c, d))
            if a + b * (c - d) == target and (c - d) > 0:
                forms.append("{}+{}*({}-{})".format(a, b, c, d))
        if not forms:
            return self._compose_expression(target, 5)
        return rng.choice(forms)


# --- controller ----------------------------------------------------------

class GateController:
    """Tracks live gate pairs and runs the pass-through tick."""

    DESPAWN_BELOW_PX = 80.0    # pair removed once it scrolls this far past the floor
    EMPHASIZE_LEAD = 2.0       # gate-heights above the hero at which a pair's
                               # approach pulse fires

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
                # Approach cue: once the pair drops within a short lead of the
                # hero, pulse each gate's glyph so the eye lands on the choice
                # right as it matters. emphasize() self-guards to fire once.
                lead = pair[0].y - hero_cy
                if -pair[0].height <= lead <= pair[0].height * self.EMPHASIZE_LEAD:
                    for g in pair:
                        g.emphasize()
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

            if pair[0].y + pair[0].height < self.stage.y - graphics.ws(self.DESPAWN_BELOW_PX):
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
