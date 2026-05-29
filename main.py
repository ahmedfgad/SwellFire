"""GateRunner — auto-runner shooter in Kivy.

M1: screen scaffolding. All eleven meta screens (menu, world map, level select,
settings, about, guide, tutorial, autoplayer tuning, multiplayer menu, host,
join) are wired through a ScreenManager and persist progress to a JSON save
via state.GameState. Gameplay (auto-scroll world, hero, enemies, gates,
weapons, squad mechanic, boss waves, networked sync, GA autoplay) lands in
M3-M13 — see the plan at /home/ahmed-gad/.claude/plans/.
"""

import os

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.config import Config

# Portrait window on desktop: a tall, narrow playfield like a real auto-runner.
# Use (almost) the full screen height and derive a slim width from a 9:16 phone
# aspect so it mirrors the mobile build. Android / iOS use the orientation set in
# their build configs. Done before any window is created.
def _detect_screen_height():
    """Best-effort desktop screen height in px. Tries a few sources so it
    works whether or not tkinter is installed, and falls back to a
    phone-ish height when there's no display (headless)."""
    # 1. tkinter, if present.
    try:
        import tkinter
        _probe = tkinter.Tk()
        h = _probe.winfo_screenheight()
        _probe.destroy()
        if h > 0:
            return h
    except Exception:
        pass
    # 2. Parse `xrandr` (Linux/X) for the active "*"-marked mode "WxH".
    try:
        import subprocess
        out = subprocess.run(["xrandr"], capture_output=True, text=True,
                             timeout=2.0).stdout
        for line in out.splitlines():
            if "*" in line:
                res = line.split()[0]  # e.g. "3840x2160"
                return int(res.split("x")[1])
    except Exception:
        pass
    return 854  # headless / unknown — phone-ish default


def _portrait_window_size():
    aspect = 9.0 / 16.0  # width / height — standard phone portrait
    screen_h = _detect_screen_height()
    height = max(640, int(screen_h * 0.92))   # leave room for title bar / taskbar
    width = int(round(height * aspect))
    return width, height


_WIN_W, _WIN_H = _portrait_window_size()
Config.set("graphics", "width", str(_WIN_W))
Config.set("graphics", "height", str(_WIN_H))
Config.set("graphics", "resizable", "1")

import ui
import levels
import stresstest
import game
from audio import AudioManager
from state import GameState


def app():
    return App.get_running_app()


class GateRunnerApp(App):
    title = "GateRunner"

    # --- lifecycle ---------------------------------------------------------

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = None        # GameState, set in build()
        self.audio = None        # AudioManager, set in build()
        self.sm = None           # ScreenManager
        self.current_world = 1
        self.current_level = 1
        self.current_mode = "single"   # "single" | "versus"
        self.mp_net = None       # live NetHost / NetClient during a versus match
        self.mp_seed = 0

    def build(self):
        # State first so AudioManager can read settings on attach.
        storage_dir = self.user_data_dir or os.path.dirname(os.path.abspath(__file__))
        self.state = GameState(storage_dir)
        asset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        self.audio = AudioManager(asset_dir)
        self.audio.attach_state(self.state)

        self.sm = ScreenManager(transition=FadeTransition(duration=0.25))
        self.sm.add_widget(ui.MenuScreen(name="menu"))
        self.sm.add_widget(ui.WorldMapScreen(name="worldmap"))
        self.sm.add_widget(ui.LevelSelectScreen(name="levelselect"))
        self.sm.add_widget(ui.SettingsScreen(name="settings"))
        self.sm.add_widget(ui.AboutScreen(name="about"))
        self.sm.add_widget(ui.GuideScreen(name="guide"))
        self.sm.add_widget(ui.TutorialScreen(name="tutorial"))
        self.sm.add_widget(ui.AutoPlayerScreen(name="autoplayer"))
        self.sm.add_widget(ui.MultiplayerMenuScreen(name="multiplayer"))
        self.sm.add_widget(ui.HostScreen(name="mphost"))
        self.sm.add_widget(ui.JoinScreen(name="mpjoin"))
        self.sm.add_widget(ui.ShopScreen(name="shop"))
        self.sm.add_widget(game.GameScreen(name="game"))
        self.sm.add_widget(stresstest.StressTestScreen(name="stresstest"))
        return self.sm

    def on_stop(self):
        # Persist whatever changed during the session even if the OS killed us.
        if self.state is not None:
            self.state.save()
        if self.mp_net is not None:
            try:
                self.mp_net.stop()
            except Exception:
                pass
            self.mp_net = None

    # --- navigation called by ui screens -----------------------------------

    def go(self, screen_name):
        if self.sm is not None:
            self.sm.current = screen_name

    def open_world(self, world):
        self.current_world = int(world)
        self.go("levelselect")

    def start_level(self, level_num):
        self.current_level = int(level_num)
        self.current_mode = "single"
        self.current_world = ((self.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
        self._enter_game()

    def _enter_game(self):
        """Switch to the game screen, forcing a fresh on_leave/on_enter cycle.

        Kivy's ScreenManager short-circuits when `sm.current` is set to the
        screen it's already showing. That's the bug Retry / Next Level hit:
        the navigation looked like a no-op, so the level config never re-applied.
        We bounce through "levelselect" with an instant transition so the
        lifecycle methods run and the new level state takes effect.
        """
        if self.sm is None:
            return
        if self.sm.current == "game":
            old_dur = self.sm.transition.duration
            self.sm.transition.duration = 0
            self.sm.current = "levelselect"

            def _back_to_game(_dt):
                self.sm.transition.duration = old_dur
                self.sm.current = "game"

            Clock.schedule_once(_back_to_game, 0)
        else:
            self.sm.current = "game"

    # --- multiplayer hand-off (real impl in M13) ---------------------------

    def start_mp_host(self, mode, seed, network):
        self.current_mode = mode
        self.mp_seed = int(seed)
        self.mp_net = network
        self._enter_game()

    def start_mp_client(self, mode, seed, network):
        self.current_mode = mode
        self.mp_seed = int(seed)
        self.mp_net = network
        self._enter_game()


if __name__ == "__main__":
    GateRunnerApp().run()
