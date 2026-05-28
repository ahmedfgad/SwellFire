# Menu, navigation and settings screens for GateRunner.
#
# Structure is ported from CoinTex's ui.py: a themed Background widget on every
# screen, a StyledButton with click feedback, ConfirmDialog / InfoDialog modals,
# and the eleven Screen subclasses the brief requires (menu, world map, level
# select, settings, about, guide, tutorial, autoplayer tuning, multiplayer
# menu, host, join). Content is rewritten for the GateRunner gate-runner /
# squad-multiplier loop.

import random
import threading

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.slider import Slider
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import sp, dp
from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty

import graphics
import levels
import net


ABOUT_TEXT = (
    "GateRunner\n"
    "\n"
    "An auto-runner shooter in the squad-multiplier genre. Your character runs "
    "forward on their own; you only steer left and right and choose which gate "
    "to pass through. Gates apply effects to your crowd of runners: x2 doubles "
    "the squad, +5 adds five, SHOTGUN swaps every runner's weapon.\n"
    "\n"
    "Waves of enemies stream toward you and the whole squad auto-fires at the "
    "nearest target. The wider your crowd, the more shots per second. Bring as "
    "much firepower as you can to the boss waiting at the end of each world.\n"
    "\n"
    "There are 6 worlds with 10 levels each, 60 levels in total. The further "
    "you go, the denser the spawns and the more punishing the bosses.\n"
    "\n"
    "GateRunner is built with Python and the Kivy framework. The same codebase "
    "runs on Windows, Linux, macOS, Android and iPhone.\n"
    "\n"
    "Tap the Auto button during a level to let a small genetic algorithm play "
    "for you. It picks gates that maximise expected firepower and steers around "
    "hazards. Tune its style and reaction speed from Settings.\n"
    "\n"
    "Multiplayer lets two people race in the same shared world. One device "
    "hosts, the other joins by typing the host's address. Both players' "
    "runners are drawn on each device's screen; whoever has the higher score "
    "at the finish line wins.\n"
    "\n"
    "Created by Ahmed Fawzy Gad.\n"
    "Email: ahmed.f.gad@gmail.com\n"
    "Source code: https://github.com/ahmedfgad/GateRunner"
)


def app():
    return App.get_running_app()


# --- shared widgets --------------------------------------------------------

class StyledButton(ButtonBehavior, Label):
    bg = ListProperty([0.20, 0.55, 0.95, 1])

    def __init__(self, **kwargs):
        kwargs.setdefault("font_size", sp(22))
        kwargs.setdefault("bold", True)
        kwargs.setdefault("color", [1, 1, 1, 1])
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color(*self.bg)
            self._rect = RoundedRectangle(radius=[dp(12)])
        self.bind(pos=self._sync, size=self._sync, bg=self._sync_color)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _sync_color(self, *_):
        self._color.rgba = self.bg

    def on_press(self):
        running = app()
        if running is not None and getattr(running, "audio", None):
            running.audio.play_sfx("click")
        self._color.rgba = [self.bg[0] * 0.8, self.bg[1] * 0.8, self.bg[2] * 0.8, self.bg[3]]

    def on_release(self):
        self._color.rgba = self.bg


class ConfirmDialog(ModalView):
    def __init__(self, message, on_yes, yes_text="Yes", no_text="No", on_no=None, **kwargs):
        super().__init__(size_hint=(0.75, 0.45), auto_dismiss=False, **kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(16))
        with box.canvas.before:
            Color(0.12, 0.14, 0.22, 0.98)
            self._bg = RoundedRectangle(radius=[dp(16)])
        box.bind(pos=lambda *a: setattr(self._bg, "pos", box.pos),
                 size=lambda *a: setattr(self._bg, "size", box.size))
        box.add_widget(Label(text=message, font_size=sp(20), halign="center",
                             valign="middle", color=[1, 1, 1, 1]))
        row = BoxLayout(orientation="horizontal", spacing=dp(16), size_hint_y=0.4)
        no_btn = StyledButton(text=no_text, bg=[0.45, 0.45, 0.5, 1])
        yes_btn = StyledButton(text=yes_text, bg=[0.85, 0.3, 0.3, 1])

        def cancel(*_):
            self.dismiss()
            if on_no:
                on_no()
        no_btn.bind(on_release=cancel)

        def confirm(*_):
            self.dismiss()
            on_yes()
        yes_btn.bind(on_release=confirm)
        row.add_widget(no_btn)
        row.add_widget(yes_btn)
        box.add_widget(row)
        self.add_widget(box)


class InfoDialog(ModalView):
    """Simple titled message box with one OK button.

    Used for the one-shot hints (first gate seen, first boss seen, etc.).
    """

    def __init__(self, title, message, on_ok=None, ok_text="Got it", **kwargs):
        super().__init__(size_hint=(0.82, 0.5), auto_dismiss=False, **kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(22), spacing=dp(14))
        with box.canvas.before:
            Color(0.12, 0.14, 0.22, 0.98)
            self._bg = RoundedRectangle(radius=[dp(16)])
        box.bind(pos=lambda *a: setattr(self._bg, "pos", box.pos),
                 size=lambda *a: setattr(self._bg, "size", box.size))
        box.add_widget(Label(text=title, font_size=sp(28), bold=True,
                             color=[1, 0.85, 0.2, 1], size_hint_y=0.3))
        body = Label(text=message, font_size=sp(19), halign="center", valign="middle",
                     color=[1, 1, 1, 1], size_hint_y=0.48)
        body.bind(width=lambda *a: setattr(body, "text_size", (body.width, None)))
        box.add_widget(body)
        ok = StyledButton(text=ok_text, bg=[0.2, 0.7, 0.4, 1], size_hint_y=0.22)

        def confirm(*_):
            self.dismiss()
            if on_ok:
                on_ok()
        ok.bind(on_release=confirm)
        box.add_widget(ok)
        self.add_widget(box)


class StyledScreen(Screen):
    """Screen with a themed gradient background drawn in code."""
    theme_world = 6   # default world index for the background

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_layout = FloatLayout()
        self.bg = graphics.Background(levels.get_world(self.theme_world), size_hint=(1, 1))
        self.root_layout.add_widget(self.bg)
        self.add_widget(self.root_layout)
        self.build()

    def build(self):
        pass


class LevelButton(StyledButton):
    """Level tile: label on top, a 3-star rating drawn at the bottom."""
    stars = NumericProperty(0)

    def __init__(self, **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "top")
        super().__init__(**kwargs)
        self.bind(stars=self._draw_stars, pos=self._draw_stars, size=self._on_size)
        self._on_size()

    def _on_size(self, *_):
        self.text_size = (self.width, self.height)
        self._draw_stars()

    def _draw_stars(self, *_):
        self.canvas.after.clear()
        if self.width <= 1:
            return
        x, y = self.pos
        w, h = self.size
        slot = w * 0.24
        outer = slot * 0.40
        start = x + (w - slot * 3) / 2
        cy = y + h * 0.18
        with self.canvas.after:
            for i in range(3):
                cx = start + slot * (i + 0.5)
                color = (1.0, 0.85, 0.2, 1) if i < self.stars else (1.0, 1.0, 1.0, 0.22)
                graphics.draw_star(cx, cy, outer, color)


# --- screens ---------------------------------------------------------------

class MenuScreen(StyledScreen):
    theme_world = 6

    def build(self):
        box = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(18),
                        size_hint=(0.7, 0.86), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="GateRunner", font_size=sp(56), bold=True,
                             color=[1, 0.85, 0.2, 1], size_hint_y=0.32))

        play = StyledButton(text="Play", bg=[0.2, 0.7, 0.4, 1])
        multiplayer = StyledButton(text="Multiplayer", bg=[0.55, 0.4, 0.8, 1])
        how = StyledButton(text="How to play", bg=[0.9, 0.6, 0.2, 1])
        guide = StyledButton(text="Guide", bg=[0.85, 0.5, 0.25, 1])
        about = StyledButton(text="About", bg=[0.25, 0.5, 0.9, 1])
        settings = StyledButton(text="Settings", bg=[0.4, 0.45, 0.55, 1])

        play.bind(on_release=lambda *_: app().go("worldmap"))
        multiplayer.bind(on_release=lambda *_: app().go("multiplayer"))
        how.bind(on_release=lambda *_: app().go("tutorial"))
        guide.bind(on_release=lambda *_: app().go("guide"))
        about.bind(on_release=lambda *_: app().go("about"))
        settings.bind(on_release=lambda *_: app().go("settings"))

        for btn in (play, multiplayer, how, guide, about, settings):
            box.add_widget(btn)

        self.stars = Label(text="", font_size=sp(18), color=[1, 1, 1, 0.85], size_hint_y=0.18)
        box.add_widget(self.stars)
        self.root_layout.add_widget(box)

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        self.stars.text = "Stars collected: {}    Coins: {}".format(
            running.state.total_stars(), running.state.coins_balance)
        # First-launch auto-tutorial — same one-shot flag CoinTex uses.
        if not running.state.get_setting("tutorial_seen"):
            Clock.schedule_once(lambda dt: running.go("tutorial"), 0)


class WorldMapScreen(StyledScreen):
    theme_world = 6

    def build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        outer.add_widget(Label(text="Select World", font_size=sp(34), bold=True,
                               size_hint_y=0.15, color=[1, 1, 1, 1]))
        self.grid = GridLayout(cols=3, spacing=dp(16), size_hint_y=0.7)
        outer.add_widget(self.grid)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.15)
        back.bind(on_release=lambda *_: app().go("menu"))
        outer.add_widget(back)
        self.root_layout.add_widget(outer)

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        self.grid.clear_widgets()
        for world in range(1, levels.NUM_WORLDS + 1):
            theme = levels.get_world(world)
            first_level = (world - 1) * levels.LEVELS_PER_WORLD + 1
            unlocked = running.state.is_unlocked(first_level)
            label = theme["name"] if unlocked else "Locked"
            color = [theme["top"][0], theme["top"][1], theme["top"][2], 1] if unlocked else [0.3, 0.3, 0.35, 1]
            btn = StyledButton(text="{}\n{}".format(world, label), bg=color, halign="center")
            if unlocked:
                btn.bind(on_release=lambda b, w=world: app().open_world(w))
            self.grid.add_widget(btn)


class LevelSelectScreen(StyledScreen):
    theme_world = 1

    def build(self):
        self.outer = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        self.title_label = Label(text="", font_size=sp(30), bold=True,
                                 size_hint_y=0.14, color=[1, 1, 1, 1])
        self.outer.add_widget(self.title_label)
        self.grid = GridLayout(cols=5, spacing=dp(12), size_hint_y=0.72)
        self.outer.add_widget(self.grid)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.14)
        back.bind(on_release=lambda *_: app().go("worldmap"))
        self.outer.add_widget(back)
        self.root_layout.add_widget(self.outer)

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        world = running.current_world
        theme = levels.get_world(world)
        self.title_label.text = "World {}  -  {}".format(world, theme["name"])
        self.bg.set_theme(theme)
        self.grid.clear_widgets()
        for lvl in levels.levels_in_world(world):
            index = lvl["index"]
            unlocked = running.state.is_unlocked(index)
            stars = running.state.get_stars(index)
            label = "W{} L{}".format(lvl["world"], lvl["world_index"])
            if unlocked:
                btn = LevelButton(text=label, bg=[0.25, 0.55, 0.9, 1])
                btn.stars = stars
                btn.bind(on_release=lambda b, i=index: running.start_level(i))
            else:
                btn = StyledButton(text=label + "\nLocked",
                                   bg=[0.3, 0.3, 0.35, 1], halign="center")
            self.grid.add_widget(btn)


class SettingsScreen(StyledScreen):
    theme_world = 6

    def build(self):
        box = BoxLayout(orientation="vertical", padding=dp(26), spacing=dp(14),
                        size_hint=(0.8, 0.9), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="Settings", font_size=sp(34), bold=True,
                             size_hint_y=0.12, color=[1, 1, 1, 1]))

        self.music_btn = StyledButton(size_hint_y=0.12)
        self.music_btn.bind(on_release=lambda *_: self._toggle("music_on"))
        box.add_widget(self.music_btn)

        self.sfx_btn = StyledButton(size_hint_y=0.12)
        self.sfx_btn.bind(on_release=lambda *_: self._toggle("sfx_on"))
        box.add_widget(self.sfx_btn)

        vol_row = BoxLayout(orientation="horizontal", size_hint_y=0.12, spacing=dp(10))
        vol_row.add_widget(Label(text="Volume", font_size=sp(20), size_hint_x=0.35, color=[1, 1, 1, 1]))
        self.volume = Slider(min=0, max=1, value=1, step=0.05, size_hint_x=0.65)
        self.volume.bind(value=self._on_volume)
        vol_row.add_widget(self.volume)
        box.add_widget(vol_row)

        auto = StyledButton(text="Auto Player", bg=[0.3, 0.6, 0.55, 1], size_hint_y=0.12)
        auto.bind(on_release=lambda *_: app().go("autoplayer"))
        box.add_widget(auto)

        reset = StyledButton(text="Reset progress", bg=[0.85, 0.35, 0.3, 1], size_hint_y=0.12)
        reset.bind(on_release=lambda *_: self._confirm_reset())
        box.add_widget(reset)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.12)
        back.bind(on_release=lambda *_: app().go("menu"))
        box.add_widget(back)
        self.root_layout.add_widget(box)

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        self.volume.value = running.state.get_setting("volume")
        self._refresh_labels()

    def _refresh_labels(self):
        running = app()
        on = running.state.get_setting("music_on")
        self.music_btn.text = "Music: {}".format("On" if on else "Off")
        self.music_btn.bg = [0.2, 0.7, 0.4, 1] if on else [0.5, 0.5, 0.55, 1]
        on = running.state.get_setting("sfx_on")
        self.sfx_btn.text = "Sound effects: {}".format("On" if on else "Off")
        self.sfx_btn.bg = [0.2, 0.7, 0.4, 1] if on else [0.5, 0.5, 0.55, 1]

    def _toggle(self, key):
        running = app()
        new_value = not running.state.get_setting(key)
        running.state.set_setting(key, new_value)
        running.audio.apply_settings(running.state)
        self._refresh_labels()

    def _on_volume(self, _slider, value):
        running = app()
        running.state.set_setting("volume", round(value, 2))
        running.audio.apply_settings(running.state)

    def _confirm_reset(self):
        def do_reset():
            running = app()
            running.state.reset_progress()
            running.audio.apply_settings(running.state)
        ConfirmDialog("Reset all progress?\nThis cannot be undone.", do_reset,
                      yes_text="Reset", no_text="Cancel").open()


class AboutScreen(StyledScreen):
    theme_world = 6

    def build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        outer.add_widget(Label(text="About", font_size=sp(34), bold=True,
                               size_hint_y=0.12, color=[1, 1, 1, 1]))
        scroll = ScrollView(size_hint_y=0.74)
        text = Label(text=ABOUT_TEXT, font_size=sp(20), color=[1, 1, 1, 1],
                     halign="left", valign="top", padding=(dp(8), dp(8)))
        text.bind(width=lambda *_: setattr(text, "text_size", (text.width, None)))
        text.bind(texture_size=lambda *_: setattr(text, "height", text.texture_size[1]))
        text.size_hint_y = None
        scroll.add_widget(text)
        outer.add_widget(scroll)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.14)
        back.bind(on_release=lambda *_: app().go("menu"))
        outer.add_widget(back)
        self.root_layout.add_widget(outer)

    def on_enter(self):
        app().audio.play_menu_music()


# --- guide content for the gate-runner loop -------------------------------

GUIDE_ROWS = [
    ("runner",   "Drag left or right anywhere on the screen to steer your runner. The whole "
                 "squad follows in formation and auto-fires at the nearest enemy."),
    ("gate",     "Gates appear in pairs ahead. Pass through one to apply its effect: x2 doubles "
                 "the squad, +N adds runners, and weapon gates swap every runner's gun."),
    ("enemy",    "Enemy waves run toward you. Heavies take more hits. Touching an enemy costs "
                 "you a runner from the front of the squad."),
    ("projectile", "Each runner fires automatically. The wider your crowd, the more shots per "
                 "second and the more lanes you cover."),
    ("coin",     "Pick up coins between waves. Spend them between runs to upgrade weapons in "
                 "the shop."),
]

GUIDE_TIPS = [
    "Always pick x2 over +1: doubling the squad doubles your firepower for the same gate cost.",
    "Shotguns crush dense waves; snipers punch through heavies. Choose weapon gates with the next wave in mind.",
    "Tap Auto during a level to let a genetic algorithm pick gates for you. Tune it under Settings > Auto Player.",
    "Each world ends in a boss with attack patterns. Arrive with as many runners as possible.",
]


class GuideScreen(StyledScreen):
    theme_world = 3

    def build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(10))
        outer.add_widget(Label(text="Game Guide", font_size=sp(32), bold=True,
                               size_hint_y=0.10, color=[1, 1, 1, 1]))

        scroll = ScrollView(size_hint_y=0.76)
        col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12), padding=(0, dp(4)))
        col.bind(minimum_height=col.setter("height"))

        for kind, text in GUIDE_ROWS:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(84), spacing=dp(14))
            row.add_widget(self._make_icon(kind))
            lbl = Label(text=text, font_size=sp(18), color=[1, 1, 1, 1],
                        halign="left", valign="middle")
            lbl.bind(size=lambda widget, *a: setattr(widget, "text_size", widget.size))
            row.add_widget(lbl)
            col.add_widget(row)

        for tip in GUIDE_TIPS:
            t = Label(text="- " + tip, font_size=sp(18), color=[1, 1, 1, 1],
                      halign="left", valign="top", size_hint_y=None)
            t.bind(width=lambda widget, *a: setattr(widget, "text_size", (widget.width, None)))
            t.bind(texture_size=lambda widget, *a: setattr(widget, "height", widget.texture_size[1] + dp(8)))
            col.add_widget(t)

        scroll.add_widget(col)
        outer.add_widget(scroll)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.12)
        back.bind(on_release=lambda *_: app().go("menu"))
        outer.add_widget(back)
        self.root_layout.add_widget(outer)

    def _make_icon(self, kind):
        if kind == "runner":
            return graphics.RunnerSprite(size_hint=(None, 1), width=dp(60))
        if kind == "gate":
            return graphics.GateSprite(label="x2", size_hint=(None, 1), width=dp(60))
        if kind == "enemy":
            return graphics.EnemySprite(size_hint=(None, 1), width=dp(60))
        if kind == "projectile":
            return graphics.Projectile(size_hint=(None, 1), width=dp(60))
        # coin
        return graphics.Coin(size_hint=(None, 1), width=dp(60))


# --- tutorial: step-through text walkthrough (M14 makes it interactive) ----

TUTORIAL_STEPS = [
    ("Welcome to GateRunner",
     "You auto-run forward. Your only job is to steer left and right and "
     "pick which gate to pass through."),
    ("Gates",
     "Gates appear in pairs ahead. Each one applies an effect to your squad: "
     "x2 doubles the crowd, +5 adds five runners, SHOTGUN swaps every "
     "runner's weapon. Pick the better one."),
    ("Squad and firepower",
     "Your whole squad auto-fires at the nearest enemy. The more runners, "
     "the more shots per second. Lose a runner from the front of the crowd "
     "every time an enemy or hazard hits the squad."),
    ("Enemies and the boss",
     "Waves of enemies run toward you. Heavies take more hits. At the end of "
     "each world a boss with attack patterns waits — arrive with as many "
     "runners as possible."),
    ("You are ready",
     "Tap Play! to start World 1. You can replay this walkthrough any time "
     "from the menu's How to play button."),
]


class TutorialScreen(StyledScreen):
    theme_world = 1

    def build(self):
        self.step = 0
        outer = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(16),
                          size_hint=(0.86, 0.86), pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.title_label = Label(text="", font_size=sp(32), bold=True,
                                 color=[1, 0.88, 0.2, 1], size_hint_y=0.18)
        outer.add_widget(self.title_label)
        self.body = Label(text="", font_size=sp(20), color=[1, 1, 1, 1],
                          halign="center", valign="middle", size_hint_y=0.5)
        self.body.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        outer.add_widget(self.body)

        # Step indicator (dots).
        self.dots = Label(text="", font_size=sp(18), color=[1, 1, 1, 0.7], size_hint_y=0.08)
        outer.add_widget(self.dots)

        row = BoxLayout(orientation="horizontal", spacing=dp(16), size_hint_y=0.18)
        self.skip = StyledButton(text="Skip", bg=[0.45, 0.45, 0.5, 1])
        self.skip.bind(on_release=lambda *_: self._finish())
        self.next_btn = StyledButton(text="Next", bg=[0.2, 0.7, 0.4, 1])
        self.next_btn.bind(on_release=lambda *_: self._advance())
        row.add_widget(self.skip)
        row.add_widget(self.next_btn)
        outer.add_widget(row)

        self.root_layout.add_widget(outer)

    def on_enter(self):
        app().audio.play_menu_music()
        self.step = 0
        self._render()

    def _render(self):
        title, body = TUTORIAL_STEPS[self.step]
        self.title_label.text = title
        self.body.text = body
        self.dots.text = "  ".join(
            "*" if i == self.step else "." for i in range(len(TUTORIAL_STEPS))
        )
        self.next_btn.text = "Play!" if self.step == len(TUTORIAL_STEPS) - 1 else "Next"

    def _advance(self):
        if self.step >= len(TUTORIAL_STEPS) - 1:
            self._finish()
            return
        self.step += 1
        self._render()

    def _finish(self):
        running = app()
        running.state.set_setting("tutorial_seen", True)
        running.go("menu")


# --- autoplay tuning ------------------------------------------------------

class AutoPlayerScreen(StyledScreen):
    """Tunes the genetic-algorithm auto-player (M12)."""
    theme_world = 6

    STYLES = [("cautious", "Cautious"), ("balanced", "Balanced"), ("aggressive", "Aggressive")]
    SPEEDS = [("slow", "Slow"), ("normal", "Normal"), ("fast", "Fast")]

    def build(self):
        box = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12),
                        size_hint=(0.88, 0.92), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="Auto Player", font_size=sp(32), bold=True,
                             size_hint_y=0.12, color=[1, 1, 1, 1]))
        intro = Label(text="Let a genetic algorithm pick gates and steer for you.\n"
                           "Choose how it plays:",
                      font_size=sp(16), size_hint_y=0.14, color=[1, 1, 1, 0.9],
                      halign="center", valign="middle")
        intro.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(intro)

        box.add_widget(Label(text="Play style  (safety vs firepower)", font_size=sp(18),
                             bold=True, size_hint_y=0.08, color=[1, 1, 1, 1]))
        self.style_btns = {}
        style_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=0.14)
        for key, label in self.STYLES:
            b = StyledButton(text=label, font_size=sp(18))
            b.bind(on_release=lambda w, k=key: self._set("ga_style", k))
            self.style_btns[key] = b
            style_row.add_widget(b)
        box.add_widget(style_row)

        box.add_widget(Label(text="Reaction speed  (how often it re-decides)", font_size=sp(18),
                             bold=True, size_hint_y=0.08, color=[1, 1, 1, 1]))
        self.speed_btns = {}
        speed_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=0.14)
        for key, label in self.SPEEDS:
            b = StyledButton(text=label, font_size=sp(18))
            b.bind(on_release=lambda w, k=key: self._set("ga_speed", k))
            self.speed_btns[key] = b
            speed_row.add_widget(b)
        box.add_widget(speed_row)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.12)
        back.bind(on_release=lambda *_: app().go("settings"))
        box.add_widget(back)
        self.root_layout.add_widget(box)

    def on_enter(self):
        app().audio.play_menu_music()
        self._refresh()

    def _set(self, key, value):
        app().state.set_setting(key, value)
        self._refresh()

    def _refresh(self):
        state = app().state
        style = state.get_setting("ga_style")
        speed = state.get_setting("ga_speed")
        for key, btn in self.style_btns.items():
            btn.bg = [0.2, 0.7, 0.4, 1] if key == style else [0.35, 0.4, 0.5, 1]
        for key, btn in self.speed_btns.items():
            btn.bg = [0.2, 0.7, 0.4, 1] if key == speed else [0.35, 0.4, 0.5, 1]


# --- multiplayer (versus only) -------------------------------------------

class MultiplayerMenuScreen(StyledScreen):
    """Pick whether to host a versus game or join one."""
    theme_world = 4

    def build(self):
        box = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(20),
                        size_hint=(0.7, 0.84), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="Multiplayer Versus", font_size=sp(40), bold=True,
                             color=[1, 0.85, 0.2, 1], size_hint_y=0.28))
        info = Label(text="Race a friend over the network for the higher score.\n"
                          "Both runners appear on each device's screen in the same world.\n"
                          "One device hosts and the other joins with the host's address.",
                     font_size=sp(16), color=[1, 1, 1, 0.9], halign="center",
                     valign="middle", size_hint_y=0.28)
        info.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(info)
        host = StyledButton(text="Host Game", bg=[0.2, 0.7, 0.4, 1])
        join = StyledButton(text="Join Game", bg=[0.25, 0.5, 0.9, 1])
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1])
        host.bind(on_release=lambda *_: app().go("mphost"))
        join.bind(on_release=lambda *_: app().go("mpjoin"))
        back.bind(on_release=lambda *_: app().go("menu"))
        for b in (host, join, back):
            box.add_widget(b)
        self.root_layout.add_widget(box)

    def on_enter(self):
        app().audio.play_menu_music()


class HostScreen(StyledScreen):
    """Hosts a 2-player versus match.

    Listens on the standard port, shows the local and (best-effort) public
    address, waits for one joiner, then hands off to the gameplay screen.
    Versus is the only mode in GateRunner, so the game type picker CoinTex
    used is omitted — see net.send_start where mode is hard-coded to
    'versus'.
    """
    theme_world = 4

    def build(self):
        self.net = None
        self._poll = None
        self._ready = False
        self._handed_off = False
        self._ip_token = 0
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(10),
                        size_hint=(0.86, 0.94), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="Host a Versus Game", font_size=sp(30), bold=True,
                             color=[1, 1, 1, 1], size_hint_y=0.12))
        self.addr_label = Label(text="", font_size=sp(20), bold=True, color=[0.6, 0.95, 1, 1],
                                halign="center", valign="middle", size_hint_y=0.15)
        self.addr_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(self.addr_label)
        self.inet_label = Label(text="", font_size=sp(14), color=[1, 1, 1, 0.85],
                                halign="center", valign="middle", size_hint_y=0.18)
        self.inet_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(self.inet_label)
        self.status = Label(text="", font_size=sp(17), color=[1, 1, 1, 0.9], size_hint_y=0.16)
        box.add_widget(self.status)
        self.start_btn = StyledButton(text="Start", bg=[0.3, 0.3, 0.35, 1], size_hint_y=0.16)
        self.start_btn.bind(on_release=lambda *_: self._start())
        self.start_btn.disabled = True
        box.add_widget(self.start_btn)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.12)
        back.bind(on_release=lambda *_: self._leave())
        box.add_widget(back)
        self.root_layout.add_widget(box)

    def on_enter(self):
        app().audio.play_menu_music()
        self._handed_off = False
        self._begin_listening()
        self.inet_label.text = "Checking your internet address..."
        self._ip_token += 1
        token = self._ip_token
        threading.Thread(target=self._fetch_public_ip, args=(token, net.DEFAULT_PORT),
                         daemon=True).start()
        self._poll = Clock.schedule_interval(self._check, 0.2)

    def _begin_listening(self):
        if self.net is not None:
            self.net.stop()
        self._ready = False
        self.start_btn.disabled = True
        self.start_btn.bg = [0.3, 0.3, 0.35, 1]
        self.status.text = ("Waiting for a player to join.\n"
                            "If your firewall asks to allow GateRunner, click Allow.")
        self.net = net.NetHost()
        try:
            self.net.start_listening()
            self.addr_label.text = "Same Wi-Fi address\n{}   port {}".format(
                net.get_local_ip(), self.net.port)
        except Exception as error:
            self.addr_label.text = "Could not start hosting."
            self.status.text = str(error)

    def _fetch_public_ip(self, token, port):
        ip = net.get_public_ip()
        Clock.schedule_once(lambda dt: self._show_public_ip(token, port, ip), 0)

    def _show_public_ip(self, token, port, ip):
        if token != self._ip_token:
            return
        if ip:
            self.inet_label.text = (
                "Internet play: forward TCP port {} on your router,\n"
                "then give the other player this address:\n"
                "{}   port {}".format(port, ip, port))
        else:
            self.inet_label.text = (
                "Internet play: forward TCP port {} on your router\n"
                "and share your public IP address.".format(port))

    def on_leave(self):
        self._ip_token += 1
        if self._poll is not None:
            self._poll.cancel()
            self._poll = None
        if self.net is not None and not self._handed_off:
            self.net.stop()
        if not self._handed_off:
            self.net = None

    def _check(self, dt):
        if self.net is None:
            return
        while True:
            try:
                msg = self.net.inbox.get_nowait()
            except Exception:
                break
            kind = msg.get("t")
            if kind == "_connected":
                self.status.text = "A player is connecting..."
            elif kind == "hello":
                if msg.get("version") != net.PROTOCOL_VERSION:
                    self._begin_listening()
                    self.status.text = "A player with a different game version tried to join."
                    return
                self._ready = True
                self.status.text = "A player joined. Tap Start."
                self.start_btn.disabled = False
                self.start_btn.bg = [0.2, 0.7, 0.4, 1]
            elif kind in ("leave", "_disconnected"):
                self._begin_listening()
                return

    def _start(self):
        if not self._ready or self.net is None:
            return
        seed = random.randint(1, 2000000000)
        self.net.send_start("versus", levels.MP_LEVEL, seed)
        self._handed_off = True
        app().start_mp_host("versus", seed, self.net)

    def _leave(self):
        if self.net is not None and not self._handed_off:
            self.net.stop()
            self.net = None
        app().go("multiplayer")


class JoinScreen(StyledScreen):
    """Joins a hosted versus game by typing the host's address."""
    theme_world = 4

    def build(self):
        self.net = None
        self._poll = None
        self._handed_off = False
        box = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14),
                        size_hint=(0.82, 0.82), pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(Label(text="Join a Versus Game", font_size=sp(34), bold=True,
                             color=[1, 1, 1, 1], size_hint_y=0.16))
        prompt = Label(text="Type the host's address (shown on the host's screen).\n"
                            "It can be a same-Wi-Fi address or a public internet one.",
                       font_size=sp(16), color=[1, 1, 1, 0.9], halign="center",
                       valign="middle", size_hint_y=0.16)
        prompt.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(prompt)
        self.ip_input = TextInput(text="", multiline=False, font_size=sp(22),
                                  size_hint_y=0.16, write_tab=False)
        box.add_widget(self.ip_input)
        self.status = Label(text="", font_size=sp(17), color=[1, 1, 1, 0.9], size_hint_y=0.12)
        box.add_widget(self.status)
        self.connect_btn = StyledButton(text="Connect", bg=[0.2, 0.7, 0.4, 1], size_hint_y=0.16)
        self.connect_btn.bind(on_release=lambda *_: self._connect())
        box.add_widget(self.connect_btn)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1], size_hint_y=0.14)
        back.bind(on_release=lambda *_: self._leave())
        box.add_widget(back)
        self.root_layout.add_widget(box)

    def on_enter(self):
        app().audio.play_menu_music()
        self._handed_off = False
        self.status.text = ""
        self.connect_btn.disabled = False
        last = app().state.get_setting("mp_last_ip")
        self.ip_input.text = last if last else net.local_subnet_prefix()
        self.ip_input.cursor = (len(self.ip_input.text), 0)

    def on_leave(self):
        if self._poll is not None:
            self._poll.cancel()
            self._poll = None
        if self.net is not None and not self._handed_off:
            self.net.stop()
        if not self._handed_off:
            self.net = None

    def _connect(self):
        ip = self.ip_input.text.strip()
        if not ip:
            self.status.text = "Please type the host's address."
            return
        self.status.text = "Connecting..."
        self.connect_btn.disabled = True
        self.net = net.NetClient()
        self.net.connect(ip, net.DEFAULT_PORT)
        if self._poll is None:
            self._poll = Clock.schedule_interval(self._check, 0.1)

    def _check(self, dt):
        if self.net is None:
            return
        while True:
            try:
                msg = self.net.inbox.get_nowait()
            except Exception:
                break
            kind = msg.get("t")
            if kind == "_connect_failed":
                self.status.text = "Could not connect. Check the address and Wi-Fi."
                self.connect_btn.disabled = False
                self.net.stop()
                self.net = None
                return
            elif kind == "_connected":
                self.status.text = "Connected. Waiting for the host to start..."
            elif kind == "start":
                if msg.get("version") != net.PROTOCOL_VERSION:
                    self.status.text = "The host has a different game version."
                    self.connect_btn.disabled = False
                    self.net.stop()
                    self.net = None
                    return
                app().state.set_setting("mp_last_ip", self.ip_input.text.strip())
                self._handed_off = True
                app().start_mp_client(msg.get("mode", "versus"), msg.get("seed", 0), self.net)
                return
            elif kind in ("leave", "_disconnected"):
                self.status.text = "The host closed the game."
                self.connect_btn.disabled = False
                self.net.stop()
                self.net = None
                return

    def _leave(self):
        if self.net is not None and not self._handed_off:
            self.net.stop()
            self.net = None
        app().go("multiplayer")
