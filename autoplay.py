"""autoplay.py — Gate Runner auto-player (M12).

Ported from CoinTex's autoplay.py with the genre retargeted:

* CoinTex was 2-D (the player walked freely in a grid), so the GA searched
  over (x, y) target points and fitness was "collect coins / avoid monsters."
* Gate Runner is effectively 1-D — the world auto-scrolls vertically, the
  hero only steers horizontally — so the solution space is just a target
  fraction ``f`` in ``[0, 1]`` across the road. Fitness rewards steering
  through the gate panel that improves the squad the most, dodging
  upcoming enemies, and grabbing coin/double-coin pickups when safe.

The structure is the same as CoinTex: ``sense()`` snapshots the world,
``fitness()`` scores a candidate target, and ``AutoPlayer`` runs a small
GA in a daemon thread that re-evaluates a few times per second.

Tuning lives in the user's save (``ga_style`` and ``ga_speed``) and is
applied by ``apply_auto_settings`` — same shape as CoinTex so the existing
AutoPlayerScreen wires up without modification.
"""

from __future__ import annotations

import random
import threading
import time

from kivy.clock import Clock

import gates


# How often the GA re-decides. Overridden by apply_auto_settings().
RETARGET_DELAY = 0.15

# Look-ahead windows (as a fraction of the stage height). Gates have the
# largest window because the player needs to start steering well before
# the pair arrives; enemies and pickups only matter once they're close.
GATE_LOOKAHEAD = 1.4
ENEMY_LOOKAHEAD = 0.9
PICKUP_LOOKAHEAD = 1.0

# Fitness weights. Gate selection dominates safety dominates pickups.
# The numbers were picked so that a gate that doubles the squad outscores
# a single enemy directly on the target lane, but two enemies in a row
# can pull the agent off a marginal gate.
GATE_WEIGHT = 600.0
# Enemy avoidance was 400 — the agent died on W3+ before finding a gate
# because the centering bias kept pulling it back into enemy columns.
# Bumped to 800 and ENEMY_RADIUS widened to 0.14 so dense lanes get a
# real "go around" signal.
ENEMY_PENALTY = 800.0
# Pickup attraction is intentionally disabled. With any non-zero weight,
# a near coin (d ≈ 0.05) scored ~PICKUP_WEIGHT / 0.05 ≈ 1600 — enough
# to drag the agent through a SUB or DIV gate, which always loses more
# squad than the pickup is worth. Coins still get collected when they
# happen to lie on the way to a good gate; they just don't drive the
# steering decision anymore.
PICKUP_WEIGHT = 0.0
# Centering used to be 5.0, strong enough to fight a marginal dodge.
# At 1.5 the agent freely commits to a side when threats are present
# but still returns to the middle on an empty stretch.
CENTERING_WEIGHT = 1.5
ENEMY_RADIUS = 0.14           # frac-of-road "too close" threshold

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

    # --- enemies ahead --------------------------------------------------
    enemies_ahead: list[tuple[float, float]] = []
    if screen.enemy_controller is not None:
        pool = screen.enemy_controller.pool
        for i in range(len(pool.active)):
            if not pool.active[i]:
                continue
            dy = pool.cy[i] - hero_cy
            if dy < 0 or dy > stage_h * ENEMY_LOOKAHEAD:
                continue
            enemies_ahead.append((
                _frac_x(pool.cx[i], road_left, road_w),
                dy / stage_h,
            ))

    # --- pickups ahead --------------------------------------------------
    pickups_ahead: list[tuple[float, float]] = []
    if screen.pickup_controller is not None:
        pool = screen.pickup_controller.pool
        for i in range(len(pool.active)):
            if not pool.active[i]:
                continue
            dy = pool.cy[i] - hero_cy
            if dy < 0 or dy > stage_h * PICKUP_LOOKAHEAD:
                continue
            pickups_ahead.append((
                _frac_x(pool.cx[i], road_left, road_w),
                dy / stage_h,
            ))

    return {
        "hero_x_frac": _frac_x(hero_cx, road_left, road_w),
        "road_left":   road_left,
        "road_w":      road_w,
        "squad":       max(1, screen.squad_count),
        "gate":        next_pair,
        "enemies":     enemies_ahead,
        "pickups":     pickups_ahead,
    }


# --- gate outcome model -----------------------------------------------------

def _simulate_gate(squad: int, op: str, value) -> int:
    """Project the squad count after the hero passes through this gate.

    Weapon and grenade gates don't change the squad — they get a small
    fixed bonus so the agent still values them over a missed gate, but
    less than a real squad-multiplying gate.
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 0
    if op == gates.OP_MUL:
        return max(0, squad * v)
    if op == gates.OP_ADD:
        return max(0, squad + v)
    if op == gates.OP_SUB:
        return max(0, squad - v)
    if op == gates.OP_DIV:
        return max(0, squad // max(1, v))
    if op == gates.OP_WEAPON:
        return squad + 3
    if op == gates.OP_GRENADE:
        return squad + 2
    return squad


# --- fitness ---------------------------------------------------------------

def fitness(snapshot: dict | None, target_frac: float) -> float:
    """Score a candidate target X (as a fraction of the road). Bigger
    is better, same convention as CoinTex.
    """
    if snapshot is None:
        return 0.0
    score = 0.0
    squad = snapshot["squad"]

    # Gate reward — the dominant term when a pair is in range.
    gate = snapshot["gate"]
    if gate is not None:
        left_outcome  = _simulate_gate(squad, gate["left_op"],  gate["left_val"])
        right_outcome = _simulate_gate(squad, gate["right_op"], gate["right_val"])
        # Side check: does the target land inside a gate panel?
        left_in  = gate["left_x"]  <= target_frac <= gate["left_x"]  + gate["left_w"]
        right_in = gate["right_x"] <= target_frac <= gate["right_x"] + gate["right_w"]
        urgency = 1.0 / (gate["dy_frac"] + 0.20)
        norm = max(1, squad)
        if left_in:
            score += (GATE_WEIGHT * STYLE_GATE_MULT
                      * (left_outcome - squad) * urgency / norm)
        elif right_in:
            score += (GATE_WEIGHT * STYLE_GATE_MULT
                      * (right_outcome - squad) * urgency / norm)
        else:
            best = max(left_outcome, right_outcome)
            # Half-weight penalty: missing a pair is bad but recoverable.
            score -= (GATE_WEIGHT * STYLE_GATE_MULT
                      * max(0, best - squad) * urgency / norm * 0.5)

    # Enemy avoidance — closer + same-column = bigger penalty.
    for ex, ey in snapshot["enemies"]:
        proximity = 1.0 - min(1.0, ey / ENEMY_LOOKAHEAD)
        lateral_gap = abs(target_frac - ex)
        if lateral_gap < ENEMY_RADIUS:
            severity = 1.0 - lateral_gap / ENEMY_RADIUS
            score -= ENEMY_PENALTY * STYLE_SAFE_MULT * proximity * severity

    # Pickup pull intentionally disabled — see PICKUP_WEIGHT comment.
    # The block is left in place behind a weight check so it can be
    # re-enabled cleanly if the tuning is revisited.
    if PICKUP_WEIGHT > 0.0:
        for px, py in snapshot["pickups"]:
            d = abs(target_frac - px) + 0.05
            score += PICKUP_WEIGHT / d * (1.0 / (py + 0.20))

    # Mild centering bias — keeps the hero from drifting to the rail
    # when nothing else demands a side.
    score -= CENTERING_WEIGHT * abs(target_frac - 0.5)
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

            ranked = sorted(
                population,
                key=lambda f: fitness(snapshot, f),
                reverse=True,
            )
            best_frac = ranked[0]
            target_x = snapshot["road_left"] + best_frac * snapshot["road_w"]
            # Apply on the main thread — _hero_target_x is read in _update,
            # so a cross-thread write would be a race.
            Clock.schedule_once(
                lambda _dt, _x=target_x: self._apply_target(_x), 0,
            )
            population = self._next_generation(ranked)
            time.sleep(RETARGET_DELAY)

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
