# Plays the music and sound effects and respects the player's settings.
#
# One menu track + a per-world track (world 1..NUM_WORLDS), plus a small bank
# of short SFX. Files are WAV under assets/music/ and assets/sfx/. A missing
# file is silent rather than fatal — so the audio bank can grow milestone by
# milestone without breaking the build.
#
# Pattern is the same as CoinTex's audio.py (Kivy SoundLoader, one menu/world
# track plus a SFX dict, stop-before-play to avoid stale channels). The
# difference: AudioManager is created without a state object and is attached
# to one later via attach_state(state), which suits GateRunner's startup
# order (audio module imported before main builds the GameState).

import os

from kivy.core.audio import SoundLoader

import levels


MENU_MUSIC = "bg_music_menu.wav"


def world_music_name(world):
    return "bg_music_world{}.wav".format(world)


# logical name in code -> wav file in assets/sfx
SFX_FILES = {
    "click":          "click.wav",
    "shoot":          "shoot.wav",
    "hit":            "hit.wav",
    "enemy_death":    "enemy_death.wav",
    "gate_pickup":    "gate_pickup.wav",
    "coin":           "coin.wav",
    "level_complete": "level_complete.wav",
    "death":          "death.wav",
    "victory":        "victory.wav",
    "reload":         "reload.wav",
}


class AudioManager:
    def __init__(self, asset_dir=""):
        self.asset_dir = asset_dir
        self._music_dir = os.path.join(asset_dir, "music") if asset_dir else ""
        self._sfx_dir = os.path.join(asset_dir, "sfx") if asset_dir else ""
        self._state = None
        self._menu = None
        self._world = {}      # world number -> Sound
        self._sfx = {}
        self._current = None  # ("menu",) or ("world", N)
        self._load()

    # --- one-time load -----------------------------------------------------

    def _load_sound(self, directory, filename, loop=False):
        if not directory:
            return None
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            return None
        sound = SoundLoader.load(path)
        if sound is not None:
            sound.loop = loop
        return sound

    def _load(self):
        self._menu = self._load_sound(self._music_dir, MENU_MUSIC, loop=True)
        for world in range(1, levels.NUM_WORLDS + 1):
            self._world[world] = self._load_sound(
                self._music_dir, world_music_name(world), loop=True)
        for name, filename in SFX_FILES.items():
            self._sfx[name] = self._load_sound(self._sfx_dir, filename, loop=False)

    # --- state ------------------------------------------------------------

    def attach_state(self, state):
        self._state = state
        self.apply_settings(state)

    def _get_setting(self, key, default=None):
        if self._state is None:
            return default
        return self._state.get_setting(key)

    def _volume(self):
        try:
            return float(self._get_setting("volume", 1.0))
        except (TypeError, ValueError):
            return 1.0

    # --- music routing ----------------------------------------------------

    def _sound_for(self, key):
        if key is None:
            return None
        if key[0] == "menu":
            return self._menu
        return self._world.get(key[1])

    def _all_music(self):
        return [self._menu] + list(self._world.values())

    def play_menu_music(self):
        self._switch(("menu",))

    def play_level_music(self, world):
        self._switch(("world", int(world)))

    def _switch(self, key):
        if self._current == key:
            current = self._sound_for(key)
            if current is not None and current.state == "play":
                return
        self.stop_music()
        self._current = key
        if not self._get_setting("music_on", True):
            return
        sound = self._sound_for(key)
        if sound is not None:
            sound.stop()
            sound.volume = self._volume()
            sound.play()

    def stop_music(self):
        for sound in self._all_music():
            if sound is not None and sound.state == "play":
                sound.stop()

    # --- sfx --------------------------------------------------------------

    def play_sfx(self, name):
        if not self._get_setting("sfx_on", True):
            return
        sound = self._sfx.get(name)
        if sound is not None:
            sound.volume = self._volume()
            if sound.state == "play":
                sound.stop()
            sound.play()

    # --- settings push (called from SettingsScreen) -----------------------

    def apply_settings(self, state=None):
        if state is not None:
            self._state = state
        volume = self._volume()
        for sound in self._all_music():
            if sound is not None:
                sound.volume = volume
        if not self._get_setting("music_on", True):
            self.stop_music()
        elif self._current is not None:
            current = self._sound_for(self._current)
            if current is not None and current.state != "play":
                current.volume = volume
                current.play()
