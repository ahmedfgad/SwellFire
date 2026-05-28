"""GateRunner level definitions.

`build_levels()` generates all 60 levels (6 worlds × 10 levels) procedurally
from a small set of knobs that ramp with world + in-world index. The
returned dict is keyed by absolute level index (1..60); `LEVELS` caches
the result at module load. Game logic reads per-level dicts via
`get_level(index)`.

Knob design (port from CoinTex's pattern):
    * `distance_goal` — px the player must scroll past to finish.
    * `enemy_spawn_interval` — seconds between enemy spawns (smaller = more).
    * `enemy_speed` — px/sec the enemies travel toward the hero.
    * `enemy_hp` — HP per enemy.
    * `enemy_chase_{min,max}` — per-enemy lateral homing strength range.
    * `gate_interval_px` — distance between gate pairs.
    * `allowed_ops` — gate operation tags the spawner may pick.
    * `allowed_weapons` — weapon ids that may appear in weapon-swap gates.
    * `squad_target_{2,3}_star` — squad-count thresholds for the
      respective star rating at level end.

Difficulty scales **mostly via behavior**, not entity count — same lesson
as CoinTex. The pool capacities and the renderer can sustain 200+ entities
(see M3/M5 perf measurements); making the player feel pressure comes from
faster enemies, more aggressive chasers, denser gates with riskier ops.
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
            gate_interval_px = _lerp(720.0, 420.0, t)

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

            allowed_ops = ["mul", "add"]
            if world >= 2:
                allowed_ops.append("grenade")     # bonus pickup gates from W2
            if world >= 3:
                allowed_ops.append("weapon")
            if world >= 5:
                allowed_ops.append("sub")

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
            # squad. Sim-tuned in the difficulty regression script.
            boss_hp = int(round(_lerp(350.0, 1100.0, t))) if is_boss else 0
            starting_squad = int(round(_lerp(3.0, 12.0, world / NUM_WORLDS))) if is_boss else 1
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
            }
    return levels


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
