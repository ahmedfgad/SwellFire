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


# Order matters: items render in this order under their category.
CATALOG: list[ShopItem] = [
    # --- starting weapons ------------------------------------------------
    ShopItem(
        id="weapon_rifle", label="Rifle (starter)", price=800,
        category="weapon",
        description="Permanent. Every non-boss level starts with a rifle "
                    "(7 shots/s) instead of a pistol — the difference that "
                    "makes W4+ playable.",
    ),
    ShopItem(
        id="weapon_shotgun", label="Shotgun (starter)", price=1500,
        category="weapon",
        description="Permanent. 5 projectiles per shot with spread — crushes "
                    "the dense W5+ swarmer + bomber waves.",
    ),
    ShopItem(
        id="weapon_sniper", label="Sniper (starter)", price=2500,
        category="weapon",
        description="Permanent. 3 damage per shot — punches through tanks and "
                    "boss HP. Pair with a big squad and W6 is on the table.",
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
    """One-off items (weapons, squad bonuses) become owned after purchase.
    Boosters are consumable — never "owned"."""
    if item.category == "weapon":
        # Weapon item id is "weapon_<id>"; strip the prefix to get the
        # weapon id used by state.weapon_unlocks.
        wid = item.id.split("_", 1)[1]
        return state.is_weapon_unlocked(wid)
    if item.category == "squad":
        return state.squad_bonus >= item.squad_target
    return False
