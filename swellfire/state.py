# Saves game progress and settings for Swellfire.
# Everything is kept in one JSON file inside the folder the game passes in
# (the Kivy user_data_dir, which can be written to on all platforms).

import json
import math
import os

from . import weapons

# Keep in sync with levels.LEVELS_PER_WORLD (kept local to avoid an import cycle).
_LEVELS_PER_WORLD = 10
_TOTAL_LEVELS = 60
SQUAD_BONUS_MAX = 6
BOOSTER_IDS = ("grenade", "shield", "reinforce", "freeze", "overdrive", "magnet")

# Settings and their starting values. The "seen" flags remember one-time things:
# the tutorial auto-shows once, and each world's heads-up message shows once.
DEFAULT_SETTINGS = {
    "music_on": True,
    "sfx_on": True,
    # Stats HUD (squad/weapon/kills/coins + distance bar). Off by default so
    # the top band never covers gameplay (notably the boss); the player can
    # turn it on in Settings.
    "show_stats": False,
    # FPS / debug overlay (FPS, frame ms, entity counts). Off by default;
    # toggled in Settings, separate from show_stats (the band/title/chips).
    "show_debug": False,
    # Top safe-area inset (fraction of screen height) to push the progress bar
    # and the 2x-coins timer below a phone notch / dynamic island. Slider in
    # Settings; clamped to [0, 0.12] at apply time.
    "top_safe_inset": 0.05,
    "volume": 1.0,            # 0.0 to 1.0
    "ga_style": "balanced",   # auto player: cautious | balanced | aggressive
    "ga_speed": "normal",     # auto player: slow | normal | fast
    "tutorial_seen": False,
    "gates_hint_seen": False,
    "weapons_hint_seen": False,
    "boss_hint_seen": False,
    "shop_hint_seen": False,
    "intro_seen_w2": False,
    "intro_seen_w3": False,
    "intro_seen_w4": False,
    "intro_seen_w5": False,
    "intro_seen_w6": False,
    "mp_last_ip": "",         # the host address the joiner typed last time
}

# All starting weapons are available at tier 1. The legacy `weapon_unlocks`
# mapping remains in the save format for backward compatibility.
DEFAULT_WEAPON_UNLOCKS = {
    "pistol": True,
    "rifle": True,
    "shotgun": True,
    "sniper": True,
}

# Stable weapon order retained for old saves and UI helpers.
WEAPON_TIERS = ["pistol", "rifle", "shotgun", "sniper"]

SAVE_NAME = "swellfire_save.json"


class GameState:
    def __init__(self, storage_dir):
        self.storage_dir = storage_dir
        self.path = os.path.join(storage_dir, SAVE_NAME)
        self.data = self._load()

    def _default(self):
        return {
            "version": 1,
            "highest_unlocked": 1,                # highest level the player can enter
            "scores": {},                         # best score per level, e.g. {"7": 1820}
            "stars": {},                          # best stars per level, e.g. {"7": 2}
            "best_distance": {},                  # best distance per level (used for the score tie-break)
            "coins_balance": 300,                 # meta-currency for the shop (starting grant)
            # Booster balances (per the boosters registry). New boosters can be
            # added without bumping the save version — `_load` fills missing
            # keys from defaults.
            "grenade_balance": 0,
            "shield_balance": 0,
            "reinforce_balance": 0,
            "freeze_balance": 0,
            "overdrive_balance": 0,
            "magnet_balance": 0,
            "weapon_unlocks": dict(DEFAULT_WEAPON_UNLOCKS),
            # Per-weapon upgrade tiers (1 to weapons.MAX_TIER). All four
            # weapons start at tier 1; higher tiers deal more damage.
            "weapon_tiers": {"pistol": 1, "rifle": 1, "shotgun": 1, "sniper": 1},
            # Equipped weapon = which one the player starts every non-boss
            # level with. Default pistol; the shop lets the player tap any
            # owned weapon to make it the active starting weapon.
            "equipped_weapon": "pistol",
            # Permanent shop upgrade — +N to every non-boss level's starting
            # squad. Capped at +6 by `set_squad_bonus`.
            "squad_bonus": 0,
            # One-time UX hints already shown (so they don't repeat).
            "world2_hint_shown": False,
            "settings": dict(DEFAULT_SETTINGS),
        }


    @staticmethod
    def _safe_int(value, default=0):
        if isinstance(value, bool):
            return default
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return default

    @staticmethod
    def _safe_float(value, default=0.0):
        if isinstance(value, bool):
            return default
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            return default
        return result if math.isfinite(result) else default

    @classmethod
    def _normalise_level_map(cls, value, minimum=0, maximum=None):
        if not isinstance(value, dict):
            return {}
        result = {}
        for raw_level, raw_value in value.items():
            level = cls._safe_int(raw_level, 0)
            if not 1 <= level <= _TOTAL_LEVELS:
                continue
            parsed = max(minimum, cls._safe_int(raw_value, minimum))
            if maximum is not None:
                parsed = min(maximum, parsed)
            result[str(level)] = parsed
        return result

    @staticmethod
    def _normalise_setting(key, value):
        if key not in DEFAULT_SETTINGS:
            raise KeyError("unknown setting: {}".format(key))
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            if isinstance(value, bool):
                return value
            if value in (0, 1):
                return bool(value)
            return default
        if key == "volume":
            return max(0.0, min(1.0, GameState._safe_float(value, default)))
        if key == "top_safe_inset":
            return max(0.0, min(0.12, GameState._safe_float(value, default)))
        if key == "ga_style":
            return value if value in ("cautious", "balanced", "aggressive") else default
        if key == "ga_speed":
            return value if value in ("slow", "normal", "fast") else default
        if key == "mp_last_ip":
            return value.strip()[:253] if isinstance(value, str) else default
        return value

    def _normalise(self, data):
        """Return a complete, bounded save even when JSON was edited or corrupt."""
        if not isinstance(data, dict):
            return self._default()
        clean = self._default()
        clean["highest_unlocked"] = max(
            1, min(_TOTAL_LEVELS, self._safe_int(data.get("highest_unlocked"), 1))
        )
        clean["scores"] = self._normalise_level_map(data.get("scores"))
        clean["stars"] = self._normalise_level_map(data.get("stars"), maximum=3)
        clean["best_distance"] = self._normalise_level_map(data.get("best_distance"))
        clean["coins_balance"] = max(
            0, self._safe_int(data.get("coins_balance"), clean["coins_balance"])
        )
        for booster_id in BOOSTER_IDS:
            key = "{}_balance".format(booster_id)
            clean[key] = max(0, self._safe_int(data.get(key), 0))

        # Tier-1 ownership is universal in the current shop design. Retaining
        # the legacy mapping keeps old saves readable without reviving locks.
        clean["weapon_unlocks"] = dict(DEFAULT_WEAPON_UNLOCKS)
        raw_tiers = data.get("weapon_tiers")
        if not isinstance(raw_tiers, dict):
            raw_tiers = {}
        clean["weapon_tiers"] = {
            weapon_id: max(
                1,
                min(
                    weapons.MAX_TIER,
                    self._safe_int(raw_tiers.get(weapon_id), 1),
                ),
            )
            for weapon_id in weapons.WEAPONS
        }
        equipped = data.get("equipped_weapon")
        clean["equipped_weapon"] = equipped if equipped in weapons.WEAPONS else "pistol"
        clean["squad_bonus"] = max(
            0, min(SQUAD_BONUS_MAX, self._safe_int(data.get("squad_bonus"), 0))
        )
        clean["world2_hint_shown"] = bool(data.get("world2_hint_shown") is True)

        raw_settings = data.get("settings")
        if not isinstance(raw_settings, dict):
            raw_settings = {}
        clean["settings"] = {
            key: self._normalise_setting(key, raw_settings.get(key, default))
            for key, default in DEFAULT_SETTINGS.items()
        }
        return clean
    def _load(self):
        data = self._default()
        if os.path.exists(self.path):
            try:
                with open(self.path) as save_file:
                    loaded = json.load(save_file)
                if not isinstance(loaded, dict):
                    raise ValueError("save root must be a JSON object")
                data.update(loaded)
                return self._normalise(data)
            except Exception as error:
                print("Swellfire: could not read save, starting fresh.", error)
        return data

    def save(self):
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w") as save_file:
                json.dump(self.data, save_file)
            os.replace(tmp_path, self.path)
        except Exception as error:
            print("Swellfire: could not save game.", error)

    # progress
    @property
    def highest_unlocked(self):
        return self.data["highest_unlocked"]

    def is_unlocked(self, level_num):
        level_num = self._safe_int(level_num, 0)
        return 1 <= level_num <= self.highest_unlocked

    def unlock_up_to(self, level_num):
        level_num = max(1, min(_TOTAL_LEVELS, self._safe_int(level_num, 1)))
        if level_num > self.highest_unlocked:
            self.data["highest_unlocked"] = level_num
            self.save()

    def record_result(self, level_num, score, stars=0, distance=0):
        """Store a bounded level result; return whether the best score improved."""
        level_num = self._safe_int(level_num, 0)
        if not 1 <= level_num <= _TOTAL_LEVELS:
            return False
        score = max(0, self._safe_int(score, 0))
        stars = max(0, min(3, self._safe_int(stars, 0)))
        distance = max(0, self._safe_int(distance, 0))
        key = str(level_num)
        best = self.data["scores"].get(key, 0)
        improved = score > best
        if improved:
            self.data["scores"][key] = score
        if stars > self.data["stars"].get(key, 0):
            self.data["stars"][key] = stars
        if distance > self.data["best_distance"].get(key, 0):
            self.data["best_distance"][key] = distance
        self.save()
        return improved

    def _level_value(self, collection, level_num):
        level_num = self._safe_int(level_num, 0)
        if not 1 <= level_num <= _TOTAL_LEVELS:
            return 0
        return self.data[collection].get(str(level_num), 0)

    def get_score(self, level_num):
        return self._level_value("scores", level_num)

    def get_stars(self, level_num):
        return self._level_value("stars", level_num)

    def get_distance(self, level_num):
        return self._level_value("best_distance", level_num)

    def total_stars(self):
        return sum(self.data["stars"].values())

    def reset_progress(self):
        # Clear progress and scores but keep a detached copy of settings.
        settings = dict(self.data["settings"])
        self.data = self._default()
        self.data["settings"] = settings
        self.save()

    # coins / weapons
    @property
    def coins_balance(self):
        return self.data["coins_balance"]

    def add_coins(self, amount):
        amount = self._safe_int(amount, 0)
        if amount <= 0:
            return
        self.data["coins_balance"] += amount
        self.save()

    @property
    def grenade_balance(self):
        return self.get_booster_balance("grenade")

    def add_grenades(self, amount):
        self.add_booster("grenade", amount)

    def get_booster_balance(self, booster_id: str) -> int:
        if booster_id not in BOOSTER_IDS:
            return 0
        return max(0, self._safe_int(self.data.get("{}_balance".format(booster_id)), 0))

    def add_booster(self, booster_id: str, amount: int) -> None:
        if booster_id not in BOOSTER_IDS:
            return
        amount = self._safe_int(amount, 0)
        if amount == 0:
            return
        key = "{}_balance".format(booster_id)
        self.data[key] = max(0, self.get_booster_balance(booster_id) + amount)
        self.save()

    def is_weapon_unlocked(self, weapon_id):
        return weapon_id in weapons.WEAPONS

    def unlock_weapon(self, weapon_id):
        # Retained for compatibility with old callers; tier-1 weapons are free.
        if weapon_id in weapons.WEAPONS and not self.data["weapon_unlocks"].get(weapon_id):
            self.data["weapon_unlocks"][weapon_id] = True
            self.save()

    @property
    def starting_weapon(self) -> str:
        """The currently equipped tier-1-or-better starting weapon."""
        equipped = self.data.get("equipped_weapon", "pistol")
        return equipped if equipped in weapons.WEAPONS else "pistol"

    @property
    def max_world_reached(self) -> int:
        """Highest world the player has reached, from highest_unlocked."""
        return (max(1, self.highest_unlocked) - 1) // _LEVELS_PER_WORLD + 1

    def max_tier_for_world(self, world: int) -> int:
        """Weapon-tier cap at `world`: min(MAX_TIER, world) — W1=1 ... W6=6."""
        return min(weapons.MAX_TIER, max(1, self._safe_int(world, 1)))

    def max_squad_bonus_for_world(self, world: int) -> int:
        """Squad-bonus cap at `world`: min(SQUAD_BONUS_MAX, world-1)."""
        return min(SQUAD_BONUS_MAX, max(0, self._safe_int(world, 1) - 1))

    def get_weapon_tier(self, weapon_id: str) -> int:
        if weapon_id not in weapons.WEAPONS:
            return 1
        tiers = self.data.get("weapon_tiers", {})
        return max(1, min(weapons.MAX_TIER, self._safe_int(tiers.get(weapon_id), 1)))

    def equip_weapon(self, weapon_id: str) -> None:
        if weapon_id in weapons.WEAPONS:
            self.data["equipped_weapon"] = weapon_id
            self.save()

    def upgrade_weapon_tier(self, weapon_id: str, target_tier: int,
                            price: int) -> bool:
        """Atomically deduct coins and raise a known weapon by one tier."""
        if weapon_id not in weapons.WEAPONS:
            return False
        target_tier = self._safe_int(target_tier, 0)
        price = self._safe_int(price, -1)
        current = self.get_weapon_tier(weapon_id)
        if target_tier != current + 1 or price <= 0:
            return False
        if target_tier > self.max_tier_for_world(self.max_world_reached):
            return False
        if not self.can_afford(price):
            return False
        self.data["coins_balance"] -= price
        tiers = dict(self.data.get("weapon_tiers", {}))
        tiers[weapon_id] = target_tier
        self.data["weapon_tiers"] = tiers
        self.save()
        return True

    @property
    def squad_bonus(self) -> int:
        return max(0, min(SQUAD_BONUS_MAX, self._safe_int(self.data.get("squad_bonus"), 0)))

    def set_squad_bonus(self, n: int) -> None:
        self.data["squad_bonus"] = max(
            0, min(SQUAD_BONUS_MAX, self._safe_int(n, 0))
        )
        self.save()

    @property
    def world2_hint_shown(self) -> bool:
        return bool(self.data.get("world2_hint_shown", False))

    def mark_world2_hint_shown(self) -> None:
        self.data["world2_hint_shown"] = True
        self.save()

    # --- shop API --------------------------------------------------------

    def can_afford(self, price: int) -> bool:
        price = self._safe_int(price, -1)
        return price >= 0 and self.coins_balance >= price

    def spend_coins(self, price: int) -> bool:
        price = self._safe_int(price, -1)
        if price < 0 or not self.can_afford(price):
            return False
        self.data["coins_balance"] -= price
        self.save()
        return True

    def purchase_weapon(self, weapon_id: str, price: int) -> bool:
        # Legacy API: all current weapons are already owned at tier 1.
        if weapon_id not in weapons.WEAPONS or self.is_weapon_unlocked(weapon_id):
            return False
        return False

    def purchase_booster(self, booster_id: str, qty: int, price: int) -> bool:
        qty = self._safe_int(qty, 0)
        price = self._safe_int(price, -1)
        if booster_id not in BOOSTER_IDS or qty <= 0 or price <= 0:
            return False
        if not self.can_afford(price):
            return False
        self.data["coins_balance"] -= price
        key = "{}_balance".format(booster_id)
        self.data[key] = self.get_booster_balance(booster_id) + qty
        self.save()
        return True

    def purchase_squad_bonus(self, target: int, price: int) -> bool:
        target = self._safe_int(target, 0)
        price = self._safe_int(price, -1)
        if (target <= self.squad_bonus or target > SQUAD_BONUS_MAX
                or price <= 0):
            return False
        if target > self.max_squad_bonus_for_world(self.max_world_reached):
            return False
        if not self.can_afford(price):
            return False
        self.data["coins_balance"] -= price
        self.data["squad_bonus"] = target
        self.save()
        return True

    # settings
    def get_setting(self, key):
        return self.data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key, value):
        self.data["settings"][key] = self._normalise_setting(key, value)
        self.save()
