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
