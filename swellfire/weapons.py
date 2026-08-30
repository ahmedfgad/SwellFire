"""Swellfire weapon registry.

Each weapon is a small dataclass that the gameplay layer reads to drive
auto-fire timing, projectile shape and spread. M7's "weapon gate" picks
an id from `WEAPONS` and sets it as the hero's `current_weapon`. The
in-run shop (later milestone) gates ids behind `state.weapon_unlocks`.

Numbers are first-pass and intentionally crude; M14 tunes them once the
real waves exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    fire_rate: float          # shots per second
    damage: int               # HP removed per projectile
    projectiles_per_shot: int # >1 for shotgun-style spread
    spread_deg: float         # half-angle cone (deg) for each projectile
    projectile_speed: float   # px/sec
    projectile_size: float    # px, square
    ttl: float                # projectile lifespan (seconds)
    frame: str                # atlas frame name for the projectile sprite
    range_frac: float = 0.33  # kill-zone reach as a fraction of the play field


# Order matters: cycle key visits these in this order, and the digit shortcuts
# 1..4 map to indices 0..3.
WEAPONS: dict[str, Weapon] = {
    "pistol": Weapon(
        id="pistol",  name="Pistol",
        fire_rate=2.5, damage=1, projectiles_per_shot=1,
        spread_deg=2.0, projectile_speed=820.0, projectile_size=14.0,
        ttl=1.0, frame="projectile", range_frac=0.50,
    ),
    "rifle": Weapon(
        id="rifle",   name="Rifle",
        fire_rate=7.0, damage=1, projectiles_per_shot=1,
        spread_deg=4.0, projectile_speed=980.0, projectile_size=12.0,
        ttl=0.70, frame="projectile", range_frac=0.50,
    ),
    "shotgun": Weapon(
        id="shotgun", name="Shotgun",
        fire_rate=1.7, damage=1, projectiles_per_shot=6,
        spread_deg=15.0, projectile_speed=720.0, projectile_size=14.0,
        ttl=0.8, frame="projectile", range_frac=0.42,
    ),
    "sniper": Weapon(
        id="sniper",  name="Sniper",
        fire_rate=1.0, damage=5, projectiles_per_shot=1,
        spread_deg=0.5, projectile_speed=1400.0, projectile_size=10.0,
        ttl=1.5, frame="projectile", range_frac=0.66,
    ),
}


# Stable order for cycle / shortcut keys.
ORDERED_IDS: list[str] = list(WEAPONS.keys())

# Weapon tier scaling. Tier 1 is the base weapon (free for all); each
# higher tier increases projectile damage. Index by tier 1..MAX_TIER; the zero
# slot is unused.
MAX_TIER = 6
TIER_DAMAGE_MULT: list[float] = [None, 1.0, 1.5, 2.0, 3.0, 4.0, 5.5]
TIER_DAMAGE_FLOOR_BONUS: list[int] = [None, 0, 1, 2, 3, 5, 7]


def tier_damage(weapon: "Weapon", tier: int) -> int:
    """Effective damage for `weapon` at tier `tier` (clamped to MAX_TIER)."""
    tier = max(1, min(MAX_TIER, int(tier)))
    scaled = int(round(weapon.damage * TIER_DAMAGE_MULT[tier]))
    # Low-base-damage automatic weapons used to repeat the same integer damage
    # at adjacent tiers (for example rifle T2 and T3 both dealt 2). Every paid
    # tier must be a real upgrade, while high-damage weapons retain their
    # multiplier curve.
    return max(1, weapon.damage + TIER_DAMAGE_FLOOR_BONUS[tier], scaled)


def combat_power(weapon: "Weapon", tier: int) -> float:
    """Comparable sustained projectile power for upgrade/swap decisions."""
    return (weapon.fire_rate * weapon.projectiles_per_shot
            * tier_damage(weapon, tier))


def get(weapon_id: str) -> Weapon:
    return WEAPONS[weapon_id]


def next_id(current_id: str) -> str:
    idx = ORDERED_IDS.index(current_id)
    return ORDERED_IDS[(idx + 1) % len(ORDERED_IDS)]


def by_index(idx: int) -> str | None:
    if 0 <= idx < len(ORDERED_IDS):
        return ORDERED_IDS[idx]
    return None
