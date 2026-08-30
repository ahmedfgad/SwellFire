"""Shop catalog — what the player can buy with coins.

The catalog is read-only data; the UI (ui.ShopScreen) renders it and the
purchase actions live on `state.GameState` (`purchase_weapon`,
`purchase_booster`, `purchase_squad_bonus`).

Economy design
==============

Completion and star rewards are the dependable income floor; kill fractions
and ground pickups add a smaller skill bonus. The weapon prices are centered
on upgrading one preferred weapon once per world, while optional squad and
booster purchases provide alternate recovery paths. All weapons remain free at
tier 1, so a player can change style without first paying an unlock fee.

Catalog items
=============

Each item is a `ShopItem`:

    id        — unique key (matches weapons.WEAPONS for weapon items, etc.)
    label     — display name
    price     — base price in coins
    category  — "weapon" / "booster" / "squad"
    description — short rationale shown under the price
"""

from __future__ import annotations

from dataclasses import dataclass

from . import weapons


@dataclass(frozen=True)
class ShopItem:
    id: str
    label: str
    price: int
    category: str          # "weapon" | "booster" | "squad"
    description: str
    # Optional context:
    booster_id: str = ""
    booster_qty: int = 0
    squad_target: int = 0
    weapon_id: str = ""    # for weapon items — which weapon this row represents


# Per-weapon, per-tier prices: TIER_PRICES[weapon][tier] = coins.
# Cheaper weapons have cheaper upgrades; tier 1 is always free for all weapons.
TIER_PRICES: dict[str, dict[int, int]] = {
    "pistol":  {2: 150, 3: 350, 4: 700,  5: 1200, 6: 1800},
    "rifle":   {2: 400, 3: 900, 4: 1800, 5: 2200, 6: 3000},
    "shotgun": {2: 500, 3: 1000, 4: 1800, 5: 2800, 6: 4000},
    "sniper":  {2: 700, 3: 1400, 4: 2400, 5: 3600, 6: 5200},
}


def next_tier_price(weapon_id: str, current_tier: int) -> int | None:
    """Price to upgrade `weapon_id` from `current_tier` to the next tier.
    Returns None if the weapon is already at the max tier."""
    if current_tier >= weapons.MAX_TIER:
        return None
    return TIER_PRICES.get(weapon_id, {}).get(current_tier + 1)


# Order matters: items render in this order under their category.
CATALOG: list[ShopItem] = [
    # --- weapons --------------------------------------------------------
    # All four weapons are tier-1 free. The card's `price` is set dynamically
    # in the UI based on the player's current tier; this static price is
    # the floor (tier 2 entry price) used for the catalog declaration only.
    ShopItem(
        id="weapon_pistol", label="Pistol", price=150, category="weapon",
        description="Reliable starter — 2.5 shots/s, 1 damage. Tap to equip; "
                    "tap upgrade for more damage per shot.",
        weapon_id="pistol",
    ),
    ShopItem(
        id="weapon_rifle", label="Rifle", price=400, category="weapon",
        description="7 shots/s, 1 damage — the everyday workhorse. "
                    "Crucial for W4+ regular levels.",
        weapon_id="rifle",
    ),
    ShopItem(
        id="weapon_shotgun", label="Shotgun", price=500, category="weapon",
        description="6 projectiles per shot, wide spread. Crushes swarmer "
                    "clusters and dense W5+ waves.",
        weapon_id="shotgun",
    ),
    ShopItem(
        id="weapon_sniper", label="Sniper", price=700, category="weapon",
        description="5 damage per shot, slow fire rate. Punches through "
                    "tanks; pairs with a big squad for W6.",
        weapon_id="sniper",
    ),

    # --- boosters --------------------------------------------------------
    ShopItem(
        id="grenade_1", label="Grenade x 1", price=50, category="booster",
        description="Single grenade. Detonate with G; clears the screen of "
                    "enemies in front of the hero.",
        booster_id="grenade", booster_qty=1,
    ),
    ShopItem(
        id="grenade_5", label="Grenade x 5", price=200, category="booster",
        description="Five grenades for 200 coins — 20 % bulk discount.",
        booster_id="grenade", booster_qty=5,
    ),
    ShopItem(
        id="shield_1", label="Shield x 1", price=80, category="booster",
        description="3-second attrition immunity. Press S to activate.",
        booster_id="shield", booster_qty=1,
    ),
    ShopItem(
        id="shield_3", label="Shield x 3", price=200, category="booster",
        description="Three shields for 200 coins (was 240) — bulk discount.",
        booster_id="shield", booster_qty=3,
    ),
    ShopItem(
        id="reinforce_1", label="Reinforcements x 1", price=120, category="booster",
        description="Instantly summon +8 squad members. Press R. The fastest "
                    "way to recover from a brutal wave.",
        booster_id="reinforce", booster_qty=1,
    ),
    ShopItem(
        id="reinforce_3", label="Reinforcements x 3", price=300, category="booster",
        description="Three reinforcement kits for 300 coins — bulk discount.",
        booster_id="reinforce", booster_qty=3,
    ),
    ShopItem(
        id="freeze_1", label="Freeze x 1", price=80, category="booster",
        description="Freezes every enemy for 3 seconds while your squad keeps "
                    "firing. Press F.",
        booster_id="freeze", booster_qty=1,
    ),
    ShopItem(
        id="freeze_3", label="Freeze x 3", price=200, category="booster",
        description="Three freezes for 200 coins — bulk discount.",
        booster_id="freeze", booster_qty=3,
    ),
    ShopItem(
        id="overdrive_1", label="Overdrive x 1", price=80, category="booster",
        description="2× fire rate (and extra punch) for 5 seconds. Press O. "
                    "Melts dense waves and bosses.",
        booster_id="overdrive", booster_qty=1,
    ),
    ShopItem(
        id="overdrive_3", label="Overdrive x 3", price=200, category="booster",
        description="Three overdrives for 200 coins — bulk discount.",
        booster_id="overdrive", booster_qty=3,
    ),
    ShopItem(
        id="magnet_1", label="Magnet x 1", price=60, category="booster",
        description="Pulls every coin on screen to the hero for 6 seconds. "
                    "Press M.",
        booster_id="magnet", booster_qty=1,
    ),
    ShopItem(
        id="magnet_3", label="Magnet x 3", price=150, category="booster",
        description="Three magnets for 150 coins — bulk discount.",
        booster_id="magnet", booster_qty=3,
    ),

    # --- squad bonuses (cumulative) --------------------------------------
    ShopItem(
        id="squad_1", label="Starting Squad +1", price=500, category="squad",
        description="Permanent. +1 follower at every non-boss level start.",
        squad_target=1,
    ),
    ShopItem(
        id="squad_2", label="Starting Squad +2", price=900, category="squad",
        description="Permanent. Requires Starting Squad +1 first. +2 followers "
                    "at every non-boss level start.",
        squad_target=2,
    ),
    ShopItem(
        id="squad_3", label="Starting Squad +3", price=1400, category="squad",
        description="Permanent. Requires Starting Squad +2 first. +3 followers "
                    "at every non-boss level start.",
        squad_target=3,
    ),
    ShopItem(
        id="squad_4", label="Starting Squad +4", price=2000, category="squad",
        description="Permanent. Requires Starting Squad +3 first. +4 followers "
                    "at every non-boss level start.",
        squad_target=4,
    ),
    ShopItem(
        id="squad_5", label="Starting Squad +5", price=2800, category="squad",
        description="Permanent. Requires Starting Squad +4 first. +5 followers "
                    "at every non-boss level start.",
        squad_target=5,
    ),
]


def category_items(category: str) -> list[ShopItem]:
    return [item for item in CATALOG if item.category == category]


# Order shown under each section heading in the UI.
CATEGORY_ORDER = ("weapon", "booster", "squad")
CATEGORY_LABELS = {
    "weapon":  "Starting Weapons",
    "booster": "Boosters",
    "squad":   "Squad Upgrades",
}


def is_owned(item: ShopItem, state) -> bool:
    """Squad bonuses become permanently owned after purchase. Weapons are
    always "owned" (tier 1 is free) — the meaningful state is whether the
    current tier is maxed out. Boosters are consumable, never "owned"."""
    if item.category == "weapon":
        # All weapons are owned at tier 1 by default; "owned" in the UI
        # sense means at MAX tier (no more upgrades to buy).
        return state.get_weapon_tier(item.weapon_id) >= weapons.MAX_TIER
    if item.category == "squad":
        return state.squad_bonus >= item.squad_target
    return False
