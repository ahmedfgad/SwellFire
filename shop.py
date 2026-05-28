"""Shop catalog — what the player can buy with coins.

The catalog is read-only data; the UI (ui.ShopScreen) renders it and the
purchase actions live on `state.GameState` (`purchase_weapon`,
`purchase_booster`, `purchase_squad_bonus`).

Economy design
==============

A typical W1-W3 run yields ~250-400 coins (1 per kill + 50 completion +
30 per star). After clearing W1+W2 the player has ~3000 coins, enough to
buy the Rifle starter weapon (800) which is the gate to playing W4+ at
all. Continued play through W3-W4 funds the Shotgun (1500) which makes
W5-W6 survivable. Top tier (Sniper, full squad bonus) is a stretch goal.

The progression:

    Coins after W1   ~1500       → Rifle (800) leaves headroom for boosters
    Coins after W2   ~3500       → Squad +1 (1000) + grenade stock
    Coins after W3   ~6500       → Shotgun (1500)
    Coins after W4   ~12000      → Squad +2 (2200 cumulative) + Sniper (2500)

Bosses pay extra coin so finishing a world has a tangible "you can now
afford the next upgrade" moment.

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
    "pistol":  {2: 200,  3: 500,  4: 1200},
    "rifle":   {2: 400,  3: 1000, 4: 2200},
    "shotgun": {2: 700,  3: 1500, 4: 3000},
    "sniper":  {2: 1000, 3: 2500, 4: 5000},
}


def next_tier_price(weapon_id: str, current_tier: int) -> int | None:
    """Price to upgrade `weapon_id` from `current_tier` to the next tier.
    Returns None if the weapon is already at the max tier."""
    if current_tier >= 4:
        return None
    return TIER_PRICES.get(weapon_id, {}).get(current_tier + 1)


# Order matters: items render in this order under their category.
CATALOG: list[ShopItem] = [
    # --- weapons --------------------------------------------------------
    # All four weapons are tier-1 free. The card's `price` is set dynamically
    # in the UI based on the player's current tier; this static price is
    # the floor (tier 2 entry price) used for the catalog declaration only.
    ShopItem(
        id="weapon_pistol", label="Pistol", price=200, category="weapon",
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
        id="weapon_shotgun", label="Shotgun", price=700, category="weapon",
        description="5 projectiles per shot, wide spread. Crushes swarmer "
                    "clusters and dense W5+ waves.",
        weapon_id="shotgun",
    ),
    ShopItem(
        id="weapon_sniper", label="Sniper", price=1000, category="weapon",
        description="3 damage per shot, slow fire rate. Punches through "
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

    # --- squad bonuses (cumulative) --------------------------------------
    ShopItem(
        id="squad_1", label="Starting Squad +1", price=1000, category="squad",
        description="Permanent. +1 follower at every non-boss level start.",
        squad_target=1,
    ),
    ShopItem(
        id="squad_2", label="Starting Squad +2", price=2200, category="squad",
        description="Permanent. Requires Starting Squad +1 first. +2 followers "
                    "at every non-boss level start.",
        squad_target=2,
    ),
    ShopItem(
        id="squad_3", label="Starting Squad +3", price=3600, category="squad",
        description="Permanent. Requires Starting Squad +2 first. +3 followers "
                    "at every non-boss level start.",
        squad_target=3,
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
        return state.get_weapon_tier(item.weapon_id) >= 4
    if item.category == "squad":
        return state.squad_bonus >= item.squad_target
    return False
