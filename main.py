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
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import sp, dp
from kivy.config import Config

# Lock to landscape on desktop (Android / iOS use the orientation set in their
# build configs). Done before any window is created.
Config.set("graphics", "width", "960")
Config.set("graphics", "height", "540")
Config.set("graphics", "resizable", "1")

import ui
import levels
import stresstest
from audio import AudioManager
from state import GameState


class PlaceholderGameScreen(ui.StyledScreen):
    """Stand-in gameplay screen used while M3-M13 wire up the real one.

    Shows the current level / world / mode and a Back button. Replaced when
    the real GameScreen lands (renderer in M3, gameplay through M13).
    """
    theme_world = 1

    def build(self):
        self.title_label = Label(
            text="", font_size=sp(34), bold=True,
            color=[1, 0.88, 0.2, 1],
            halign="center", valign="middle",
            size_hint=(0.9, 0.18), pos_hint={"center_x": 0.5, "top": 0.95},
        )
        self.title_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.root_layout.add_widget(self.title_label)

        self.info = Label(
            text="Gameplay lands across milestones M3-M13.\n"
                 "M1 only wires up the screens and the saved state.",
            font_size=sp(18), color=[1, 1, 1, 0.92],
            halign="center", valign="middle",
            size_hint=(0.8, 0.3), pos_hint={"center_x": 0.5, "center_y": 0.55},
        )
        self.info.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.root_layout.add_widget(self.info)

        row = BoxLayout(
            orientation="horizontal", spacing=dp(18),
            size_hint=(0.7, 0.12), pos_hint={"center_x": 0.5, "y": 0.08},
        )
        finish = ui.StyledButton(text="Mark complete (stub)", bg=[0.2, 0.7, 0.4, 1])
        finish.bind(on_release=lambda *_: self._mark_complete())
        back = ui.StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1])
        back.bind(on_release=lambda *_: self._exit())
        row.add_widget(finish)
        row.add_widget(back)
        self.root_layout.add_widget(row)

    def on_enter(self):
        running = app()
        if running.current_mode == "single" and running.current_level:
            world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
            theme = levels.get_world(world)
            self.title_label.text = "World {} - {}\nLevel {}".format(
                world, theme["name"], running.current_level)
            self.bg.set_theme(theme)
            running.audio.play_level_music(world)
        else:
            self.title_label.text = "Multiplayer Versus\n(mode: {})".format(running.current_mode)
            running.audio.play_level_music(1)

    def _mark_complete(self):
        """Stub that advances progression so the level-select screen can be
        exercised end-to-end during M1 testing. Real win condition + star
        scoring lands in M9-M10."""
        running = app()
        if running.current_mode == "single" and running.current_level:
            running.state.unlock_up_to(running.current_level + 1)
            running.state.record_result(running.current_level, score=100, stars=1, distance=500)
        running.go("menu")

    def _exit(self):
        running = app()
        # Tear down any active network link if this was a multiplayer match.
        if running.mp_net is not None:
            try:
                running.mp_net.send_leave()
            except Exception:
                pass
            running.mp_net.stop()
            running.mp_net = None
        running.go("menu")


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
        self.sm.add_widget(PlaceholderGameScreen(name="game"))
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
        self.go("game")

    # --- multiplayer hand-off (real impl in M13) ---------------------------

    def start_mp_host(self, mode, seed, network):
        self.current_mode = mode
        self.mp_seed = int(seed)
        self.mp_net = network
        self.go("game")

    def start_mp_client(self, mode, seed, network):
        self.current_mode = mode
        self.mp_seed = int(seed)
        self.mp_net = network
        self.go("game")


if __name__ == "__main__":
    GateRunnerApp().run()
