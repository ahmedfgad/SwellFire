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
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import sp, dp
from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty

import graphics
import levels
import net
import shop


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


# --- shared layout dims --------------------------------------------------
#
# Fixed dp() sizes — proportional size_hint_y on every child of a vertical
# layout means the children squeeze below readable height on short screens
# (Android landscape, iOS, a resized Linux window). Use these constants for
# anything in a stack so the layout stays usable.

BTN_HEIGHT = dp(52)
TITLE_HEIGHT = dp(84)
SUBTITLE_HEIGHT = dp(48)
INFO_HEIGHT = dp(72)
INPUT_HEIGHT = dp(52)
ROW_SPACING = dp(12)


class ShopIcon(Widget):
    """Per-item shop icon. M14 — switched from canvas-drawn primitives
    to real PNG sprites so the shop UI matches the in-level art.

    Each ``kind`` maps to a PNG under ``assets/sprites/`` (see
    ``_PNG_FOR_KIND``); the widget renders the texture full-bleed in
    the centre of its bounds.
    """

    _PNG_FOR_KIND = {
        "grenade":       "assets/sprites/icon_grenade.png",
        "shield":        "assets/sprites/icon_shield.png",
        "squad":         "assets/sprites/hero_blue.png",
        "weapon_pistol": "assets/sprites/icon_weapon_pistol.png",
        "weapon_rifle":  "assets/sprites/icon_weapon_rifle.png",
        "weapon_shotgun":"assets/sprites/icon_weapon_shotgun.png",
        "weapon_sniper": "assets/sprites/icon_weapon_sniper.png",
    }

    def __init__(self, kind: str, count: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.kind = kind
        # M14 — for squad upgrades, ``count`` is the number of soldier
        # silhouettes drawn side by side so "+2" reads as two figures,
        # "+3" as three, etc.
        self.count = max(1, int(count))
        with self.canvas:
            Color(1, 1, 1, 1)
            self._rects: list[Rectangle] = [Rectangle()
                                            for _ in range(self.count)]
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        path = self._PNG_FOR_KIND.get(self.kind)
        if path is None:
            for r in self._rects:
                r.texture = None
            return
        tex = graphics.load_texture(path)
        x, y = self.pos
        w, h = self.size
        n = len(self._rects)
        # All silhouettes share one square footprint inside the icon;
        # for n>1 they tile horizontally with a small overlap so 3
        # soldiers still fit cleanly inside a dp(80) icon.
        side = min(w, h) * 0.95
        if n == 1:
            ix = x + (w - side) * 0.5
            iy = y + (h - side) * 0.5
            self._rects[0].texture = tex
            self._rects[0].pos = (ix, iy)
            self._rects[0].size = (side, side)
            return
        # Multi-soldier layout: each figure is scaled down and tiled with
        # a slight overlap so they read as a group, not a row of icons.
        scale = 0.78 if n == 2 else 0.62
        fig_side = side * scale
        overlap = fig_side * 0.42
        row_w = fig_side + (n - 1) * (fig_side - overlap)
        start_x = x + (w - row_w) * 0.5
        iy = y + (h - fig_side) * 0.5
        for k, r in enumerate(self._rects):
            r.texture = tex
            r.pos = (start_x + k * (fig_side - overlap), iy)
            r.size = (fig_side, fig_side)

    # M14 — old canvas-drawn icons removed; ShopIcon now uses PNG
    # textures from assets/sprites/ via the _PNG_FOR_KIND map above.


def _scroll_panel(*, size_hint=(0.72, 0.94),
                  pos_hint=None, padding=dp(22), spacing=ROW_SPACING):
    """Return (ScrollView, inner BoxLayout) so callers can populate the box.

    Wrapping every vertical menu in a ScrollView makes the screens robust
    to any window height: when content fits, the box stays centered; when
    the window is shorter than the content, the user can scroll.
    """
    if pos_hint is None:
        pos_hint = {"center_x": 0.5, "center_y": 0.5}
    scroll = ScrollView(
        size_hint=size_hint, pos_hint=pos_hint,
        do_scroll_x=False, do_scroll_y=True, bar_width=dp(4),
        scroll_type=["bars", "content"],
    )
    box = BoxLayout(
        orientation="vertical", padding=padding, spacing=spacing,
        size_hint_y=None,
    )
    box.bind(minimum_height=box.setter("height"))
    scroll.add_widget(box)
    return scroll, box


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
    def __init__(self, message, on_yes, yes_text="Yes", no_text="No",
                 on_no=None, *, markup: bool = False, **kwargs):
        super().__init__(size_hint=(0.78, 0.52), auto_dismiss=False, **kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(16))
        with box.canvas.before:
            Color(0.12, 0.14, 0.22, 0.98)
            self._bg = RoundedRectangle(radius=[dp(16)])
        box.bind(pos=lambda *a: setattr(self._bg, "pos", box.pos),
                 size=lambda *a: setattr(self._bg, "size", box.size))
        msg_label = Label(
            text=message, font_size=sp(18), halign="center",
            valign="middle", color=[1, 1, 1, 1], markup=markup,
        )
        msg_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(msg_label)
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


class StarRow(Widget):
    """Three-star row drawn with graphics.draw_star — used by LevelResultDialog."""

    stars = NumericProperty(0)

    def __init__(self, stars: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.stars = stars
        self.bind(pos=self._redraw, size=self._redraw, stars=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 1 or self.height <= 1:
            return
        x, y = self.pos
        w, h = self.size
        slot = w / 3
        outer = min(slot, h) * 0.42
        cy = y + h * 0.5
        with self.canvas:
            for i in range(3):
                cx = x + slot * (i + 0.5)
                color = (1.0, 0.85, 0.20, 1.0) if i < self.stars else (1.0, 1.0, 1.0, 0.22)
                graphics.draw_star(cx, cy, outer, color)


def _format_time(seconds: float) -> str:
    s = int(round(seconds))
    return "{}:{:02d}".format(s // 60, s % 60)


def _add_stat_row(grid, label_text: str, value_text: str, *,
                  value_color=(1, 1, 1, 1)) -> None:
    """Helper to keep the two-column stat layout consistent."""
    grid.add_widget(Label(
        text=label_text, font_size=sp(15), color=(1, 1, 1, 0.78),
        halign="right", valign="middle", size_hint_x=0.45,
        text_size=(None, None),
    ))
    grid.add_widget(Label(
        text=value_text, font_size=sp(15), color=value_color,
        halign="left", valign="middle", size_hint_x=0.55,
        markup=True, text_size=(None, None),
    ))


class LevelResultDialog(ModalView):
    """Modal shown at level end: title, stars (if won), score, action buttons."""

    def __init__(self, won: bool, stars: int, score: int, level_label: str,
                 *, on_next=None, on_retry, on_menu, stats=None,
                 opponent_stats=None, **kwargs):
        # Slightly taller now to fit the stats block.
        super().__init__(size_hint=(0.80, 0.78), auto_dismiss=False, **kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(8))
        with box.canvas.before:
            Color(0.10, 0.12, 0.18, 0.98)
            self._bg = RoundedRectangle(radius=[dp(16)])
        box.bind(pos=lambda *a: setattr(self._bg, "pos", box.pos),
                 size=lambda *a: setattr(self._bg, "size", box.size))

        title = "Level Complete!" if won else "Level Failed"
        title_color = (1.0, 0.85, 0.20, 1.0) if won else (0.95, 0.50, 0.45, 1.0)
        box.add_widget(Label(text=title, font_size=sp(32), bold=True,
                             color=title_color, size_hint_y=0.14))

        box.add_widget(Label(text=level_label, font_size=sp(16), bold=False,
                             color=(1, 1, 1, 0.85), size_hint_y=0.07))

        if won:
            star_holder = BoxLayout(orientation="horizontal", size_hint_y=0.16,
                                    padding=(dp(40), 0, dp(40), 0))
            star_holder.add_widget(StarRow(stars=stars, size_hint=(1, 1)))
            box.add_widget(star_holder)
        else:
            box.add_widget(Label(
                text="Your squad fell to the swarm. Try a steadier path through the gates.",
                font_size=sp(14), color=(1, 1, 1, 0.85),
                halign="center", valign="middle", size_hint_y=0.16,
            ))

        box.add_widget(Label(text="Score   {}".format(score),
                             font_size=sp(20), bold=True, color=(1, 1, 1, 1),
                             size_hint_y=0.09))

        # --- stats block: pairs of [icon-ish label : value] in a grid -----
        # Visible feedback for *what* the player did during the level, not
        # just whether they passed. Children especially want to see numbers
        # tick up — "I killed 47 of them" is a story they can retell.
        if stats:
            if opponent_stats:
                # Versus: 3-column grid with header — Label | YOU | OPP
                grid = GridLayout(cols=3, spacing=(dp(8), dp(4)),
                                  size_hint_y=0.36,
                                  padding=(dp(8), 0, dp(8), 0))
                grid.add_widget(Label(text="", size_hint_x=0.40))
                grid.add_widget(Label(text="YOU", font_size=sp(13), bold=True,
                                      color=(0.40, 0.85, 0.50, 1.0),
                                      halign="center", valign="middle",
                                      size_hint_x=0.30))
                grid.add_widget(Label(text="OPP", font_size=sp(13), bold=True,
                                      color=(0.95, 0.45, 0.45, 1.0),
                                      halign="center", valign="middle",
                                      size_hint_x=0.30))
                rows = [
                    ("Coins",   stats.get("coins_total", 0),
                                opponent_stats.get("coins_total", 0),
                                (1.0, 0.92, 0.40, 1.0)),
                    ("Kills",   stats.get("kills", 0),
                                opponent_stats.get("kills", 0),
                                (0.95, 0.50, 0.45, 1.0)),
                    ("Gates",   "{}/{}".format(stats.get("gates_hit", 0),
                                               stats.get("gates_missed", 0)),
                                "{}/{}".format(opponent_stats.get("gates_hit", 0),
                                               opponent_stats.get("gates_missed", 0)),
                                (1, 1, 1, 1)),
                    ("Squad",   "{}/{}".format(stats.get("squad_end", 0),
                                               stats.get("squad_peak", 0)),
                                "{}/{}".format(opponent_stats.get("squad_end", 0),
                                               opponent_stats.get("squad_peak", 0)),
                                (0.65, 0.85, 1.0, 1.0)),
                    ("Distance","{} m".format(stats.get("distance", 0)),
                                "{} m".format(opponent_stats.get("distance", 0)),
                                (1, 1, 1, 1)),
                    ("Time",    _format_time(stats.get("time", 0.0)),
                                _format_time(opponent_stats.get("time", 0.0)),
                                (1, 1, 1, 1)),
                ]
                for label, you_v, opp_v, accent in rows:
                    grid.add_widget(Label(
                        text=label, font_size=sp(14), color=(1, 1, 1, 0.78),
                        halign="right", valign="middle", size_hint_x=0.40,
                    ))
                    grid.add_widget(Label(
                        text="[b]{}[/b]".format(you_v), font_size=sp(14),
                        bold=True, color=accent, markup=True,
                        halign="center", valign="middle", size_hint_x=0.30,
                    ))
                    grid.add_widget(Label(
                        text="[b]{}[/b]".format(opp_v), font_size=sp(14),
                        bold=True, color=accent, markup=True,
                        halign="center", valign="middle", size_hint_x=0.30,
                    ))
                box.add_widget(grid)
            else:
                grid = GridLayout(cols=2, spacing=(dp(8), dp(4)),
                                  size_hint_y=0.30,
                                  padding=(dp(16), 0, dp(16), 0))
                # First the headline row: total coins broken out as X + Y.
                coin_total = stats.get("coins_total", 0)
                coin_pickup = stats.get("coins_pickup", 0)
                coin_other = coin_total - coin_pickup
                coin_value = "[b]{}[/b]   ({} pickups + {} progress)".format(
                    coin_total, coin_pickup, coin_other,
                )
                _add_stat_row(grid, "Coins earned", coin_value,
                              value_color=(1.0, 0.92, 0.40, 1.0))
                _add_stat_row(grid, "Enemies killed",
                              "[b]{}[/b]".format(stats.get("kills", 0)))
                _add_stat_row(grid, "Gates passed",
                              "[b]{}[/b] hit  /  [b]{}[/b] missed".format(
                                  stats.get("gates_hit", 0),
                                  stats.get("gates_missed", 0),
                              ))
                _add_stat_row(grid, "Squad survived",
                              "[b]{}[/b] of {} runners".format(
                                  stats.get("squad_end", 0),
                                  stats.get("squad_peak", 0),
                              ))
                _add_stat_row(grid, "Distance",
                              "[b]{}[/b] m".format(stats.get("distance", 0)))
                _add_stat_row(grid, "Time",
                              "[b]{}[/b]".format(_format_time(stats.get("time", 0.0))))
                box.add_widget(grid)

        button_row = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=0.18)
        if won and on_next is not None:
            next_btn = StyledButton(text="Next Level", bg=[0.2, 0.7, 0.4, 1])
            next_btn.bind(on_release=lambda *_: self._fire(on_next))
            button_row.add_widget(next_btn)
        retry_btn = StyledButton(text="Retry", bg=[0.25, 0.5, 0.9, 1])
        retry_btn.bind(on_release=lambda *_: self._fire(on_retry))
        button_row.add_widget(retry_btn)
        menu_btn = StyledButton(text="Menu", bg=[0.45, 0.45, 0.5, 1])
        menu_btn.bind(on_release=lambda *_: self._fire(on_menu))
        button_row.add_widget(menu_btn)
        box.add_widget(button_row)
        self.add_widget(box)

    def _fire(self, callback) -> None:
        self.dismiss()
        if callback is not None:
            callback()


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
        scroll, box = _scroll_panel(size_hint=(0.7, 0.94))
        box.add_widget(Label(text="GateRunner", font_size=sp(48), bold=True,
                             color=[1, 0.85, 0.2, 1],
                             size_hint_y=None, height=TITLE_HEIGHT))

        play = StyledButton(text="Play", bg=[0.2, 0.7, 0.4, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        shop_btn = StyledButton(text="Shop", bg=[1.0, 0.65, 0.20, 1],
                                size_hint_y=None, height=BTN_HEIGHT)
        multiplayer = StyledButton(text="Multiplayer", bg=[0.55, 0.4, 0.8, 1],
                                   size_hint_y=None, height=BTN_HEIGHT)
        how = StyledButton(text="How to play", bg=[0.9, 0.6, 0.2, 1],
                           size_hint_y=None, height=BTN_HEIGHT)
        guide = StyledButton(text="Guide", bg=[0.85, 0.5, 0.25, 1],
                             size_hint_y=None, height=BTN_HEIGHT)
        about = StyledButton(text="About", bg=[0.25, 0.5, 0.9, 1],
                             size_hint_y=None, height=BTN_HEIGHT)
        settings = StyledButton(text="Settings", bg=[0.4, 0.45, 0.55, 1],
                                size_hint_y=None, height=BTN_HEIGHT)

        play.bind(on_release=lambda *_: app().go("worldmap"))
        shop_btn.bind(on_release=lambda *_: app().go("shop"))
        multiplayer.bind(on_release=lambda *_: app().go("multiplayer"))
        how.bind(on_release=lambda *_: app().go("tutorial"))
        guide.bind(on_release=lambda *_: app().go("guide"))
        about.bind(on_release=lambda *_: app().go("about"))
        settings.bind(on_release=lambda *_: app().go("settings"))

        for btn in (play, shop_btn, multiplayer, how, guide, about, settings):
            box.add_widget(btn)

        self.stars = Label(text="", font_size=sp(16), color=[1, 1, 1, 0.85],
                           size_hint_y=None, height=SUBTITLE_HEIGHT)
        box.add_widget(self.stars)
        self.root_layout.add_widget(scroll)

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        self.stars.text = "Stars collected: {}    Coins: {}".format(
            running.state.total_stars(), running.state.coins_balance)
        if hasattr(self, "_refresh_play_label"):
            self._refresh_play_label()
        # First-launch auto-tutorial — same one-shot flag CoinTex uses.
        if not running.state.get_setting("tutorial_seen"):
            Clock.schedule_once(lambda dt: running.go("tutorial"), 0)


class ShopScreen(StyledScreen):
    """Coins-for-upgrades shop. Read-only catalog from `shop.CATALOG`;
    purchase actions live on `state.GameState`. Re-rendered on every
    enter so prices reflect the current coins balance."""

    theme_world = 6

    def build(self):
        scroll, self._box = _scroll_panel(size_hint=(0.92, 0.94),
                                          padding=dp(18), spacing=dp(10))
        # Header
        header = BoxLayout(orientation="vertical",
                          size_hint_y=None, height=dp(78))
        header.add_widget(Label(
            text="Shop", font_size=sp(28), bold=True, color=(1, 0.85, 0.2, 1),
            size_hint_y=None, height=dp(40),
        ))
        self.balance_label = Label(
            text="Coins: 0", font_size=sp(18), bold=True,
            color=(1.0, 0.92, 0.40, 1.0),
            size_hint_y=None, height=dp(34),
        )
        header.add_widget(self.balance_label)
        self._box.add_widget(header)
        # Sections — populated on enter so price-affordability is fresh.
        self._section_holders = {}
        for cat in shop.CATEGORY_ORDER:
            section = BoxLayout(orientation="vertical", spacing=dp(6),
                                size_hint_y=None)
            section.bind(minimum_height=section.setter("height"))
            section_label = Label(
                text=shop.CATEGORY_LABELS.get(cat, cat),
                font_size=sp(20), bold=True, color=(1, 1, 1, 0.92),
                halign="left", valign="middle",
                size_hint_y=None, height=dp(40),
            )
            section_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
            section.add_widget(section_label)
            self._box.add_widget(section)
            self._section_holders[cat] = section
        # Back button at the bottom.
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: app().go("menu"))
        self._box.add_widget(back)
        self.root_layout.add_widget(scroll)

    def on_enter(self):
        app().audio.play_menu_music()
        self._render()

    def _render(self):
        running = app()
        state = running.state
        self.balance_label.text = "Coins: {}".format(state.coins_balance)
        # Clear previous items in each section, leaving the section label.
        for cat in shop.CATEGORY_ORDER:
            section = self._section_holders[cat]
            # Keep only the section header (index 0).
            while len(section.children) > 1:
                section.remove_widget(section.children[0])
            for item in shop.category_items(cat):
                section.add_widget(self._make_item_widget(item, state))

    def _make_item_widget(self, item: shop.ShopItem, state) -> "BoxLayout":
        """Each shop item is a single ButtonBehavior card — clicking
        anywhere on the card triggers either a buy (upgrade/booster/squad)
        or an equip (weapon). Visual states make owned / locked /
        can't-afford / equipped unambiguous.
        """
        # Weapons: ALL owned at tier 1; the "ownable" state is MAX tier.
        # Price is dynamic — depends on the current tier the player has.
        if item.category == "weapon":
            wid = item.weapon_id
            current_tier = state.get_weapon_tier(wid)
            next_price = shop.next_tier_price(wid, current_tier)
            is_max = (next_price is None)
            is_equipped = (state.starting_weapon == wid)
            # The "effective price" used to render the card.
            effective_price = next_price if next_price is not None else 0
            can_afford = (next_price is not None) and state.can_afford(next_price)
            owned = is_max          # for the OWNED border treatment when at MAX
            squad_locked = False
            is_selected = is_equipped
            can_buy = is_max or can_afford  # can interact: equip (always) or upgrade
            card = ShopItemCard(
                item=item, can_buy=can_buy, owned=owned,
                squad_locked=False, is_selected=is_selected,
                on_buy=self._buy,
                weapon_tier=current_tier, weapon_next_price=next_price,
                weapon_is_max=is_max, weapon_is_equipped=is_equipped,
            )
            return card

        owned = shop.is_owned(item, state)
        can_afford = state.can_afford(item.price)
        squad_locked = False
        if item.category == "squad" and not owned:
            if state.squad_bonus < item.squad_target - 1:
                squad_locked = True
        can_buy = (not owned) and can_afford and (not squad_locked)
        card = ShopItemCard(
            item=item, can_buy=can_buy, owned=owned,
            squad_locked=squad_locked, is_selected=False,
            on_buy=self._buy,
        )
        return card

    def _buy(self, item: shop.ShopItem, card=None) -> None:
        """Card-click handler. Shows a confirmation modal first; the actual
        purchase + success animation runs on confirm. Children especially
        need that "are you sure?" step before spending hard-earned coins.
        """
        state = app().state
        if item.category == "weapon":
            wid = item.weapon_id
            current_tier = state.get_weapon_tier(wid)
            next_price = shop.next_tier_price(wid, current_tier)
            is_equipped = (state.starting_weapon == wid)
            if not is_equipped:
                # Equip costs nothing — confirm just to make the choice deliberate.
                msg = (
                    "Equip [b]{}[/b]?\n\n"
                    "This will become your starting weapon for every "
                    "non-boss level."
                ).format(item.label)
                self._confirm(msg, "Equip", lambda: self._do_equip_weapon(wid, item, card))
                return
            if next_price is None:
                # Already MAX — nothing to do.
                app().audio.play_sfx("hit")
                return
            if not state.can_afford(next_price):
                app().audio.play_sfx("hit")
                return
            msg = (
                "Upgrade [b]{}[/b] to [b]Lv {}[/b]?\n\n"
                "Cost: [b]{} coins[/b]\n"
                "You have: {} coins"
            ).format(item.label, current_tier + 1, next_price, state.coins_balance)
            self._confirm(msg, "Upgrade",
                          lambda: self._do_upgrade_weapon(wid, current_tier + 1,
                                                          next_price, item, card))
        elif item.category == "booster":
            already = state.get_booster_balance(item.booster_id)
            msg = (
                "Buy [b]{}[/b]?\n\n"
                "Cost: [b]{} coins[/b]\n"
                "You have: {} coins\n\n"
                "You currently own [b]{}[/b] of these."
            ).format(item.label, item.price, state.coins_balance, already)
            self._confirm(msg, "Buy", lambda: self._do_buy_booster(item, card))
        elif item.category == "squad":
            msg = (
                "Buy [b]{}[/b]?\n\n"
                "Cost: [b]{} coins[/b]\n"
                "You have: {} coins\n\n"
                "Every non-boss level starts with this many extra squad members."
            ).format(item.label, item.price, state.coins_balance)
            self._confirm(msg, "Buy", lambda: self._do_buy_squad(item, card))

    def _confirm(self, message: str, yes_text: str, on_confirm) -> None:
        """Open a ConfirmDialog with markup-enabled bold text.

        Kept as a method so all shop confirmations share the same wording
        pattern and the same Cancel/confirm UX.
        """
        ConfirmDialog(message, on_confirm,
                      yes_text=yes_text, no_text="Cancel",
                      markup=True).open()

    # --- actual purchase actions + animation -----------------------------

    def _do_equip_weapon(self, weapon_id: str, item, card) -> None:
        state = app().state
        state.equip_weapon(weapon_id)
        app().audio.play_sfx("gate_pickup")
        self._render()
        self._float_text_from_card(card, "EQUIPPED!", (1.0, 0.85, 0.20, 1.0))

    def _do_upgrade_weapon(self, weapon_id: str, target_tier: int, price: int,
                           item, card) -> None:
        state = app().state
        if state.upgrade_weapon_tier(weapon_id, target_tier, price):
            app().audio.play_sfx("gate_pickup")
            self._pulse_balance(price)
            self._render()
            self._float_text_from_card(card, "Lv {}!".format(target_tier),
                                       (0.55, 0.95, 0.55, 1.0))
        else:
            app().audio.play_sfx("hit")

    def _do_buy_booster(self, item, card) -> None:
        state = app().state
        if state.purchase_booster(item.booster_id, item.booster_qty, item.price):
            app().audio.play_sfx("gate_pickup")
            self._pulse_balance(item.price)
            self._render()
            label = "+{} {}".format(item.booster_qty,
                                    item.booster_id.upper())
            self._float_text_from_card(card, label, (0.55, 0.95, 0.55, 1.0))
        else:
            app().audio.play_sfx("hit")

    def _do_buy_squad(self, item, card) -> None:
        state = app().state
        if state.purchase_squad_bonus(item.squad_target, item.price):
            app().audio.play_sfx("gate_pickup")
            self._pulse_balance(item.price)
            self._render()
            self._float_text_from_card(card,
                                       "+{} SQUAD".format(item.squad_target),
                                       (0.55, 0.95, 0.55, 1.0))
        else:
            app().audio.play_sfx("hit")

    def _pulse_balance(self, price: int) -> None:
        """Brief red-flash + scale-up on the coins balance label so the
        deduction is visible even to a child not reading the text."""
        from kivy.animation import Animation
        lbl = self.balance_label
        # Show a brief "-N" overlay above the balance.
        flash = Label(
            text="[b]-{}[/b]".format(price), font_size=sp(22),
            color=(1.0, 0.35, 0.30, 1.0), markup=True,
            halign="center", valign="middle",
            size_hint=(None, None), size=(dp(120), dp(36)),
        )
        flash.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        # Position centred over the balance label.
        flash.center = lbl.center
        self.root_layout.add_widget(flash)
        anim = Animation(y=flash.y + dp(40), opacity=0, duration=0.8, t="out_quad")
        anim.bind(on_complete=lambda *_, _w=flash: (
            _w.parent.remove_widget(_w) if _w.parent else None
        ))
        anim.start(flash)

    def _float_text_from_card(self, card, text: str,
                              color: tuple[float, float, float, float]) -> None:
        """Rising + fading text label that gives visual confirmation of
        what was just purchased. Big, bold, color-coded — readable at a
        glance even by a younger player."""
        if card is None:
            return
        from kivy.animation import Animation
        floating = Label(
            text="[b]{}[/b]".format(text), font_size=sp(28),
            color=color, markup=True, bold=True,
            halign="center", valign="middle",
            size_hint=(None, None), size=(dp(280), dp(56)),
        )
        floating.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        floating.center = card.center
        self.root_layout.add_widget(floating)
        # Rise + fade-out over 1.1 s with an ease-out so the start is snappy.
        anim = Animation(
            y=floating.y + dp(120),
            opacity=0,
            duration=1.1,
            t="out_quad",
        )
        anim.bind(on_complete=lambda *_, _w=floating: (
            _w.parent.remove_widget(_w) if _w.parent else None
        ))
        anim.start(floating)
        # Briefly enlarge the card's border to draw the eye.
        try:
            from kivy.animation import Animation as _Anim
            original_rgba = card._border_color.rgba
            card._border_color.rgba = (color[0], color[1], color[2], 1.0)
            _Anim(rgba=original_rgba, duration=0.7, t="out_quad").start(card._border_color)
        except Exception:
            pass


class ShopItemCard(ButtonBehavior, BoxLayout):
    """Full-row clickable shop item card.

    Visual states:
      owned          → green border + check overlay
      is_selected    → gold border (currently-equipped starting weapon)
      can_buy        → bright accent bg, normal text
      squad_locked   → grey lock badge, prereq message
      can't afford   → grey "Need N coins" tag, click does nothing
    """

    def __init__(self, *, item, can_buy: bool, owned: bool,
                 squad_locked: bool, is_selected: bool, on_buy,
                 weapon_tier: int = 1, weapon_next_price=None,
                 weapon_is_max: bool = False,
                 weapon_is_equipped: bool = False,
                 **kwargs):
        super().__init__(orientation="horizontal", spacing=dp(10),
                         size_hint_y=None, height=dp(96),
                         padding=(dp(10), dp(8)),
                         **kwargs)
        self.item = item
        self.can_buy = can_buy
        self.owned = owned
        self.squad_locked = squad_locked
        self.is_selected = is_selected
        self._on_buy = on_buy
        self.weapon_tier = weapon_tier
        self.weapon_next_price = weapon_next_price
        self.weapon_is_max = weapon_is_max
        self.weapon_is_equipped = weapon_is_equipped

        # Background card (color depends on state) + outer border.
        with self.canvas.before:
            if owned:
                bg_color = (0.10, 0.22, 0.16, 0.95)  # green-tinted
            elif squad_locked:
                bg_color = (0.18, 0.18, 0.22, 0.85)
            elif not can_buy:
                bg_color = (0.16, 0.16, 0.20, 0.85)
            else:
                bg_color = (0.12, 0.18, 0.30, 0.95)
            self._bg_color = Color(*bg_color)
            self._bg = RoundedRectangle(radius=[dp(12)])
            # Outer border.
            if is_selected:
                border_rgba = (1.0, 0.85, 0.20, 1.0)
                border_width = 3.0
            elif owned:
                border_rgba = (0.30, 0.85, 0.45, 1.0)
                border_width = 2.0
            else:
                border_rgba = (1.0, 1.0, 1.0, 0.18)
                border_width = 1.5
            self._border_color = Color(*border_rgba)
            self._border = Line(rounded_rectangle=[0, 0, 0, 0, dp(12)],
                                width=border_width)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        # Left: icon (square). Squad upgrades render N soldier figures
        # (one per +N) so "+2" reads as two soldiers and "+3" as three,
        # matching the in-level formation the purchase actually grows.
        icon_kind = self._icon_kind_for(item)
        icon_count = item.squad_target if item.category == "squad" else 1
        icon = ShopIcon(kind=icon_kind, count=icon_count,
                        size_hint_x=None, width=dp(80))
        self.add_widget(icon)

        # Middle: title (top), description (bottom), state badge (bottom)
        mid = BoxLayout(orientation="vertical", spacing=dp(2),
                        size_hint_x=1.0)
        title = Label(
            text=item.label, font_size=sp(18), bold=True,
            color=(1, 1, 1, 1), halign="left", valign="middle",
            size_hint_y=None, height=dp(28),
        )
        title.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        mid.add_widget(title)
        desc = Label(
            text=item.description, font_size=sp(13),
            color=(1, 1, 1, 0.80), halign="left", valign="top",
        )
        desc.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        mid.add_widget(desc)
        self.add_widget(mid)

        # Right: price / state stack
        right = BoxLayout(orientation="vertical",
                          size_hint_x=None, width=dp(124), spacing=dp(4))
        # Weapons render their own special right column (tier indicator +
        # upgrade price + equip badge) and skip the generic rendering.
        if item.category == "weapon":
            self._build_weapon_right_column(right)
            self.add_widget(right)
            self._sync_bg()
            return
        # Booster items get a current-count chip pinned to the top.
        if item.category == "booster":
            state = app().state
            count_now = state.get_booster_balance(item.booster_id)
            owned_chip = Label(
                text="[b]You have: {}[/b]".format(count_now),
                font_size=sp(14), color=(0.55, 0.95, 0.55, 1),
                halign="center", valign="middle", markup=True,
                size_hint_y=0.32,
            )
            owned_chip.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
            right.add_widget(owned_chip)
            price_size_hint = 0.36
            state_size_hint = 0.32
        else:
            price_size_hint = 0.55
            state_size_hint = 0.45

        # Top of right column = price OR owned check
        if owned:
            top_text = "[b]OWNED[/b]"
            top_color = (0.55, 0.95, 0.55, 1)
        elif squad_locked:
            top_text = "[b]LOCKED[/b]"
            top_color = (0.95, 0.55, 0.55, 1)
        elif not can_buy:
            top_text = "[b]{} c[/b]".format(item.price)
            top_color = (0.95, 0.55, 0.55, 1)   # red — not affordable
        else:
            top_text = "[b]{} c[/b]".format(item.price)
            top_color = (1.0, 0.92, 0.40, 1)
        price_lbl = Label(
            text=top_text, font_size=sp(18), color=top_color,
            halign="center", valign="middle", markup=True,
            size_hint_y=price_size_hint,
        )
        price_lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        right.add_widget(price_lbl)

        # Bottom of right column = state line (Tap to buy / Need N coins / etc.)
        if owned:
            if is_selected:
                state_text = "EQUIPPED"
                state_color = (1.0, 0.85, 0.20, 1.0)
            else:
                state_text = "Tap to use" if item.category == "weapon" else ""
                state_color = (1, 1, 1, 0.7)
        elif squad_locked:
            state_text = "Need +{}".format(item.squad_target - 1)
            state_color = (1, 1, 1, 0.7)
        elif not can_buy:
            shortfall = item.price - app().state.coins_balance
            state_text = "Need +{} c".format(shortfall)
            state_color = (0.95, 0.55, 0.55, 1)
        else:
            state_text = "Tap to buy"
            state_color = (0.55, 0.95, 0.55, 1)
        state_lbl = Label(
            text=state_text, font_size=sp(13), bold=True,
            color=state_color, halign="center", valign="middle",
            size_hint_y=state_size_hint,
        )
        state_lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        right.add_widget(state_lbl)
        self.add_widget(right)

        # Initial bg/border sync
        self._sync_bg()

    def _build_weapon_right_column(self, right):
        """Special right-column layout for weapon cards."""
        tier = self.weapon_tier
        # Top: tier indicator "Lv 2 / 4"
        tier_lbl = Label(
            text="[b]Lv {} / 4[/b]".format(tier),
            font_size=sp(18), color=(1, 1, 1, 0.92), markup=True,
            halign="center", valign="middle",
            size_hint_y=0.30,
        )
        tier_lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        right.add_widget(tier_lbl)
        # Middle: EQUIPPED badge or "Tap to equip"
        if self.weapon_is_equipped:
            equip_text = "[b]EQUIPPED[/b]"
            equip_color = (1.0, 0.85, 0.20, 1.0)
        else:
            equip_text = "Tap to equip"
            equip_color = (0.55, 0.95, 0.55, 1.0)
        equip_lbl = Label(
            text=equip_text, font_size=sp(13), color=equip_color, markup=True,
            halign="center", valign="middle",
            size_hint_y=0.30,
        )
        equip_lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        right.add_widget(equip_lbl)
        # Bottom: upgrade chip — "Buy Lv X+1: Yc" / "MAX" / "Need +c"
        if self.weapon_is_max:
            up_text = "[b]MAX[/b]"
            up_color = (0.55, 0.95, 0.55, 1.0)
        else:
            if self.weapon_is_equipped:
                can_pay = app().state.can_afford(self.weapon_next_price)
                if can_pay:
                    up_text = "Tap: Lv {} {}c".format(tier + 1, self.weapon_next_price)
                    up_color = (1.0, 0.92, 0.40, 1.0)
                else:
                    shortfall = self.weapon_next_price - app().state.coins_balance
                    up_text = "Lv {}: need +{}c".format(tier + 1, shortfall)
                    up_color = (0.95, 0.55, 0.55, 1.0)
            else:
                up_text = "Lv {}: {}c".format(tier + 1, self.weapon_next_price)
                up_color = (1, 1, 1, 0.5)
        up_lbl = Label(
            text=up_text, font_size=sp(13), bold=True, color=up_color,
            markup=True, halign="center", valign="middle",
            size_hint_y=0.40,
        )
        up_lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        right.add_widget(up_lbl)

    def _icon_kind_for(self, item):
        if item.category == "weapon":
            wid = item.id.split("_", 1)[1]
            return "weapon_" + wid
        if item.category == "booster":
            return item.booster_id   # "grenade" or "shield"
        if item.category == "squad":
            return "squad"
        return ""

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = [
            self.x, self.y, self.width, self.height, dp(12),
        ]

    def on_release(self):
        # For weapons: tap is always actionable (equip if not equipped, OR
        # upgrade if equipped and affordable). The on_buy handler in
        # ShopScreen disambiguates.
        if self.item.category == "weapon":
            self._on_buy(self.item, self)
            return
        if not self.can_buy:
            running = app()
            if running is not None and getattr(running, "audio", None):
                running.audio.play_sfx("hit")
            from kivy.animation import Animation
            self._border_color.rgba = (1.0, 0.30, 0.30, 1.0)
            Animation(rgba=(1.0, 1.0, 1.0, 0.18),
                      duration=0.5, t="out_quad").start(self._border_color)
            return
        self._on_buy(self.item, self)


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


class LevelNode(ButtonBehavior, Widget):
    """Candy-Crush-style circular level node.

    Visual stack, bottom to top:
    1. Drop shadow (offset, blurred-looking ellipse)
    2. Outer ring (theme accent / green for passed / red for boss / gray for locked)
    3. Inner filled disc
    4. Small specular highlight near the top — gives a "polished button" feel
    5. Center number label (always visible; dimmed on locked nodes)
    6. Star row sitting ABOVE the node when the level has been won

    The "?" text for locked levels was replaced with the actual level
    number rendered at low alpha — the player can see what's coming
    next without losing the locked / disabled visual signal.
    """

    NODE_RADIUS = dp(40)
    BOSS_RADIUS = dp(54)
    STAR_STRIP_HEIGHT = dp(24)
    RING_PAD = dp(5)         # extra radius of the ring beyond the inner disc
    SHADOW_OFFSET = dp(3)

    def __init__(self, *, level_index, in_world, is_boss, unlocked, stars,
                 theme, on_click, is_next: bool = False, **kwargs):
        radius = self.BOSS_RADIUS if is_boss else self.NODE_RADIUS
        # Extra width to accommodate the ring + shadow that sit outside
        # the disc; height adds the star strip on top.
        total_size = radius * 2 + self.RING_PAD * 2 + self.SHADOW_OFFSET
        super().__init__(size_hint=(None, None),
                         size=(total_size, total_size + self.STAR_STRIP_HEIGHT),
                         **kwargs)
        self.level_index = level_index
        self.in_world = in_world
        self.is_boss = is_boss
        self.unlocked = unlocked
        self.stars = stars
        self.is_next = is_next        # next unplayed unlocked level — pulsed
        self._on_click = on_click
        self._theme = theme
        self._radius = radius
        self._build_canvas()
        self._build_children()
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    # --- colour palette ---------------------------------------------------

    def _palette(self) -> dict:
        """Return (ring, inner, label_color, highlight_alpha) for this state."""
        accent = self._theme["accent"]
        if not self.unlocked:
            return {
                "ring":      (0.42, 0.44, 0.50, 0.92),
                "inner":     (0.22, 0.24, 0.30, 0.94),
                "label":     (1.0, 1.0, 1.0, 0.32),
                "highlight": 0.10,
            }
        if self.is_boss:
            return {
                "ring":      (1.00, 0.55, 0.30, 1.00),
                "inner":     (0.62, 0.14, 0.14, 1.00),
                "label":     (1.0, 1.0, 1.0, 1.0),
                "highlight": 0.22,
            }
        if self.stars > 0:
            # Cleared levels lean green so the player can spot what's done.
            return {
                "ring":      (0.40, 0.85, 0.50, 1.00),
                "inner":     (0.18, 0.46, 0.28, 1.00),
                "label":     (1.0, 1.0, 1.0, 1.0),
                "highlight": 0.20,
            }
        # Unlocked, not yet passed.
        return {
            "ring":      (accent[0], accent[1], accent[2], 1.00),
            "inner":     (0.20, 0.55, 0.92, 1.00),
            "label":     (1.0, 1.0, 1.0, 1.0),
            "highlight": 0.20,
        }

    def _build_canvas(self) -> None:
        pal = self._palette()
        with self.canvas:
            # Drop shadow.
            self._shadow_color = Color(0, 0, 0,
                                       0.42 if self.unlocked else 0.22)
            self._shadow = Ellipse()
            # "Next to play" gets a soft outer glow so the player can spot
            # where to go next at a glance.
            self._glow_color = Color(1.0, 0.92, 0.30,
                                     0.55 if self.is_next else 0.0)
            self._glow = Ellipse()
            # Outer ring.
            self._ring_color = Color(*pal["ring"])
            self._ring = Ellipse()
            # Inner filled disc.
            self._inner_color = Color(*pal["inner"])
            self._inner = Ellipse()
            # Specular highlight near the top of the disc.
            self._highlight_color = Color(1.0, 1.0, 1.0, pal["highlight"])
            self._highlight = Ellipse()

    def _build_children(self) -> None:
        pal = self._palette()
        # Always render the actual level number — locked levels get a
        # low-alpha label rather than the old anonymous "?". The player
        # can see "this is level 7" even before unlocking it.
        text = str(self.in_world)
        font_size = sp(30) if self.is_boss else sp(24)
        self._label = Label(text=text, font_size=font_size, bold=True,
                            color=pal["label"],
                            halign="center", valign="middle")
        self.add_widget(self._label)
        self._star_row = None
        if self.unlocked and self.stars > 0:
            self._star_row = StarRow(stars=self.stars)
            self.add_widget(self._star_row)

    def _sync(self, *_):
        x, y = self.pos
        r = self._radius
        ring_pad = self.RING_PAD
        shadow = self.SHADOW_OFFSET
        # Inner disc is centred horizontally inside the widget's width,
        # leaving room for the ring + shadow on all sides.
        disc_x = x + ring_pad
        disc_y = y + ring_pad
        # Shadow: offset down-right of the ring.
        self._shadow.pos = (disc_x - ring_pad + shadow,
                            disc_y - ring_pad - shadow)
        self._shadow.size = (r * 2 + ring_pad * 2, r * 2 + ring_pad * 2)
        # Glow: 1.5× outside the ring.
        glow_pad = ring_pad + dp(6)
        self._glow.pos = (disc_x - glow_pad, disc_y - glow_pad)
        self._glow.size = (r * 2 + glow_pad * 2, r * 2 + glow_pad * 2)
        # Ring: the visible outer disc that frames the inner.
        self._ring.pos = (disc_x - ring_pad, disc_y - ring_pad)
        self._ring.size = (r * 2 + ring_pad * 2, r * 2 + ring_pad * 2)
        # Inner: the coloured disc that holds the number.
        self._inner.pos = (disc_x, disc_y)
        self._inner.size = (r * 2, r * 2)
        # Highlight: a flat elliptical sheen near the top of the disc.
        hi_w = r * 1.4
        hi_h = r * 0.45
        self._highlight.pos = (disc_x + r - hi_w / 2,
                               disc_y + r * 1.05)
        self._highlight.size = (hi_w, hi_h)
        # Number label centred on the disc.
        self._label.pos = (disc_x, disc_y)
        self._label.size = (r * 2, r * 2)
        self._label.text_size = self._label.size
        if self._star_row is not None:
            self._star_row.pos = (disc_x, disc_y + r * 2 + dp(4))
            self._star_row.size = (r * 2, self.STAR_STRIP_HEIGHT - dp(4))

    def on_release(self):
        running = app()
        if not self.unlocked:
            if running and getattr(running, "audio", None):
                running.audio.play_sfx("hit")
            return
        self._on_click(self.level_index)


class LevelSelectScreen(StyledScreen):
    """Candy-Crush-style level map for the current world.

    10 circular `LevelNode`s on a zigzag path, level 1 at the bottom
    (player starts low and climbs up), level 10 (boss) at the top.
    Wrapped in a ScrollView so all nodes fit on any window height.
    Auto-scrolls to the highest-unlocked level on entry.
    """

    theme_world = 1
    NODE_SPACING_Y = dp(82)
    NODE_LEFT_X_FRAC = 0.30
    NODE_RIGHT_X_FRAC = 0.70

    def build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        self.title_label = Label(
            text="", font_size=sp(26), bold=True, color=[1, 1, 1, 1],
            size_hint_y=None, height=dp(50),
        )
        outer.add_widget(self.title_label)

        self.scroll = ScrollView(
            size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True,
            bar_width=dp(4), scroll_type=["bars", "content"],
        )
        self.map_widget = Widget(
            size_hint=(1, None),
            height=self.NODE_SPACING_Y * levels.LEVELS_PER_WORLD + dp(80),
        )
        self.scroll.add_widget(self.map_widget)
        outer.add_widget(self.scroll)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: app().go("worldmap"))
        outer.add_widget(back)

        self.root_layout.add_widget(outer)
        self.map_widget.bind(
            width=lambda *_: self._layout_nodes(),
            height=lambda *_: self._layout_nodes(),
        )

    def on_enter(self):
        running = app()
        running.audio.play_menu_music()
        world = running.current_world
        theme = levels.get_world(world)
        self.title_label.text = "World {}  -  {}".format(world, theme["name"])
        self.bg.set_theme(theme)

        self.map_widget.clear_widgets()
        self.map_widget.canvas.before.clear()

        nodes_data = list(levels.levels_in_world(world))
        # Identify the "next-to-play" node — the lowest unlocked level
        # that hasn't been beaten yet. That's the one we want to glow so
        # the player can spot where to head next at a glance.
        next_index = None
        for lvl in nodes_data:
            idx = lvl["index"]
            if running.state.is_unlocked(idx) and running.state.get_stars(idx) == 0:
                next_index = idx
                break

        for lvl in nodes_data:
            index = lvl["index"]
            unlocked = running.state.is_unlocked(index)
            stars = running.state.get_stars(index)
            in_world = lvl["world_index"]
            is_boss = (in_world == levels.LEVELS_PER_WORLD)
            node = LevelNode(
                level_index=index, in_world=in_world, is_boss=is_boss,
                unlocked=unlocked, stars=stars, theme=theme,
                is_next=(index == next_index),
                on_click=lambda i: running.start_level(i),
            )
            self.map_widget.add_widget(node)

        from kivy.clock import Clock as _Clock
        _Clock.schedule_once(lambda _dt: self._layout_nodes(), 0)
        _Clock.schedule_once(lambda _dt: self._scroll_to_highest(), 0)

    def _layout_nodes(self) -> None:
        nodes = [c for c in self.map_widget.children if isinstance(c, LevelNode)]
        if not nodes:
            return
        nodes.sort(key=lambda nd: nd.in_world)
        n = len(nodes)
        map_w = self.map_widget.width
        map_h = self.map_widget.height
        if map_w <= 1 or map_h <= 1:
            return
        # Place each node by anchoring its disc centre (not its widget
        # origin) onto the zigzag path. The widget origin is the bottom-
        # left of the bounding box, so subtract ring_pad + radius to
        # land the disc centre on (cx, cy).
        centres: list[tuple[float, float]] = []
        for i, node in enumerate(nodes):
            x_frac = (self.NODE_LEFT_X_FRAC
                      if i % 2 == 0
                      else self.NODE_RIGHT_X_FRAC)
            y_frac = (i + 0.5) / n
            cx = map_w * x_frac
            cy = map_h * y_frac
            r = node._radius
            ring_pad = LevelNode.RING_PAD
            node.x = cx - r - ring_pad
            node.y = cy - r - ring_pad
            centres.append((cx, cy))

        # Build a smooth curved path through the node centres using a
        # quadratic Bezier per segment. The control point sits at the
        # segment midpoint, shifted perpendicular by ~18 % of the
        # segment length and alternating in sign — this creates the
        # gentle weaving "candy path" look instead of straight zigzag
        # legs with sharp corners.
        SAMPLES_PER_SEG = 18
        path_points: list[float] = []
        for i in range(len(centres) - 1):
            p0x, p0y = centres[i]
            p1x, p1y = centres[i + 1]
            mx = (p0x + p1x) * 0.5
            my = (p0y + p1y) * 0.5
            dx = p1x - p0x
            dy = p1y - p0y
            seg_len = (dx * dx + dy * dy) ** 0.5 or 1.0
            # Perpendicular unit vector — rotate (dx, dy) by 90°.
            perp_x = -dy / seg_len
            perp_y = dx / seg_len
            offset = seg_len * 0.18 * (1 if i % 2 == 0 else -1)
            cx_ctl = mx + perp_x * offset
            cy_ctl = my + perp_y * offset
            for s in range(SAMPLES_PER_SEG + 1):
                # Skip the duplicate point at segment boundaries so we
                # don't get a kink where two segments meet.
                if i > 0 and s == 0:
                    continue
                t = s / SAMPLES_PER_SEG
                u = 1.0 - t
                x = u * u * p0x + 2 * u * t * cx_ctl + t * t * p1x
                y = u * u * p0y + 2 * u * t * cy_ctl + t * t * p1y
                path_points.extend([x, y])

        self.map_widget.canvas.before.clear()
        with self.map_widget.canvas.before:
            # Drop shadow — wide, soft.
            Color(0, 0, 0, 0.30)
            Line(points=path_points, width=dp(8),
                 joint="round", cap="round")
            # Dirt-path base — tan, the candy-crush "trail" look.
            Color(0.82, 0.70, 0.45, 0.78)
            Line(points=path_points, width=dp(6),
                 joint="round", cap="round")
            # Centerline highlight — light cream to give the path
            # a subtle "embossed" feel.
            Color(1.0, 0.95, 0.78, 0.55)
            Line(points=path_points, width=dp(2),
                 joint="round", cap="round")

    def _scroll_to_highest(self) -> None:
        running = app()
        nodes = [c for c in self.map_widget.children if isinstance(c, LevelNode)]
        if not nodes:
            return
        nodes.sort(key=lambda nd: nd.in_world)
        highest = 1
        for node in nodes:
            if node.unlocked:
                highest = node.in_world
        n = len(nodes)
        scroll_y = (highest - 1) / max(1, n - 1)
        self.scroll.scroll_y = max(0.0, min(1.0, scroll_y))


class SettingsScreen(StyledScreen):
    theme_world = 6

    def build(self):
        scroll, box = _scroll_panel(size_hint=(0.82, 0.94))
        box.add_widget(Label(text="Settings", font_size=sp(30), bold=True,
                             size_hint_y=None, height=TITLE_HEIGHT,
                             color=[1, 1, 1, 1]))

        self.music_btn = StyledButton(size_hint_y=None, height=BTN_HEIGHT)
        self.music_btn.bind(on_release=lambda *_: self._toggle("music_on"))
        box.add_widget(self.music_btn)

        self.sfx_btn = StyledButton(size_hint_y=None, height=BTN_HEIGHT)
        self.sfx_btn.bind(on_release=lambda *_: self._toggle("sfx_on"))
        box.add_widget(self.sfx_btn)

        vol_row = BoxLayout(orientation="horizontal", spacing=dp(10),
                            size_hint_y=None, height=BTN_HEIGHT)
        vol_row.add_widget(Label(text="Volume", font_size=sp(18),
                                 size_hint_x=0.35, color=[1, 1, 1, 1]))
        self.volume = Slider(min=0, max=1, value=1, step=0.05, size_hint_x=0.65)
        self.volume.bind(value=self._on_volume)
        vol_row.add_widget(self.volume)
        box.add_widget(vol_row)

        auto = StyledButton(text="Auto Player", bg=[0.3, 0.6, 0.55, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        auto.bind(on_release=lambda *_: app().go("autoplayer"))
        box.add_widget(auto)

        stress = StyledButton(text="Rendering test (debug)",
                              bg=[0.25, 0.45, 0.65, 1],
                              size_hint_y=None, height=BTN_HEIGHT)
        stress.bind(on_release=lambda *_: app().go("stresstest"))
        box.add_widget(stress)

        reset = StyledButton(text="Reset progress", bg=[0.85, 0.35, 0.3, 1],
                             size_hint_y=None, height=BTN_HEIGHT)
        reset.bind(on_release=lambda *_: self._confirm_reset())
        box.add_widget(reset)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: app().go("menu"))
        box.add_widget(back)
        self.root_layout.add_widget(scroll)

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
        # M14 — guide icons now use the real M14 sprites instead of
        # canvas-drawn placeholders.
        png_for_kind = {
            "runner":     "assets/sprites/hero_blue.png",
            "enemy":      "assets/sprites/enemy_w1_grunt.png",
            "projectile": "assets/sprites/icon_projectile.png",
            "coin":       "assets/sprites/icon_coin.png",
        }
        # Special inline-drawn icon for "gate" (no asset; renders the
        # ×2 label on a green pill).
        if kind == "gate":
            return graphics.GateSprite(label="x2", size_hint=(None, 1), width=dp(60))
        path = png_for_kind.get(kind, "assets/sprites/hero_blue.png")
        return graphics.TextureSprite(path, size_hint=(None, 1), width=dp(60))


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
        scroll, box = _scroll_panel(size_hint=(0.88, 0.94))
        box.add_widget(Label(text="Auto Player", font_size=sp(28), bold=True,
                             size_hint_y=None, height=TITLE_HEIGHT,
                             color=[1, 1, 1, 1]))
        intro = Label(text="Let a genetic algorithm pick gates and steer for you.\n"
                           "Choose how it plays:",
                      font_size=sp(15), size_hint_y=None, height=INFO_HEIGHT,
                      color=[1, 1, 1, 0.9], halign="center", valign="middle")
        intro.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(intro)

        box.add_widget(Label(text="Play style  (safety vs firepower)", font_size=sp(16),
                             bold=True, size_hint_y=None, height=SUBTITLE_HEIGHT,
                             color=[1, 1, 1, 1]))
        self.style_btns = {}
        style_row = BoxLayout(orientation="horizontal", spacing=dp(10),
                              size_hint_y=None, height=BTN_HEIGHT)
        for key, label in self.STYLES:
            b = StyledButton(text=label, font_size=sp(17))
            b.bind(on_release=lambda w, k=key: self._set("ga_style", k))
            self.style_btns[key] = b
            style_row.add_widget(b)
        box.add_widget(style_row)

        box.add_widget(Label(text="Reaction speed  (how often it re-decides)", font_size=sp(16),
                             bold=True, size_hint_y=None, height=SUBTITLE_HEIGHT,
                             color=[1, 1, 1, 1]))
        self.speed_btns = {}
        speed_row = BoxLayout(orientation="horizontal", spacing=dp(10),
                              size_hint_y=None, height=BTN_HEIGHT)
        for key, label in self.SPEEDS:
            b = StyledButton(text=label, font_size=sp(17))
            b.bind(on_release=lambda w, k=key: self._set("ga_speed", k))
            self.speed_btns[key] = b
            speed_row.add_widget(b)
        box.add_widget(speed_row)

        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: app().go("settings"))
        box.add_widget(back)
        self.root_layout.add_widget(scroll)

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
    # World 4 (Snowfield) gave a near-white top gradient that washed
    # out the white labels. Cosmos (world 6) is what every other meta
    # screen uses and gives the contrast needed for the body text.
    theme_world = 6

    def build(self):
        scroll, box = _scroll_panel(size_hint=(0.72, 0.94))
        box.add_widget(Label(text="Multiplayer Versus", font_size=sp(34), bold=True,
                             color=[1, 0.85, 0.2, 1],
                             size_hint_y=None, height=TITLE_HEIGHT))
        info = Label(text="Race a friend over the network for the higher score.\n"
                          "Both runners appear on each device's screen in the same world.\n"
                          "One device hosts and the other joins with the host's address.",
                     font_size=sp(15), color=[1, 1, 1, 0.9], halign="center",
                     valign="middle",
                     size_hint_y=None, height=dp(100))
        info.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(info)
        host = StyledButton(text="Host Game", bg=[0.2, 0.7, 0.4, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        join = StyledButton(text="Join Game", bg=[0.25, 0.5, 0.9, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        host.bind(on_release=lambda *_: app().go("mphost"))
        join.bind(on_release=lambda *_: app().go("mpjoin"))
        back.bind(on_release=lambda *_: app().go("menu"))
        for b in (host, join, back):
            box.add_widget(b)
        self.root_layout.add_widget(scroll)

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
    theme_world = 6

    def build(self):
        self.net = None
        self._poll = None
        self._ready = False
        self._handed_off = False
        self._ip_token = 0
        scroll, box = _scroll_panel(size_hint=(0.88, 0.95))
        box.add_widget(Label(text="Host a Versus Game", font_size=sp(26), bold=True,
                             color=[1, 1, 1, 1],
                             size_hint_y=None, height=TITLE_HEIGHT))
        self.addr_label = Label(text="", font_size=sp(18), bold=True,
                                color=[0.6, 0.95, 1, 1],
                                halign="center", valign="middle",
                                size_hint_y=None, height=dp(70))
        self.addr_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(self.addr_label)
        self.inet_label = Label(text="", font_size=sp(13), color=[1, 1, 1, 0.85],
                                halign="center", valign="middle",
                                size_hint_y=None, height=dp(80))
        self.inet_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(self.inet_label)
        self.status = Label(text="", font_size=sp(15), color=[1, 1, 1, 0.9],
                            size_hint_y=None, height=dp(54))
        box.add_widget(self.status)
        self.start_btn = StyledButton(text="Start", bg=[0.3, 0.3, 0.35, 1],
                                      size_hint_y=None, height=BTN_HEIGHT)
        self.start_btn.bind(on_release=lambda *_: self._start())
        self.start_btn.disabled = True
        box.add_widget(self.start_btn)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: self._leave())
        box.add_widget(back)
        self.root_layout.add_widget(scroll)

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
    theme_world = 6

    def build(self):
        self.net = None
        self._poll = None
        self._handed_off = False
        scroll, box = _scroll_panel(size_hint=(0.84, 0.94))
        box.add_widget(Label(text="Join a Versus Game", font_size=sp(28), bold=True,
                             color=[1, 1, 1, 1],
                             size_hint_y=None, height=TITLE_HEIGHT))
        prompt = Label(text="Type the host's address (shown on the host's screen).\n"
                            "It can be a same-Wi-Fi address or a public internet one.",
                       font_size=sp(15), color=[1, 1, 1, 0.9], halign="center",
                       valign="middle",
                       size_hint_y=None, height=dp(72))
        prompt.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        box.add_widget(prompt)
        self.ip_input = TextInput(text="", multiline=False, font_size=sp(20),
                                  size_hint_y=None, height=INPUT_HEIGHT,
                                  write_tab=False)
        box.add_widget(self.ip_input)
        self.status = Label(text="", font_size=sp(15), color=[1, 1, 1, 0.9],
                            size_hint_y=None, height=dp(48))
        box.add_widget(self.status)
        self.connect_btn = StyledButton(text="Connect", bg=[0.2, 0.7, 0.4, 1],
                                        size_hint_y=None, height=BTN_HEIGHT)
        self.connect_btn.bind(on_release=lambda *_: self._connect())
        box.add_widget(self.connect_btn)
        back = StyledButton(text="Back", bg=[0.45, 0.45, 0.5, 1],
                            size_hint_y=None, height=BTN_HEIGHT)
        back.bind(on_release=lambda *_: self._leave())
        box.add_widget(back)
        self.root_layout.add_widget(scroll)

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
