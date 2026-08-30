"""Booster registry — pickup-based one-shot abilities the player triggers
during a run.

A booster is data: id, display name, keyboard key, HUD color, in-run cap.
Effects live in `game.GameScreen` because they need access to enemy pool,
hero, particle system etc. — but the registry here is the single source of
truth for "what boosters exist", which the HUD, the in-world pickup
spawner (M14 polish), and the future shop all read.

Shipping set:

    grenade    G — clears every enemy in a wide radius in front of the hero;
                   damages the boss if in range.
    shield     S — 3 s of full attrition immunity (visual: blue hero tint).
    reinforce  R — instant burst of squad members (counters attrition).
    freeze     F — enemies stop moving / attacking for a few seconds.
    overdrive  O — fire rate (and a little damage) surge for a few seconds.
    magnet     M — active pickups home to the hero for a few seconds.

grenade, reinforce, freeze, overdrive and magnet are also gate ops (collected
as a charge from a bonus gate, used later); shield is shop-only. All six are
sold in the shop. Effects live in `game.GameScreen`; this module is the single
source of truth for "what boosters exist".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Booster:
    id: str
    name: str
    short_label: str        # 1-2 letter HUD tag, e.g. "G"
    key_code: str           # keyboard shortcut (lowercase) — `g`, `s`
    hud_color: tuple[float, float, float, float]
    max_per_run: int = 9    # in-run cap (HUD readable, not too punishing)


GRENADE = Booster(
    id="grenade", name="Grenade", short_label="G", key_code="g",
    hud_color=(0.25, 0.80, 0.95, 1.0),
    max_per_run=9,
)

SHIELD = Booster(
    id="shield", name="Shield", short_label="S", key_code="s",
    hud_color=(0.50, 0.85, 1.00, 1.0),
    max_per_run=4,
)

REINFORCE = Booster(
    id="reinforce", name="Reinforcements", short_label="R", key_code="r",
    hud_color=(0.40, 0.90, 0.45, 1.0),       # green — recovery
    max_per_run=5,
)

FREEZE = Booster(
    id="freeze", name="Freeze", short_label="F", key_code="f",
    hud_color=(0.45, 0.80, 1.00, 1.0),       # icy blue
    max_per_run=5,
)

OVERDRIVE = Booster(
    id="overdrive", name="Overdrive", short_label="O", key_code="o",
    hud_color=(1.00, 0.55, 0.20, 1.0),       # orange — rapid fire
    max_per_run=5,
)

MAGNET = Booster(
    id="magnet", name="Magnet", short_label="M", key_code="m",
    hud_color=(0.80, 0.45, 0.95, 1.0),       # purple — economy
    max_per_run=5,
)


BOOSTERS: dict[str, Booster] = {
    b.id: b for b in (GRENADE, SHIELD, REINFORCE, FREEZE, OVERDRIVE, MAGNET)
}

# Stable order for HUD display + shop ordering.
ORDERED_IDS: list[str] = [
    "grenade", "shield", "reinforce", "freeze", "overdrive", "magnet",
]


# Booster effect durations (seconds) / magnitudes where applicable.
SHIELD_DURATION_SEC = 3.0
FREEZE_DURATION_SEC = 3.0
OVERDRIVE_DURATION_SEC = 5.0
MAGNET_DURATION_SEC = 6.0
OVERDRIVE_FIRE_MULT = 2.0        # fire-rate multiplier while Overdrive is up
OVERDRIVE_DAMAGE_MULT = 1.3      # small damage bump alongside the rate boost
REINFORCE_AMOUNT = 8             # squad members granted per Reinforcements use
MAGNET_PULL_SPEED = 900.0        # px/s pickups home toward the hero under Magnet


def refreshed_until(current_until: float, now: float,
                    base_duration: float, scale: int = 1) -> float:
    """New `*_active_until` for a timed booster, applying refresh-not-rob:
    a (re)activation extends the timer to `now + base_duration*scale` but never
    shortens an already-longer active window."""
    return max(current_until, now + base_duration * max(1, int(scale)))
