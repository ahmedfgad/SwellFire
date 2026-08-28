"""Swellfire — auto-runner shooter in Kivy.

M1: screen scaffolding. All eleven meta screens (menu, world map, level select,
settings, about, guide, tutorial, autoplayer tuning, multiplayer menu, host,
join) are wired through a ScreenManager and persist progress to a JSON save
via state.GameState. Gameplay (auto-scroll world, hero, enemies, gates,
weapons, squad mechanic, boss waves, networked sync, GA autoplay) lands in
M3-M13 — see the plan at /home/ahmed-gad/.claude/plans/.
"""

import os
import sys

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.uix.modalview import ModalView
from kivy.config import Config
from kivy.resources import resource_add_path

# Portrait window on desktop, sized to FIT the user's screen so it never opens
# taller than the display. A hard-coded tall height (e.g. 960) can exceed a
# laptop's usable height, pushing the title bar / resize edges off-screen and
# making the window awkward to move or resize. We derive a 9:16 portrait size
# from ~90% of the detected screen height instead, and keep the window freely
# resizable (the UI adapts to any size). Android / iOS use the orientation set
# in their own build configs. Done before any window is created.
def _detect_screen_height():
    """Best-effort desktop screen height in px, without creating a window.
    Tries xrandr (X / XWayland) then tkinter, falling back to a safe phone-ish
    height when there's no display (headless capture / CI)."""
    try:
        import subprocess
        out = subprocess.run(["xrandr"], capture_output=True, text=True,
                             timeout=2.0).stdout
        for line in out.splitlines():
            if "*" in line:                      # the active "*"-marked mode
                return int(line.split()[0].split("x")[1])
    except Exception:
        pass
    try:
        import tkinter
        _probe = tkinter.Tk()
        h = _probe.winfo_screenheight()
        _probe.destroy()
        if h > 0:
            return h
    except Exception:
        pass
    return 768                                   # safe default that fits laptops


def _portrait_window_size():
    """A 9:16 portrait size ~90% of the screen height, never taller than the
    screen minus room for window chrome."""
    screen_h = _detect_screen_height()
    height = max(560, min(int(screen_h * 0.90), screen_h - 72))
    width = int(round(height * 9.0 / 16.0))
    return width, height


_WIN_W, _WIN_H = _portrait_window_size()
Config.set("graphics", "width", str(_WIN_W))
Config.set("graphics", "height", str(_WIN_H))
Config.set("graphics", "resizable", "1")

# Asset root. When frozen by PyInstaller the bundled assets are unpacked under
# the onefile extraction dir (sys._MEIPASS); in dev they live next to this file.
# Register it on Kivy's resource search path so every relative "assets/..." path
# resolves regardless of the current working directory. Without this, sprite
# PNGs (CoreImage) and music/sfx (SoundLoader) are looked up via resource_find,
# whose default search path is the cwd — so the packaged binary crashes the
# moment it's launched from any directory other than the one containing assets/
# (resource_find -> None -> Kivy's load_from_filename(None) -> AttributeError).
if getattr(sys, "frozen", False):
    ASSET_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    ASSET_ROOT = os.path.dirname(os.path.abspath(__file__))
resource_add_path(ASSET_ROOT)

import ui
import levels
import stresstest
import game
from audio import AudioManager
from state import GameState


def app():
    return App.get_running_app()


class SwellfireApp(App):
    title = "Swellfire"

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
        self._resume_game_after_pause = False

    def build(self):
        # State first so AudioManager can read settings on attach.
        storage_dir = self.user_data_dir or os.path.dirname(os.path.abspath(__file__))
        self.state = GameState(storage_dir)
        asset_dir = os.path.join(ASSET_ROOT, "assets")
        self.audio = AudioManager(asset_dir)
        self.audio.attach_state(self.state)

        # Brand the window/taskbar with the Swellfire icon (Linux/Win/Mac).
        # Use ASSET_ROOT so it resolves in a frozen build too (CLAUDE.md path
        # gotcha); skip silently if the file is missing.
        from kivy.core.window import Window
        icon_path = os.path.join(ASSET_ROOT, "icon.png")
        if os.path.exists(icon_path):
            self.icon = icon_path
            try:
                Window.set_icon(icon_path)
            except Exception:
                pass

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
        Window.bind(on_keyboard=self._on_keyboard)
        return self.sm

    def _game_screen(self):
        if self.sm is None:
            return None
        try:
            return self.sm.get_screen("game")
        except Exception:
            return None

    def on_pause(self):
        """Freeze active play and checkpoint state before mobile backgrounding."""
        self._resume_game_after_pause = False
        game_screen = self._game_screen()
        if self.sm is not None and self.sm.current == "game" and game_screen is not None:
            self._resume_game_after_pause = game_screen.pause_for_lifecycle()
        if self.state is not None:
            self.state.save()
        if self.audio is not None:
            self.audio.stop_music()
        # Returning True tells Kivy/Android that the app can be resumed.
        return True

    def on_resume(self):
        game_screen = self._game_screen()
        if (
            self.sm is not None
            and self.sm.current == "game"
            and game_screen is not None
            and self._resume_game_after_pause
        ):
            game_screen.resume_from_lifecycle()
        elif self.sm is not None and self.sm.current != "game" and self.audio is not None:
            self.audio.play_menu_music()
        self._resume_game_after_pause = False

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
        try:
            from kivy.core.window import Window
            Window.unbind(on_keyboard=self._on_keyboard)
        except Exception:
            pass

    def _on_keyboard(self, _window, key, *_args):
        """Route Escape/legacy Android Back through the visible app hierarchy."""
        if key != 27 or self.sm is None:
            return False

        # Non-auto-dismiss dialogs need an explicit cancel/resume action;
        # navigating the ScreenManager underneath them leaves an orphan modal.
        try:
            from kivy.core.window import Window
            for child in list(Window.children):
                if isinstance(child, ModalView) and getattr(child, "_is_open", False):
                    handler = getattr(child, "handle_back", None)
                    if handler is not None:
                        handler()
                    return True
        except Exception:
            return True

        current = self.sm.current
        screen = self.sm.current_screen
        if current == "menu":
            return False
        if current == "game":
            if getattr(screen, "_level_ended", False):
                screen._exit()
            else:
                screen._open_pause()
            return True
        if current == "levelselect":
            self.go("worldmap")
        elif current in ("autoplayer", "stresstest"):
            self.go("settings")
        elif current in ("mphost", "mpjoin"):
            screen._leave()
        elif current == "tutorial":
            screen._finish()
        else:
            self.go("menu")
        return True

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
    SwellfireApp().run()
