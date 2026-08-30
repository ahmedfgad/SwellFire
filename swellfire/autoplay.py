"""autoplay.py — Swellfire auto-player (M12).

Ported from CoinTex's autoplay.py with the genre retargeted:

* CoinTex was 2-D (the player walked freely in a grid), so the GA searched
  over (x, y) target points and fitness was "collect coins / avoid monsters."
* Swellfire is effectively 1-D — the world auto-scrolls vertically, the
  hero only steers horizontally — so the solution space is just a target
  fraction ``f`` in ``[0, 1]`` across the road.

Phase 1 objectives: steer through the gate that strengthens the squad the
most, and deliberately miss a pair when *both* gates would weaken it.
Enemy avoidance and coin pursuit are intentionally NOT objectives — dodging
monsters sometimes forced the hero off a strengthening gate onto a weakening
one, and the squad's auto-fire clears enemies anyway, so the agent steers
purely on gate selection. No boosters are activated in this phase.

The structure is the same as CoinTex: ``sense()`` snapshots the world,
``_decide()`` picks the one attractor for the current gate pair, ``fitness()``
scores a candidate target against it, and ``AutoPlayer`` runs a small GA in a
daemon thread — seeded each tick with structured candidates (gate centers, the
gap, the previous target) so the optimum is always evaluated — that
re-evaluates a few times per second.

Tuning lives in the user's save (``ga_style`` and ``ga_speed``) and is
applied by ``apply_auto_settings`` — same shape as CoinTex so the existing
AutoPlayerScreen wires up without modification.
"""

from __future__ import annotations

import math
import random
import threading
import time

from kivy.clock import Clock

from . import gates


# How often the GA re-decides. Overridden by apply_auto_settings().
RETARGET_DELAY = 0.15

# --- mirrors of game.py constants ------------------------------------------
# autoplay.py is imported by game.py, so a real `import game` here is circular.
# Keep these in sync with game.py (SCROLL_SPEED_PX_PER_SEC, AUTO_HERO_MAX_SPEED,
# MAX_SQUAD). They are used for the reachability model and the gate-outcome cap.
SCROLL_SPEED = 360.0          # px/sec the world scrolls toward the hero
HERO_LAT_SPEED = 1800.0       # px/sec max sideways slide in auto mode
MAX_SQUAD = 100               # squad_count ceiling
GATE_HEIGHT = 112.0           # gate panel height (gates.py GATE_HEIGHT)

# Look-ahead windows (as a fraction of the stage height). Gates have the
# largest window because the player needs to start steering well before
# the pair arrives.
GATE_LOOKAHEAD = 1.4

# Fitness weights. Gate selection is the only steering objective in Phase 1.
GATE_WEIGHT = 600.0
MISS_WEIGHT = 300.0           # reward for sitting in the gap when both gates weaken

# Reward-peak widths (frac-of-road, std-dev of the Gaussian). The gate peak is
# ~a quarter-gate wide so the target settles near the center; the gap peak is
# tight because the deliberate-miss band between two gates is narrow (~9%).
GATE_SIGMA = 0.10
GAP_SIGMA = 0.035

# Centering only kicks in on open stretches (no pair in range), to keep the
# hero off the rails without fighting gate-centering.
CENTERING_WEIGHT = 1.5

# Anti-jitter: a mild pull toward the previously applied target so the
# stochastic GA commits instead of oscillating at ~6 Hz near a gate.
STICKINESS = 30.0
STICK_SIGMA = 0.06

# Sentinel delta for a lethal gate (outcome <= 0); never chosen as the attractor.
LETHAL_SENTINEL = -1e6

# Style multipliers — set by apply_auto_settings() from the user's save.
STYLE_GATE_MULT = 1.0
STYLE_SAFE_MULT = 1.0

# GA shape. The problem has only one value to find, so a smaller population
# than CoinTex's (200) is plenty and keeps the per-tick CPU cost negligible.
POPULATION = 80
PARENTS = 24
KEEP_BEST = 4
MUTATION_PROB = 0.30


def apply_auto_settings(style: str | None, speed: str | None) -> None:
    """Translate the AutoPlayerScreen's style + speed choices into the
    numbers the search uses. Same names as CoinTex so the existing
    settings screen and save schema work unchanged."""
    global STYLE_GATE_MULT, STYLE_SAFE_MULT, RETARGET_DELAY
    if style == "cautious":
        STYLE_GATE_MULT, STYLE_SAFE_MULT = 0.7, 1.7
    elif style == "aggressive":
        STYLE_GATE_MULT, STYLE_SAFE_MULT = 1.6, 0.6
    else:
        STYLE_GATE_MULT, STYLE_SAFE_MULT = 1.0, 1.0
    RETARGET_DELAY = {"slow": 0.25, "normal": 0.15, "fast": 0.08}.get(
        speed, 0.15,
    )


# --- sensing ---------------------------------------------------------------

def _frac_x(px: float, road_left: float, road_w: float) -> float:
    return (px - road_left) / max(1.0, road_w)


def sense(screen) -> dict | None:
    """Snapshot the world for one search iteration.

    Returns ``None`` when the level is over or the hero is unavailable —
    that's the agent thread's signal to exit.
    """
    if screen is None or screen._level_ended or screen.hero is None:
        return None
    stage = screen.stage
    if stage is None or stage.width <= 0:
        return None
    road_left = stage.x
    road_w = stage.width
    stage_h = max(1.0, stage.height)

    hero_cx = screen.hero.center_x
    hero_cy = screen.hero.center_y

    # --- nearest upcoming gate pair --------------------------------------
    next_pair = None
    if screen.gate_controller is not None:
        nearest_dy = float("inf")
        for pair in screen.gate_controller.pairs:
            if any(g.consumed for g in pair):
                continue
            pair_y = pair[0].center_y
            dy = pair_y - hero_cy
            if dy < 0 or dy > stage_h * GATE_LOOKAHEAD:
                continue
            if dy < nearest_dy:
                nearest_dy = dy
                left, right = sorted(pair, key=lambda g: g.x)
                next_pair = {
                    "left_x":  _frac_x(left.x,  road_left, road_w),
                    "left_w":  left.width  / road_w,
                    "left_op": left.op,
                    "left_val": left.value,
                    "right_x": _frac_x(right.x, road_left, road_w),
                    "right_w": right.width / road_w,
                    "right_op": right.op,
                    "right_val": right.value,
                    "dy_frac": dy / stage_h,
                }

    # Enemies and coins are intentionally not sensed in Phase 1 — the
    # autoplayer steers purely on gate selection. Enemy avoidance was
    # dropped because dodging sometimes forced the hero off a strengthening
    # gate onto a weakening one; the squad's auto-fire clears enemies and
    # picking the right gates carries the level.

    return {
        "hero_x_frac": _frac_x(hero_cx, road_left, road_w),
        "road_left":   road_left,
        "road_w":      road_w,
        "stage_h":     stage_h,
        "squad":       max(1, screen.squad_count),
        "gate":        next_pair,
    }


# --- gate outcome model -----------------------------------------------------

def _simulate_gate(squad: int, op: str, value) -> int:
    """Project the squad count after the hero passes through this gate.

    Mirrors game.py's `_on_apply_gate` so the agent values gates exactly as
    the game scores them — including the MAX_SQUAD cap (so a clamped ×N can't
    out-rank a +N at high squad) and the floor at 0 (so a lethal SUB/DIV is
    representable). Bonus gates (weapon/grenade/freeze/…) don't change the
    squad, so in Phase 1 they count as a delta of 0 — never preferred over a
    real squad gain, but harmless next to a weakening gate.
    """
    if op in gates.BONUS_OPS:
        return squad
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 0
    if op == gates.OP_MUL:
        return min(MAX_SQUAD, max(0, squad * v))
    if op == gates.OP_ADD:
        return min(MAX_SQUAD, squad + v)
    if op == gates.OP_SUB:
        return max(0, squad - v)
    if op == gates.OP_DIV:
        return max(0, squad // max(1, v))
    return squad


# --- decision + fitness ----------------------------------------------------

def _gauss(f: float, center: float, sigma: float) -> float:
    """Single-peaked weight: 1.0 at ``center``, smoothly decaying with
    distance. Used to pull the target toward a chosen point (a gate center
    or the gap) rather than treating a whole panel as a flat zone."""
    d = f - center
    return math.exp(-(d * d) / (2.0 * sigma * sigma))


def _reach(snapshot: dict, gate: dict, target_frac: float) -> float:
    """Fraction in [0, 1] of how reachable ``target_frac`` is before the
    pair arrives. 1.0 = comfortably reachable, 0.0 = impossible. Lets a
    reachable closer gate out-score an unreachable better one.
    """
    # The pair fires while its center is still ~0.75*GATE_HEIGHT above the
    # hero row, so the hero has a little less time than dy suggests.
    dy_px = gate["dy_frac"] * snapshot["stage_h"] - 0.75 * GATE_HEIGHT
    t = max(0.0, dy_px) / SCROLL_SPEED
    max_lat_px = HERO_LAT_SPEED * t
    needed_px = abs(target_frac - snapshot["hero_x_frac"]) * snapshot["road_w"]
    if needed_px <= 1.0:
        return 1.0
    return max(0.0, min(1.0, max_lat_px / needed_px))


def _decide(snapshot: dict | None) -> dict | None:
    """Pick the single attractor for this tick from the nearest gate pair.

    Returns ``None`` when no pair is in range (open running). Otherwise a
    dict ``{branch, desired_x, mag, sigma}`` describing where the hero
    should aim:

    * ``positive`` — a side strengthens the squad → that gate's center.
    * ``neutral``  — best a side can do is hold steady (e.g. a bonus gate
      opposite a weakening gate) → the neutral gate's center.
    * ``gap``      — both sides weaken (or both are lethal) → the gap
      between the gates, a deliberate miss (missing forgoes the effect but
      never reduces the squad).

    A gate whose outcome is <= 0 is *lethal* (passing it ends the run); it
    is never chosen, and forces the survivable side or the gap.
    """
    if snapshot is None:
        return None
    gate = snapshot["gate"]
    if gate is None:
        return None
    squad = snapshot["squad"]
    hero = snapshot["hero_x_frac"]

    left_c = gate["left_x"] + gate["left_w"] * 0.5
    right_c = gate["right_x"] + gate["right_w"] * 0.5
    gap_c = (gate["left_x"] + gate["left_w"] + gate["right_x"]) * 0.5

    left_out = _simulate_gate(squad, gate["left_op"], gate["left_val"])
    right_out = _simulate_gate(squad, gate["right_op"], gate["right_val"])
    left_lethal = left_out <= 0
    right_lethal = right_out <= 0
    left_delta = LETHAL_SENTINEL if left_lethal else left_out - squad
    right_delta = LETHAL_SENTINEL if right_lethal else right_out - squad

    # Death override: never aim at a lethal gate.
    if left_lethal and right_lethal:
        return {"branch": "gap", "desired_x": gap_c, "mag": 1.0,
                "sigma": GAP_SIGMA}
    if left_lethal:
        return _gate_decision(right_c, right_delta, squad)
    if right_lethal:
        return _gate_decision(left_c, left_delta, squad)

    best_delta = max(left_delta, right_delta)

    if best_delta > 0:
        # Strengthening side wins, but weight each side's gain by how
        # reachable it is so a reachable smaller gate beats an unreachable
        # bigger one. Ties → the gate closer to the hero (cheaper, steadier).
        left_eff = left_delta * _reach(snapshot, gate, left_c) if left_delta > 0 else -1.0
        right_eff = right_delta * _reach(snapshot, gate, right_c) if right_delta > 0 else -1.0
        if left_eff > right_eff:
            center, delta = left_c, left_delta
        elif right_eff > left_eff:
            center, delta = right_c, right_delta
        else:
            center = left_c if abs(left_c - hero) <= abs(right_c - hero) else right_c
            delta = best_delta
        return _gate_decision(center, delta, squad)

    if best_delta == 0:
        # Best a side can do is hold steady (neutral bonus vs weakening, or
        # bonus vs bonus). Aim at the neutral side; tie → closer.
        neutral = []
        if left_delta == 0:
            neutral.append(left_c)
        if right_delta == 0:
            neutral.append(right_c)
        center = min(neutral, key=lambda c: abs(c - hero))
        return {"branch": "neutral", "desired_x": center, "mag": 0.5,
                "sigma": GATE_SIGMA}

    # Both sides weaken (survivable). Deliberately thread the gap — unless
    # it's unreachable, in which case enter the less-bad gate (lesser evil).
    if _reach(snapshot, gate, gap_c) < 0.3:
        center = left_c if left_delta >= right_delta else right_c
        delta = max(left_delta, right_delta)
        return _gate_decision(center, delta, squad)
    return {"branch": "gap", "desired_x": gap_c, "mag": 1.0, "sigma": GAP_SIGMA}


def _gate_decision(center: float, delta: float, squad: int) -> dict:
    """Build a gate-aimed decision with magnitude scaled by relative gain."""
    mag = max(0.0, min(3.0, delta / max(1, squad)))
    branch = "positive" if delta > 0 else "neutral"
    if delta <= 0:
        # A weakening-but-survivable gate we're forced into: still pull
        # toward its center so the pass reads cleanly.
        mag = max(0.2, 1.0 + delta / max(1, squad))
        branch = "forced"
    return {"branch": branch, "desired_x": center, "mag": mag,
            "sigma": GATE_SIGMA}


def fitness(snapshot: dict | None, target_frac: float,
            decision: "dict | None" = None,
            prev_frac: "float | None" = None) -> float:
    """Score a candidate target X (as a fraction of the road). Bigger is
    better. ``decision`` (from ``_decide``) names the attractor for the
    current gate pair; ``prev_frac`` is the last applied target (for the
    anti-jitter stickiness term)."""
    if snapshot is None:
        return 0.0
    score = 0.0
    gate = snapshot["gate"]

    if gate is not None and decision is not None:
        urgency = 1.0 / (gate["dy_frac"] + 0.20)
        peak = _gauss(target_frac, decision["desired_x"], decision["sigma"])
        if decision["branch"] == "gap":
            # Deliberate miss: an avoidance behaviour, no reach factor.
            score += MISS_WEIGHT * STYLE_SAFE_MULT * urgency * peak
        else:
            reach = _reach(snapshot, gate, target_frac)
            score += (GATE_WEIGHT * STYLE_GATE_MULT * urgency
                      * decision["mag"] * peak * reach)
    else:
        # Open stretch: mild centering keeps the hero off the rails.
        score -= CENTERING_WEIGHT * abs(target_frac - 0.5)

    # (Enemy avoidance was removed — see sense(): the agent steers purely on
    # gate selection so it never gets pushed off a good gate by a monster.)

    # Anti-jitter: prefer staying near the previous commitment. Too small
    # to override a gate decision; enough to break near-ties.
    if prev_frac is not None:
        score += STICKINESS * _gauss(target_frac, prev_frac, STICK_SIGMA)

    return score


# --- driver ---------------------------------------------------------------

class AutoPlayer:
    """Daemon-thread genetic algorithm that drives the hero's target X.

    Same lifecycle as CoinTex's AutoPlayer: ``start()`` launches the
    thread, ``stop()`` joins it. The thread itself reads the screen's
    current state via ``sense()`` each tick — no shared mutable state.
    """

    def __init__(self, screen) -> None:
        self.screen = screen
        self._thread: threading.Thread | None = None
        self._stop = False
        self._prev_frac: float | None = None

    def start(self) -> None:
        self.stop()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        thread = self._thread
        if (thread is not None and thread.is_alive()
                and thread is not threading.current_thread()):
            thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        from kivy.app import App
        running = App.get_running_app()
        if running is not None and getattr(running, "state", None) is not None:
            apply_auto_settings(
                running.state.get_setting("ga_style"),
                running.state.get_setting("ga_speed"),
            )
        # Random fractions across the road as the initial population.
        population = [random.random() for _ in range(POPULATION)]
        while not self._stop:
            screen = self.screen
            snapshot = sense(screen)
            if snapshot is None:
                break
            if getattr(screen, "paused", False):
                time.sleep(RETARGET_DELAY)
                continue

            # Decide the attractor once per tick, then seed the population
            # with structured candidates so the GA always *evaluates* the
            # optimum (the chosen gate center, the gap, etc.) and carries it
            # forward via elitism — this is what kills the old "random
            # sampling missed the right target" failure.
            decision = _decide(snapshot)
            prev = self._prev_frac
            seeds = self._seed_candidates(snapshot, decision)
            candidates = seeds + population

            ranked = sorted(
                candidates,
                key=lambda f: fitness(snapshot, f, decision, prev),
                reverse=True,
            )
            best_frac = ranked[0]
            self._prev_frac = best_frac
            target_x = snapshot["road_left"] + best_frac * snapshot["road_w"]
            # Apply on the main thread — _hero_target_x is read in _update,
            # so a cross-thread write would be a race.
            Clock.schedule_once(
                lambda _dt, _x=target_x: self._apply_target(_x), 0,
            )
            population = self._next_generation(ranked)
            time.sleep(RETARGET_DELAY)

    def _seed_candidates(self, snapshot: dict,
                         decision: "dict | None") -> list[float]:
        """Structured fractions injected each tick so the GA never misses
        the true optimum: the chosen attractor, both gate centers, the gap,
        the current hero X, and the previous target."""
        seeds: list[float] = []
        gate = snapshot["gate"]
        if gate is not None:
            seeds.append(gate["left_x"] + gate["left_w"] * 0.5)
            seeds.append(gate["right_x"] + gate["right_w"] * 0.5)
            seeds.append((gate["left_x"] + gate["left_w"] + gate["right_x"]) * 0.5)
        if decision is not None:
            seeds.append(decision["desired_x"])
        seeds.append(snapshot["hero_x_frac"])
        if self._prev_frac is not None:
            seeds.append(self._prev_frac)
        # Clamp to the road and drop near-duplicates.
        out: list[float] = []
        for s in seeds:
            s = max(0.0, min(1.0, s))
            if all(abs(s - o) > 1e-4 for o in out):
                out.append(s)
        return out

    def _apply_target(self, x: float) -> None:
        screen = self.screen
        if screen is None or screen._level_ended:
            return
        screen._hero_target_x = x

    def _next_generation(self, ranked: list[float]) -> list[float]:
        # Elitism + uniform crossover + per-gene mutation. Same shape as
        # CoinTex; in 1-D, crossover collapses to "pick from one parent."
        parents = ranked[:PARENTS]
        new_pop = list(ranked[:KEEP_BEST])
        while len(new_pop) < POPULATION:
            mother = random.choice(parents)
            father = random.choice(parents)
            child = mother if random.random() < 0.5 else father
            if random.random() < MUTATION_PROB:
                child = random.random()
            new_pop.append(child)
        return new_pop
