"""Regression tests for corrupted saves and economy input validation."""

import json

from swellfire import state
from swellfire import weapons


def test_corrupt_save_values_are_normalised(tmp_path):
    payload = {
        "highest_unlocked": 999,
        "scores": {"1": -4, "2": "42", "999": 50, "bad": 1},
        "stars": {"1": 99, "2": -2},
        "best_distance": {"1": "75"},
        "coins_balance": -900,
        "grenade_balance": "7",
        "shield_balance": -3,
        "weapon_tiers": {"pistol": 999, "rifle": "2", "unknown": 6},
        "equipped_weapon": "unknown",
        "squad_bonus": 99,
        "settings": {
            "music_on": "false",
            "volume": float("inf"),
            "top_safe_inset": 4,
            "ga_style": "reckless",
            "mp_last_ip": "  example.test  ",
        },
    }
    (tmp_path / state.SAVE_NAME).write_text(json.dumps(payload), encoding="utf-8")

    loaded = state.GameState(str(tmp_path))
    assert loaded.highest_unlocked == state._TOTAL_LEVELS
    assert loaded.get_score(1) == 0
    assert loaded.get_score(2) == 42
    assert loaded.get_score(999) == 0
    assert loaded.get_stars(1) == 3
    assert loaded.coins_balance == 0
    assert loaded.get_booster_balance("grenade") == 7
    assert loaded.get_booster_balance("shield") == 0
    assert loaded.get_weapon_tier("pistol") == weapons.MAX_TIER
    assert loaded.get_weapon_tier("rifle") == 2
    assert loaded.starting_weapon == "pistol"
    assert loaded.squad_bonus == state.SQUAD_BONUS_MAX
    assert loaded.get_setting("music_on") is True
    assert loaded.get_setting("volume") == state.DEFAULT_SETTINGS["volume"]
    assert loaded.get_setting("top_safe_inset") == 0.12
    assert loaded.get_setting("ga_style") == "balanced"
    assert loaded.get_setting("mp_last_ip") == "example.test"


def test_negative_or_unknown_purchases_cannot_create_currency(tmp_path):
    saved = state.GameState(str(tmp_path))
    starting = saved.coins_balance
    assert saved.spend_coins(-50) is False
    assert saved.purchase_booster("unknown", 1, 10) is False
    assert saved.purchase_booster("grenade", -3, 10) is False
    assert saved.purchase_booster("grenade", 1, -10) is False
    assert saved.upgrade_weapon_tier("unknown", 2, 10) is False
    assert saved.coins_balance == starting
    assert saved.get_booster_balance("grenade") == 0


def test_booster_purchase_updates_balance_and_inventory_together(tmp_path):
    saved = state.GameState(str(tmp_path))
    assert saved.purchase_booster("shield", 3, 200) is True
    assert saved.coins_balance == 100
    assert saved.get_booster_balance("shield") == 3

    reloaded = state.GameState(str(tmp_path))
    assert reloaded.coins_balance == 100
    assert reloaded.get_booster_balance("shield") == 3


def test_squad_upgrades_respect_world_and_price_bounds(tmp_path):
    saved = state.GameState(str(tmp_path))
    saved.data["highest_unlocked"] = 31
    saved.data["coins_balance"] = 10_000
    assert saved.purchase_squad_bonus(3, 100) is True
    assert saved.purchase_squad_bonus(3, 100) is False
    assert saved.purchase_squad_bonus(4, -100) is False
    assert saved.purchase_squad_bonus(state.SQUAD_BONUS_MAX + 1, 100) is False
