"""GateRunner level definitions.

`build_levels()` generates all 60 levels (6 worlds × 10 levels) procedurally
from a small set of knobs that ramp with world + in-world index. The
returned dict is keyed by absolute level index (1..60); `LEVELS` caches
the result at module load. Game logic reads per-level dicts via
`get_level(index)`.

# ---------------------------------------------------------------
# WHICH FIELDS ARE AUTOMATIC vs HAND-TUNED?
# ---------------------------------------------------------------
#
# AUTO-DERIVED (you change one input and these recompute) :
#   distance_goal     ← max(t-lerp, min_duration * SCROLL_SPEED)
#   kill_target       ← level_seconds * (1/enemy_spawn_interval) * 0.55
#   level_seconds     ← distance_goal / SCROLL_SPEED
#   level type tag    ← derived from `t` (early=static, mid=hybrid, late=dynamic)
#   boss flag         ← in_world == LEVELS_PER_WORLD
#
# HAND-TUNED (each is its own dial — change in the function below) :
#
#   ─── per-level continuous ramps (all driven by `t` = (idx-1)/59) ───
#     enemy_spawn_interval      0.18 → 0.05 s
#     enemy_speed               180 → 290 px/s
#     enemy_chase_min/max       (25 → 80) / (80 → 170) px/s lateral
#     gate_interval_px          720 → 420 px
#     boss_hp (boss levels)     350 → 1100 HP
#     squad_target_2_star       10 → 40
#     squad_target_3_star       20 → 80
#
#   ─── tiered (step changes by world / by t) ───
#     enemy_hp                  1 (t<0.40) → 2 (t<0.78) → 3
#     boss_minion_hp            1 (W1-3) → 2 (W4-5) → 3 (W6)
#     allowed_ops               per world (see _allowed_enemy_types below)
#     allowed_weapons           per world (rifle / shotgun / sniper unlocks)
#     allowed_enemy_types       per world (grunt → +swarmer → +tank → +bomber → +splitter)
#     starting_squad (boss)     3 → 12 (depends on world, not t)
#     starting_weapon (boss)    pistol / rifle / sniper by world
#
#   ─── global knobs (apply to every level) ───
#     LEVEL_BASE_DURATION_SEC   L1's floor
#     LEVEL_DURATION_STEP_SEC   added per level globally
#     SCROLL_SPEED_PX_PER_SEC   world auto-scroll speed
#     LEVELS_PER_WORLD          10 (changing this would resize the WORLDS list)
#     NUM_WORLDS                6
#
# STRATEGY TO TUNE :
#   1. Want every level *longer*?  Bump LEVEL_BASE_DURATION_SEC or
#      LEVEL_DURATION_STEP_SEC. distance_goal + kill_target follow.
#   2. Want a *single world* harder?  Edit the matching `if world ==`
#      branch in _allowed_enemy_types() to give heavier weights to
#      tank / bomber / splitter.
#   3. Want enemies tougher *across the board*?  Move the enemy_hp tier
#      breakpoints down (e.g. `t < 0.25` instead of `t < 0.40`).
#   4. Want bosses harder?  Bump the lerp endpoints in `boss_hp` and/or
#      drop `starting_squad` endpoints. The difficulty sim in
#      tools/difficulty_sim.py will tell you if the new numbers tip
#      passive→W or greedy→L beyond what you want.
#   5. Want gate cadence tighter?  Bump the gate_interval_px endpoints.
#
# The same `tools/difficulty_sim.py` runs every level with a passive and a
# greedy agent so you can verify a change before shipping.
# ---------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

NUM_WORLDS = 6
LEVELS_PER_WORLD = 10
TOTAL_LEVELS = NUM_WORLDS * LEVELS_PER_WORLD

# Auto-scroll speed in px/sec; used to convert "minimum level duration in
# seconds" to a minimum distance_goal.
SCROLL_SPEED_PX_PER_SEC = 360.0

# Level "type" tags describe how spawn intensity responds to the player.
#   static  — fixed spawn script; missed gates are forgivable since later
#             gates compensate. Easy / forgiving feel.
#   hybrid  — static baseline + periodic dynamic spike windows where spawn
#             interval halves for a few seconds.
#   dynamic — spawn interval scales inversely with current squad firepower.
#             Missing a x2 gate punishes hard: the spawner ramps up to
#             match the squad you should have had.
TYPE_STATIC = "static"
TYPE_HYBRID = "hybrid"
TYPE_DYNAMIC = "dynamic"
TYPE_BOSS = "boss"

# World themes (used by ui.WorldMap + ui.LevelSelect for the gradient background).
WORLDS = [
    {"id": 1, "name": "Meadow",     "top": (0.32, 0.62, 0.36), "bottom": (0.16, 0.34, 0.20), "accent": (0.95, 0.85, 0.30)},
    {"id": 2, "name": "Desert",     "top": (0.92, 0.72, 0.40), "bottom": (0.60, 0.40, 0.20), "accent": (0.95, 0.65, 0.25)},
    {"id": 3, "name": "Industrial", "top": (0.40, 0.45, 0.55), "bottom": (0.16, 0.20, 0.28), "accent": (0.30, 0.75, 0.90)},
    {"id": 4, "name": "Snowfield",  "top": (0.78, 0.86, 0.92), "bottom": (0.44, 0.56, 0.66), "accent": (0.55, 0.85, 1.00)},
    {"id": 5, "name": "Volcano",    "top": (0.86, 0.32, 0.22), "bottom": (0.30, 0.08, 0.06), "accent": (1.00, 0.60, 0.15)},
    {"id": 6, "name": "Cosmos",     "top": (0.20, 0.16, 0.36), "bottom": (0.05, 0.04, 0.12), "accent": (0.70, 0.45, 1.00)},
]

# Static seeded arena used by the 2-player versus mode (M13).
MP_LEVEL = "mp"
# Versus matches are short, fixed-length sprints. 60 seconds is long
# enough for both players to grow their squad through several gates
# but short enough that a full match fits a casual "one more round".
MP_LEVEL_DURATION_SEC = 60.0


def build_mp_level() -> dict[str, Any]:
    """Construct the versus-mode level config.

    Uses L1's spawn / enemy parameters as the gameplay baseline (gentle
    intro pressure, all gate ops unlocked via L1's allowed_ops) but
    overrides ``distance_goal`` / ``level_seconds`` to MP_LEVEL_DURATION_SEC
    so a versus run takes 60 s regardless of which single-player level
    was last played.
    """
    base = dict(LEVELS[1])
    base["distance_goal"] = MP_LEVEL_DURATION_SEC * SCROLL_SPEED_PX_PER_SEC
    base["level_seconds"] = MP_LEVEL_DURATION_SEC
    base["name"] = "Versus Arena"
    return base


def get_world(world: int) -> dict:
    idx = max(1, min(NUM_WORLDS, int(world))) - 1
    return WORLDS[idx]


def _lerp(a: float, b: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def build_levels() -> dict[int, dict[str, Any]]:
    """Produce the full level table.

    `t` is the overall difficulty ramp in [0, 1] across all 60 levels.
    """
    levels: dict[int, dict[str, Any]] = {}
    # Per-level duration is the canonical "how long should this level feel"
    # knob — everything that scales with level length (distance_goal,
    # kill_target) derives from it. Two parameters control the ramp:
    #   LEVEL_BASE_DURATION_SEC  — L1's floor
    #   LEVEL_DURATION_STEP_SEC  — added per level (globally, not per world)
    # so the ramp is monotonic and the player can feel each new level
    # extending. L1 = 20 s, L60 = 20 + 59*2 = 138 s.
    LEVEL_BASE_DURATION_SEC = 20.0
    LEVEL_DURATION_STEP_SEC = 2.0
    for world in range(1, NUM_WORLDS + 1):
        for in_world in range(1, LEVELS_PER_WORLD + 1):
            index = (world - 1) * LEVELS_PER_WORLD + in_world
            t = (index - 1) / max(1, TOTAL_LEVELS - 1)

            min_duration = LEVEL_BASE_DURATION_SEC + (index - 1) * LEVEL_DURATION_STEP_SEC
            distance_goal = max(_lerp(7200.0, 14400.0, t),
                                min_duration * SCROLL_SPEED_PX_PER_SEC)
            enemy_spawn_interval = _lerp(0.18, 0.05, t)     # ~5/s → ~20/s
            enemy_speed = _lerp(180.0, 290.0, t)            # px/sec downward
            if t < 0.40:
                enemy_hp = 1
            elif t < 0.78:
                enemy_hp = 2
            else:
                enemy_hp = 3
            enemy_chase_min = _lerp(25.0, 80.0, t)
            enemy_chase_max = _lerp(80.0, 170.0, t)
            # Gate cadence: target a fixed number of pairs per level so the
            # player makes 10-24 decisions per run regardless of level
            # length. Earlier formulas used a fixed px interval, which gave
            # later levels (longer) absurd gate counts (71 pairs in W4L1!).
            # Floor at 380 px so the earliest levels still have visible
            # spacing between pairs.
            target_pairs = _lerp(10.0, 24.0, t)
            gate_interval_px = max(380.0, (distance_goal - 200.0) / target_pairs)

            # Per-level type. Boss levels override.
            if in_world == LEVELS_PER_WORLD:
                level_type = TYPE_BOSS
            elif t < 0.18:
                level_type = TYPE_STATIC
            elif t < 0.55:
                level_type = TYPE_HYBRID
            else:
                level_type = TYPE_DYNAMIC

            # Kill target derives from level length × spawn rate × 0.55.
            # Adjust `min_duration` and this updates automatically — the same
            # auto-flow applies if a future tuner edits `enemy_spawn_interval`
            # directly. (`kill_target` is informational right now — the win
            # condition is distance + boss death; M14 polish can fold it into
            # stars or a per-level objective panel.)
            level_seconds = distance_goal / SCROLL_SPEED_PX_PER_SEC
            kill_target = int(round(level_seconds * (1.0 / enemy_spawn_interval) * 0.55))

            allowed_ops = ["mul", "add", "sub"]   # SUB now available from W1
            if world >= 2:
                allowed_ops.append("grenade")     # bonus pickup gates from W2
            if world >= 3:
                allowed_ops.append("weapon")
                allowed_ops.append("div")         # divide-squad gates from W3
            # Note: SUB used to be W5+. The W1 introduction of SUB gives the
            # player real choices on every pair (often "+5 vs -2"). DIV
            # joins at W3 because by then the player has enough squad that
            # ÷2 isn't always fatal.
            # Grenade scarcity: W1 has none (excluded from allowed_ops above);
            # W2-W3 get 1 max per level, W4+ get 2 max. Boss levels keep their
            # own cap (set in game.py).
            if world == 1:
                max_grenade_gates = 0
            elif world <= 3:
                max_grenade_gates = 1
            else:
                max_grenade_gates = 2

            # Enemy archetype mix per world. Weights are relative; the spawner
            # normalizes. Late worlds add tank/bomber/splitter so a uniform-
            # firepower squad can't just hose them down — focused fire and
            # spread fire become real strategic choices.
            allowed_enemy_types = _allowed_enemy_types(world)

            allowed_weapons = ["rifle"]
            if world >= 2:
                allowed_weapons.append("shotgun")
            if world >= 4:
                allowed_weapons.append("sniper")

            squad_target_2 = int(round(_lerp(10.0, 40.0, t)))
            squad_target_3 = int(round(_lerp(20.0, 80.0, t)))

            # The last level of every world is a boss fight (M10). It
            # overrides the distance-goal win condition with "deplete boss
            # HP", disables gates (the player can't pivot mid-fight) and
            # gives the player a head-start squad + a world-appropriate weapon
            # so the fight isn't starting from pistol+1 — but the head start
            # is small enough that *passive* play loses.
            is_boss = (in_world == LEVELS_PER_WORLD)
            # Boss HP is high enough that a passive squad of `starting_squad`
            # cannot grind it down before the boss's volleys overwhelm the
            # squad. Sim-tuned in the difficulty regression script — the
            # 450 floor was raised from 350 because W3L10 passive was
            # winning in 30 s without picking a single gate.
            boss_hp = int(round(_lerp(450.0, 1200.0, t))) if is_boss else 0
            if is_boss:
                # Lowered the top end from 3..12 to 2.5..11 so W3-W5 bosses
                # don't auto-pass passive on starting squad alone.
                starting_squad = int(round(_lerp(2.5, 11.0, world / NUM_WORLDS)))
            else:
                # Non-boss starting squad scales with world: W1=1, W2=2, W3=3,
                # W4=4, W5=5, W6=6. Sub-linear fire cap (22) makes this
                # invisible firepower-wise for higher worlds (extra members
                # just absorb attrition), but it lets the player survive the
                # intro period before the first gate lands. Verified by the
                # difficulty sim — without this scaling W2+ dies at ~4 s.
                starting_squad = world
            # Per-world minion HP for boss-spawned enemies. Worlds 1-3 → 1,
            # 4-5 → 2, 6 → 3, so the squad can't just hose the wave.
            boss_minion_hp = 1 if world < 4 else (2 if world < 6 else 3)
            if not is_boss:
                starting_weapon = "pistol"
            elif world >= 4:
                starting_weapon = "sniper"
            elif world >= 2:
                starting_weapon = "rifle"
            else:
                starting_weapon = "rifle"

            levels[index] = {
                "index": index,
                "world": world,
                "world_index": in_world,
                "distance_goal": distance_goal,
                "enemy_spawn_interval": enemy_spawn_interval,
                "enemy_speed": enemy_speed,
                "enemy_hp": enemy_hp,
                "enemy_chase_min": enemy_chase_min,
                "enemy_chase_max": enemy_chase_max,
                "gate_interval_px": gate_interval_px,
                "allowed_ops": allowed_ops,
                "allowed_weapons": allowed_weapons,
                "squad_target_2_star": squad_target_2,
                "squad_target_3_star": squad_target_3,
                "boss": is_boss,
                "boss_hp": boss_hp,
                "boss_minion_hp": boss_minion_hp,
                "starting_squad": starting_squad,
                "starting_weapon": starting_weapon,
                "type": level_type,
                "min_duration_sec": min_duration,
                "kill_target": kill_target,
                "allowed_enemy_types": allowed_enemy_types,
                "max_grenade_gates": max_grenade_gates,
            }
    return levels


def _allowed_enemy_types(world: int) -> list[tuple[str, float]]:
    """Per-world archetype mix: list of (archetype_name, weight) pairs.

    Weights are relative — `EnemySpawner` normalizes. Archetypes unlock
    progressively as the player goes deeper. Each new archetype shifts
    one world later from the original draft because the sim showed an
    earlier roll-out (swarmer in W2, tank in W3) was killing greedy at
    squad=1 before the first gate could land.

        W1   grunts only
        W2   grunts only (slightly higher base spawn rate)
        W3   + swarmer (cluster of 4 → forces wide squad before W4)
        W4   + tank (focused-fire demand)
        W5   + bomber (AOE on death)
        W6   + splitter (overkill penalty)
    """
    if world <= 2:
        return [("grunt", 1.0)]
    if world == 3:
        return [("grunt", 0.78), ("swarmer", 0.22)]
    if world == 4:
        return [("grunt", 0.55), ("swarmer", 0.20), ("tank", 0.25)]
    if world == 5:
        return [("grunt", 0.40), ("swarmer", 0.15),
                ("tank", 0.20), ("bomber", 0.25)]
    return [("grunt", 0.32), ("swarmer", 0.15),
            ("tank", 0.18), ("bomber", 0.20), ("splitter", 0.15)]


LEVELS: dict[int, dict[str, Any]] = build_levels()


def get_level(index: int) -> dict[str, Any] | None:
    return LEVELS.get(int(index))


def levels_in_world(world: int) -> list[dict[str, Any]]:
    return [LEVELS[(world - 1) * LEVELS_PER_WORLD + i + 1]
            for i in range(LEVELS_PER_WORLD)]


def score_for(kills: int, final_squad: int, gates_applied: int,
              gates_missed: int) -> int:
    """Score formula used by GameScreen on level complete."""
    return (kills * 10
            + final_squad * 50
            + gates_applied * 30
            - gates_missed * 15)


def stars_for(level: dict[str, Any], won: bool, final_squad: int) -> int:
    """Map a (won?, final_squad) to a 0-3 star rating."""
    if not won:
        return 0
    stars = 1
    if final_squad >= level["squad_target_2_star"]:
        stars = 2
    if final_squad >= level["squad_target_3_star"]:
        stars = 3
    return stars
