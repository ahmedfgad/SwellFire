# Saves game progress and settings for Swellfire.
# Everything is kept in one JSON file inside the folder the game passes in
# (the Kivy user_data_dir, which can be written to on all platforms).

import json
import os

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

# Starting weapon — pistol unlocked at boot, the rest gated behind shop
# purchases. `weapon_unlocks` records what the player owns; the highest
# weapon they've purchased is automatically the new default starting
# weapon (see `state.starting_weapon`).
DEFAULT_WEAPON_UNLOCKS = {
    "pistol": True,
    "rifle": False,
    "shotgun": False,
    "sniper": False,
}

# Order of weapons from worst → best. Used by `starting_weapon` to pick
# the highest-tier unlocked weapon as the default.
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
            "coins_balance": 0,                   # meta-currency for the shop
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
            # Per-weapon upgrade tiers (1-4). All four weapons start at
            # tier 1 (free). The shop sells tier 2 → 3 → 4 upgrades; higher
            # tier → more damage per projectile.
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

    def _load(self):
        data = self._default()
        if os.path.exists(self.path):
            try:
                with open(self.path) as save_file:
                    loaded = json.load(save_file)
                data.update(loaded)
                # Fill in any setting / unlock that an older save did not have.
                settings = dict(DEFAULT_SETTINGS)
                settings.update(data.get("settings", {}))
                data["settings"] = settings
                unlocks = dict(DEFAULT_WEAPON_UNLOCKS)
                unlocks.update(data.get("weapon_unlocks", {}))
                data["weapon_unlocks"] = unlocks
                return data
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
        return level_num <= self.data["highest_unlocked"]

    def unlock_up_to(self, level_num):
        if level_num > self.data["highest_unlocked"]:
            self.data["highest_unlocked"] = level_num
            self.save()

    def record_result(self, level_num, score, stars=0, distance=0):
        # Store a level result. Returns True if the score is a new best.
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

    def get_score(self, level_num):
        return self.data["scores"].get(str(level_num), 0)

    def get_stars(self, level_num):
        return self.data["stars"].get(str(level_num), 0)

    def get_distance(self, level_num):
        return self.data["best_distance"].get(str(level_num), 0)

    def total_stars(self):
        return sum(self.data["stars"].values())

    def reset_progress(self):
        # Clear progress and scores but keep the player's settings.
        settings = self.data["settings"]
        self.data = self._default()
        self.data["settings"] = settings
        self.save()

    # coins / weapons (the shop wiring lands in a later milestone but the store
    # is in place so M1's settings/about screens can show real numbers)
    @property
    def coins_balance(self):
        return self.data["coins_balance"]

    def add_coins(self, amount):
        self.data["coins_balance"] = max(0, self.data["coins_balance"] + int(amount))
        self.save()

    @property
    def grenade_balance(self):
        return int(self.data.get("grenade_balance", 0))

    def add_grenades(self, amount):
        self.data["grenade_balance"] = max(0, self.grenade_balance + int(amount))
        self.save()

    def get_booster_balance(self, booster_id: str) -> int:
        return int(self.data.get(f"{booster_id}_balance", 0))

    def add_booster(self, booster_id: str, amount: int) -> None:
        key = f"{booster_id}_balance"
        current = int(self.data.get(key, 0))
        self.data[key] = max(0, current + int(amount))
        self.save()

    def is_weapon_unlocked(self, weapon_id):
        return bool(self.data["weapon_unlocks"].get(weapon_id, False))

    def unlock_weapon(self, weapon_id):
        if not self.is_weapon_unlocked(weapon_id):
            self.data["weapon_unlocks"][weapon_id] = True
            self.save()

    @property
    def starting_weapon(self) -> str:
        """The player's currently-equipped weapon (set via the shop). All
        four weapons are owned at tier 1 by default, so this is whichever
        one the player tapped to equip — pistol initially.

        Boss levels override with their own `starting_weapon` field.
        """
        equipped = self.data.get("equipped_weapon", "pistol")
        if equipped not in DEFAULT_WEAPON_UNLOCKS:
            return "pistol"
        return equipped

    def get_weapon_tier(self, weapon_id: str) -> int:
        tiers = self.data.get("weapon_tiers", {})
        return max(1, int(tiers.get(weapon_id, 1)))

    def equip_weapon(self, weapon_id: str) -> None:
        if weapon_id in DEFAULT_WEAPON_UNLOCKS:
            self.data["equipped_weapon"] = weapon_id
            self.save()

    def upgrade_weapon_tier(self, weapon_id: str, target_tier: int,
                            price: int) -> bool:
        """Raise this weapon's tier from current to target. Returns True
        on success (deducts coins, persists)."""
        current = self.get_weapon_tier(weapon_id)
        if target_tier != current + 1:
            return False    # only one tier at a time
        if target_tier > 4:
            return False
        if not self.spend_coins(price):
            return False
        tiers = dict(self.data.get("weapon_tiers", {}))
        tiers[weapon_id] = target_tier
        self.data["weapon_tiers"] = tiers
        self.save()
        return True

    @property
    def squad_bonus(self) -> int:
        return int(self.data.get("squad_bonus", 0))

    def set_squad_bonus(self, n: int) -> None:
        self.data["squad_bonus"] = max(0, min(6, int(n)))
        self.save()

    @property
    def world2_hint_shown(self) -> bool:
        return bool(self.data.get("world2_hint_shown", False))

    def mark_world2_hint_shown(self) -> None:
        self.data["world2_hint_shown"] = True
        self.save()

    # --- shop API --------------------------------------------------------
    #
    # The shop UI calls these. Each returns True if the purchase succeeded
    # (caller used them to gate the button). Coins are deducted atomically;
    # if the resulting state is rejected the deduction is rolled back.

    def can_afford(self, price: int) -> bool:
        return self.coins_balance >= int(price)

    def spend_coins(self, price: int) -> bool:
        price = int(price)
        if not self.can_afford(price):
            return False
        self.data["coins_balance"] -= price
        self.save()
        return True

    def purchase_weapon(self, weapon_id: str, price: int) -> bool:
        if self.is_weapon_unlocked(weapon_id):
            return False
        if not self.spend_coins(price):
            return False
        self.data["weapon_unlocks"][weapon_id] = True
        self.save()
        return True

    def purchase_booster(self, booster_id: str, qty: int, price: int) -> bool:
        if not self.spend_coins(price):
            return False
        self.add_booster(booster_id, int(qty))
        return True

    def purchase_squad_bonus(self, target: int, price: int) -> bool:
        if self.squad_bonus >= target:
            return False
        if not self.spend_coins(price):
            return False
        self.set_squad_bonus(target)
        return True

    # settings
    def get_setting(self, key):
        return self.data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key, value):
        self.data["settings"][key] = value
        self.save()
