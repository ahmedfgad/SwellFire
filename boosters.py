"""Booster registry — pickup-based one-shot abilities the player triggers
during a run.

A booster is data: id, display name, keyboard key, HUD color, in-run cap.
Effects live in `game.GameScreen` because they need access to enemy pool,
hero, particle system etc. — but the registry here is the single source of
truth for "what boosters exist", which the HUD, the in-world pickup
spawner (M14 polish), and the future shop all read.

M11.5 ships with:

    grenade   G — clears every enemy in a wide radius in front of the hero;
                  damages the boss if in range.
    shield    S — 3 s of full attrition immunity (visual: blue hero tint).

Future ideas (deferred to the M14 shop pass):
    magnet    M — auto-pickup nearby coins for a few seconds.
    squad_heal H — +5 squad members instant.
    slow_mo   T — slow enemy motion for a few seconds.
    rapidfire R — double fire rate for a few seconds.
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


BOOSTERS: dict[str, Booster] = {b.id: b for b in (GRENADE, SHIELD)}

# Stable order for HUD display + (eventual) shop ordering.
ORDERED_IDS: list[str] = ["grenade", "shield"]


# Booster effect durations (seconds) where applicable.
SHIELD_DURATION_SEC = 3.0
