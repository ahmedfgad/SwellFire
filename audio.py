# Music and sound effects for GateRunner.
#
# This is a thin M1 stub: every public method is a no-op, but the interface
# matches what ui.py and main.py call. M2 replaces the body with a real
# SoundLoader-based implementation (menu track, per-world tracks, SFX bank)
# without ui.py needing to change. Keeping the stub here means ui.py can use
# audio calls today and the audio milestone is a self-contained swap.

import os


class AudioManager:
    def __init__(self, asset_dir=""):
        self.asset_dir = asset_dir
        self._music_dir = os.path.join(asset_dir, "music") if asset_dir else ""
        self._sfx_dir = os.path.join(asset_dir, "sfx") if asset_dir else ""
        self._music_on = True
        self._sfx_on = True
        self._volume = 1.0

    # --- music ---
    def play_menu_music(self):
        pass

    def play_level_music(self, world):
        # `world` is 1..NUM_WORLDS so a real impl can pick bg_music_worldN.wav.
        pass

    def stop_music(self):
        pass

    # --- sound effects ---
    def play_sfx(self, name):
        # `name` is a logical id like "click", "shoot", "hit", "gate_pickup",
        # "coin", "death", "victory", "boss_roar". M2 maps each to a file.
        pass

    # --- settings ---
    def apply_settings(self, state=None):
        # ui.SettingsScreen calls this after toggling music_on / sfx_on / volume
        # so the running tracks adjust without a screen reload.
        if state is not None:
            self._music_on = bool(state.get_setting("music_on"))
            self._sfx_on = bool(state.get_setting("sfx_on"))
            self._volume = float(state.get_setting("volume"))

    def attach_state(self, state):
        # Called once by main.py at startup so apply_settings() has a state to
        # read on later toggles.
        self._state = state
        self.apply_settings(state)
