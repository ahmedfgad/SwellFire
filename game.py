"""GameScreen — M4 auto-scroll world + hero + free-drag-with-lane-gravity input.

What M4 lands:
    * The world scrolls forward automatically at SCROLL_SPEED.
    * The hero is a single atlas-backed widget that bobs while running.
    * Touch / mouse drag steers the hero horizontally within the road.
    * `lane_gravity_target()` is in place so M7's gate spawner can drop
      gate-slot X positions in, and the hero will soft-snap toward the
      nearer slot when free-drag isn't actively in progress.
    * Distance counter + debug FPS overlay.

Not yet here (later milestones, each leaves a runnable build):
    * Enemies / projectiles / squad      [M5-M8]
    * Gates                              [M7]
    * Boss waves + win condition         [M10]
    * Networked / autoplay overlay       [M12-M13]
"""

from __future__ import annotations

import math
import os
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle, Line
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import sp, dp
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import aim
import autoplay
import boss as boss_module
import boosters
import combat_juice
import entities
import gates
import graphics
import net
import levels
import ui
import weapons


# --- gameplay constants ---------------------------------------------------

SCROLL_SPEED_PX_PER_SEC = 360.0     # forward scroll rate (visual + distance)
HERO_W = 64.0
HERO_H = 80.0
HERO_BOTTOM_FRAC = 0.16             # hero stays this fraction up from the road floor
# --- manual aim tuning (world-px; wrapped in graphics.ws() at use) ---------
AIM_LEAD_EASE = 7.0           # per-sec ease of the trailing aim-lead point
AIM_OFFSET_FULL = 220.0       # lead-gap (px) that maps to the max tilt angle
AIM_MAX_DEG = 35.0            # max firing tilt off vertical
AIM_MAX_RAD = math.radians(AIM_MAX_DEG)
RETICLE_LEAD_DIST = 360.0     # px ahead of the muzzle the reticle sits
BOSS_ADD_THREAT_FRONT = 360.0 # px band: shoot an add this close, else the boss
# Lateral speed cap used by the autoplayer (M12). Tuned to roughly the
# top end of a sustained finger drag, so the GA reads like a real player
# steering rather than teleporting between targets every retarget tick.
AUTO_HERO_MAX_SPEED = 1800.0        # px/sec
LANE_GRAVITY_STRENGTH = 6.0         # per-second pull rate toward nearest lane
LANE_GRAVITY_RADIUS_PX = 80.0       # only engages within this distance of a lane center
N_STRIPES = 14                      # dashed centerline stripes
STRIPE_LENGTH = 36.0                # px
ENEMY_POOL_CAPACITY = 200           # M5: 50 typical, stress to 200
PROJECTILE_POOL_CAPACITY = 500      # M8: squad of 100 at high fire rate
PARTICLE_POOL_CAPACITY = 500        # M8: kills + gate pickups + attrition bursts
PICKUP_POOL_CAPACITY = 40           # in-level coin + double-coin spawns
PICKUP_COLLECT_RADIUS = 56.0        # px; hero auto-collects pickups within this
# Sub-linear firepower cap: above this many active shooters in the squad,
# only a rotating subset fires each shot. Keeps a 100-runner squad from
# trivializing late-world levels at 700 bullets/sec while still letting
# big squads absorb attrition. The cap value is tuned against the late-world
# enemy density — 22 keeps roughly 150 bullets/sec which lets W6 levels
# stay challenging at any squad size.
MAX_SHOOTERS_PER_SHOT = 22
# Boss fights are sized by *time*, not a flat HP number: at spawn we set boss
# HP so that a player firing at the squad-cap with the boss's reference weapon
# takes ~this many seconds. That makes the world-end boss the climax — longer
# than any normal level early/mid game — regardless of the player's build,
# while staying a capped "sweet spot" rather than a multi-minute slog.
BOSS_TARGET_SECONDS = 82.0
GRID_CELL_PX = 100.0                # spatial-grid cell size (broad-phase)
MUZZLE_OFFSET_Y = HERO_H * 0.55     # spawn projectiles roughly from the gun
# Top-center HUD default top anchors (fraction of screen height). The safe-area
# inset (top_safe_inset setting) subtracts from these to clear a notch.
DIST_BAR_TOP = 0.985          # always-visible level-progress bar
DC_PANEL_TOP = 0.99           # 2x-coins timer pill
TOP_SAFE_INSET_MAX = 0.12     # clamp ceiling for the inset
HERO_FRAME_NAME = "runner_blue"
HERO_SPRITE_PATH = "assets/sprites/hero_blue.png"
OPPONENT_SPRITE_PATH = "assets/sprites/hero_green.png"
DEFAULT_WEAPON_ID = "pistol"
MAX_SQUAD = 100                     # cap for squad_count; squad pool sized to MAX_SQUAD-1
ATTRITION_ZONE_HALF_W = 170.0       # half-width of the squad-contact zone (px)
ATTRITION_FRONT_OFFSET = HERO_H * 0.35   # how far above hero's center the squad's "front line" sits
MAX_GRENADES = 9                    # in-run cap; HUD shows current count
GRENADE_RADIUS = 520.0              # px; detonation kills every enemy within this
                                    # (sized to cover the full stage in front of the hero)
# --- combat juice (#1/#2/#7) ---------------------------------------------
COMBAT_SFX_INTERVAL = 0.07      # min seconds between combat sfx (~14/sec cap)
SCORE_POPUP_INTERVAL = 0.35     # seconds between aggregated score popups
SCORE_POPUP_OFFSET = 80.0       # world-px above the squad for the score popup
SCORE_COLOR = (0.95, 0.96, 1.0, 1.0)        # white/silver — distinct from coins
GATE_GAIN_COLOR = (0.55, 0.80, 1.0, 1.0)    # squad blue (gate gain)
GATE_LOSS_COLOR = (1.0, 0.42, 0.40, 1.0)    # red (gate loss)
GATE_WEAPON_COLOR = (1.0, 0.80, 0.30, 1.0)  # weapon amber
AUTOPLAYER_COST = 30   # coins charged once per level to enable the autoplayer
# Fractional coin rewards per archetype kill — accumulated via a remainder
# counter so common grunts contribute meaningfully over many kills without
# trivializing the shop. A run of ~70 grunt kills now pays ~21 coins
# (was 70). Tank kills still feel valuable.
COIN_PARTIAL_REWARD = {
    # Cut to ~1/4 of the original rates — at the old values a single
    # 100-runner level was paying out 4000+ coins, which broke the
    # shop economy and made everything trivially affordable.
    entities.TYPE_GRUNT:    0.08,
    entities.TYPE_SWARMER:  0.08,
    entities.TYPE_BOMBER:   0.20,
    entities.TYPE_SPLITTER: 0.15,
    entities.TYPE_TANK:     0.40,
}
# Per-gate reward dropped to 0 — gates are the gameplay mechanic, not
# a coin faucet. Level-end completion bonus + per-star also halved.
COIN_REWARD_GATE = 0
COIN_BONUS_LEVEL_COMPLETE = 10
COIN_BONUS_PER_STAR = 5


def lane_gravity_target(current_x: float, lane_centers: list[float], dt: float,
                        strength: float = LANE_GRAVITY_STRENGTH,
                        radius: float = LANE_GRAVITY_RADIUS_PX) -> float:
    """Soft-snap `current_x` toward the nearest lane center within `radius`.

    Frame-rate independent via `1 - exp(-strength * dt)`. With an empty
    `lane_centers` list (M4: gates land in M7), this is a no-op — that's
    intentional so the GameScreen can call it every frame regardless.
    """
    if not lane_centers:
        return current_x
    nearest = min(lane_centers, key=lambda lc: abs(lc - current_x))
    # `radius` is a world-px distance compared against scaled positions, so
    # scale it with density (no-op at 1.0). Lane centers come in scaled.
    if abs(nearest - current_x) > graphics.ws(radius):
        return current_x
    factor = 1.0 - math.exp(-strength * dt)
    return current_x + (nearest - current_x) * factor


# --- the gameplay screen --------------------------------------------------

class _HeroMarker(Widget):
    """Coloured ground-ring drawn under a hero for identity.

    Versus mode renders two heroes that share the same atlas frame —
    without a marker each player has to guess which figure they're
    steering. This widget draws a small flat ellipse (like a coloured
    shadow) the hero stands on. Local hero gets green, opponent gets
    red; both players see "self = green, other = red" so the cue is
    symmetric across devices.
    """

    def __init__(self, color: tuple[float, float, float, float], **kwargs):
        super().__init__(size_hint=(None, None), **kwargs)
        with self.canvas:
            self._outline_color = Color(0, 0, 0, 0.55)
            self._outline = Ellipse()
            self._color = Color(*color)
            self._ellipse = Ellipse()
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *_):
        self._outline.pos = (self.x - dp(2), self.y - dp(2))
        self._outline.size = (self.width + dp(4), self.height + dp(4))
        self._ellipse.pos = self.pos
        self._ellipse.size = self.size


def _dim_color(rgba, factor: float = 0.30):
    """Darkened, fully-opaque version of an RGBA colour — used as a HUD
    button background so a same-hue icon stays visible against it."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    return [r * factor, g * factor, b * factor, 1.0]


class _IconStyledButton(ui.StyledButton):
    """StyledButton with a vector icon drawn in ``canvas.after``.

    Used by the on-screen grenade + shield touch buttons. The button's
    ``text`` shows only the count (with ``valign="bottom"``), and the
    icon sits in the upper portion — far more readable on small mobile
    screens than the old plain "G" / "S" letters.
    """

    def __init__(self, icon_kind: str, **kwargs):
        # Count + status text lives at the bottom of the button so the
        # icon owns the top half. ``valign`` on a Kivy Label only honors
        # the alignment when ``text_size`` is set, so the on-resize hook
        # also writes text_size = button size.
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "bottom")
        kwargs.setdefault("padding", (dp(2), dp(4)))
        kwargs.setdefault("font_size", sp(15))
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)
        self.icon_kind = icon_kind  # "grenade" | "shield" | …
        # While a timed booster is active the button hides its icon and shows
        # a large remaining-seconds countdown instead (set via
        # ``set_icon_visible``); guarded so we only redraw on a state change.
        self._show_icon = True
        self.bind(pos=lambda *_: self._on_resize(),
                  size=lambda *_: self._on_resize())
        self._on_resize()

    def set_icon_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._show_icon:
            return
        self._show_icon = visible
        self._draw_icon()

    def _on_resize(self) -> None:
        # Constrain text rendering to the button's box; without this the
        # Label uses an unbounded text area and ignores valign, leaving
        # the count number invisible behind the icon.
        if self.width > 0 and self.height > 0:
            self.text_size = (self.width, self.height)
        self._draw_icon()

    # M14 — pre-loaded icon textures (one per icon_kind). Loaded on
    # first use so we don't pay the CoreImage cost during app start.
    _ICON_PATHS = {
        "grenade":   "assets/sprites/icon_grenade.png",
        "shield":    "assets/sprites/icon_shield.png",
        "reinforce": "assets/sprites/icon_reinforce.png",
        "freeze":    "assets/sprites/icon_freeze.png",
        "overdrive": "assets/sprites/icon_overdrive.png",
        "magnet":    "assets/sprites/icon_magnet.png",
    }

    def _draw_icon(self) -> None:
        self.canvas.after.clear()
        if not self._show_icon:
            return
        x, y = self.pos
        w, h = self.size
        if w <= 1 or h <= 1:
            return
        path = self._ICON_PATHS.get(self.icon_kind)
        # Fallback: if the icon file is missing/unloadable, the button still
        # shows its count text — we just skip the glyph rather than crash.
        tex = None
        if path is not None and os.path.exists(path):
            try:
                tex = graphics.load_texture(path)
            except Exception:
                tex = None
        if tex is None:
            return
        # Position the icon in the upper portion of the button —
        # roughly the top 60 %. Square aspect ratio.
        side = min(w * 0.66, h * 0.55)
        ix = x + (w - side) * 0.5
        iy = y + h * 0.36
        with self.canvas.after:
            Color(1, 1, 1, 1)
            Rectangle(
                texture=tex,
                pos=(ix, iy),
                size=(side, side),
            )


class _StatChip(FloatLayout):
    """One stat readout: small uppercase title + big bold value, on a
    translucent dark pill with an accent-coloured side stripe.

    Used in the gameplay HUD chip row so each stat (squad, weapon,
    kills, coins) reads at a glance even on a small screen. The accent
    stripe keeps each chip recognisable without needing icon art.
    """

    def __init__(self, title: str, value: str,
                 accent: tuple[float, float, float, float], **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color = Color(0.06, 0.08, 0.14, 0.85)
            self._bg_rect = RoundedRectangle(radius=[dp(10)])
            self._accent_color = Color(*accent)
            self._accent_rect = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=lambda *_: self._sync(),
                  size=lambda *_: self._sync())
        self._title_label = Label(
            text=title, font_size=sp(10), bold=True,
            color=(1, 1, 1, 0.62),
            halign="center", valign="middle",
            size_hint=(1.0, 0.40), pos_hint={"x": 0, "top": 1.0},
        )
        self._title_label.bind(
            size=lambda l, *_: setattr(l, "text_size", l.size),
        )
        self._value_label = Label(
            text=value, font_size=sp(18), bold=True, color=accent,
            halign="center", valign="middle",
            size_hint=(1.0, 0.60), pos_hint={"x": 0, "y": 0},
        )
        self._value_label.bind(
            size=lambda l, *_: setattr(l, "text_size", l.size),
        )
        self.add_widget(self._title_label)
        self.add_widget(self._value_label)

    def _sync(self):
        # Whole-chip pill.
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        # 3-px accent stripe along the bottom edge — subtle visual cue
        # without competing with the value for attention.
        x, y = self.pos
        w, h = self.size
        stripe_h = max(2.0, h * 0.06)
        self._accent_rect.pos = (x, y)
        self._accent_rect.size = (w, stripe_h)

    def set_value(self, value: str) -> None:
        if self._value_label.text != value:
            self._value_label.text = value


class GameScreen(ui.StyledScreen):
    """Auto-scrolling level screen."""

    theme_world = 1

    def build(self):
        # Runtime state.
        self._update_event = None
        self._atlas = None
        self.hero: graphics.AtlasSprite | None = None
        self.distance = 0.0
        self._stripe_ys: list[float] = []
        # Drag tracking
        self._dragging = False
        self._drag_origin_touch_x = 0.0
        self._drag_origin_hero_x = 0.0
        self._hero_target_x = 0.0
        # Manual-aim runtime state (see aim.py). _aim_mode is cached per
        # level in _reset; the reticle/auto target are recomputed each frame.
        self._aim_mode = "manual"
        self._aim_lead_x = 0.0
        self._aim_angle = 0.0
        self._reticle_x = 0.0
        self._reticle_y = 0.0
        self._auto_target = None       # (x, y) stashed by the fire tick for #9
        self.aim_reticle = None
        self.range_line = None               # weapon kill-zone indicator
        self.formation_spawner = None        # army-formation rank spawner
        self._weapon_range_px = None         # None = unlimited (boss/MP)
        self._rank_interval_start = 200.0
        self._rank_interval_end = 120.0
        # Lane centers (M7 fills these per spawned gate pair).
        self.lane_centers: list[float] = []
        # Enemy systems (M5).
        self.enemy_pool: graphics.EntityPool | None = None
        self.enemy_controller: entities.EnemyController | None = None
        self.enemy_spawner: entities.EnemySpawner | None = None
        self.enemy_renderer: graphics.BatchedRenderer | None = None
        # Projectile / particle / shooting systems (M6).
        self.projectile_pool: graphics.EntityPool | None = None
        self.projectile_controller: entities.ProjectileController | None = None
        self.projectile_renderer: graphics.BatchedRenderer | None = None
        self.particle_pool: graphics.EntityPool | None = None
        self.particle_controller: entities.ParticleController | None = None
        self.particle_renderer: graphics.BatchedRenderer | None = None
        # In-level pickup system (coins + double-coin power-up).
        self.pickup_pool: graphics.EntityPool | None = None
        self.pickup_controller: entities.PickupController | None = None
        self.pickup_spawner: entities.PickupSpawner | None = None
        self.pickup_renderer: graphics.BatchedRenderer | None = None
        self.grid = entities.SpatialGrid(graphics.ws(GRID_CELL_PX))
        self.current_weapon_id = DEFAULT_WEAPON_ID
        self._fire_cooldown = 0.0
        self._fire_rng = random.Random()
        self.kills_total = 0
        # Combat-juice runtime state.
        self.score_total = 0
        self._pending_score = 0
        self._had_kill_this_frame = False
        self._had_hit_this_frame = False
        self._last_combat_sfx = 0.0
        self._last_score_popup = 0.0
        # Gates + squad (M7 + M8).
        self.gate_layer: Widget | None = None
        self.gate_controller: gates.GateController | None = None
        self.gate_spawner: gates.GateSpawner | None = None
        self.squad_count = 1
        self.squad_pool: graphics.EntityPool | None = None
        self.squad_controller: entities.SquadController | None = None
        self.squad_renderer: graphics.BatchedRenderer | None = None
        # Opponent's parallel squad — pool + controller + tinted renderer.
        # Both pools render in the same stage but with different tints
        # (blue default / red opponent) so each player sees their own
        # crowd as blue and the other player's as red.
        self.opponent_squad_pool: graphics.EntityPool | None = None
        self.opponent_squad_controller: entities.SquadController | None = None
        self.opponent_squad_renderer: graphics.BatchedRenderer | None = None
        self.attrition_total = 0
        # Level config + result handling (M9).
        self.level_config: dict | None = None
        self.distance_goal = 0.0
        self._level_ended = False
        # Touch-HUD buttons (M11.5 follow-up). Initialized in build().
        self.grenade_btn = None
        self.shield_btn = None
        self.reinforce_btn = None
        self.freeze_btn = None
        self.overdrive_btn = None
        self.magnet_btn = None
        self.pause_btn = None
        self.coins_label = None
        # HUD chip-row widgets. Built in build(); None-initialised so the
        # per-frame updater can skip cleanly before the screen is built.
        self.squad_chip = None
        self.weapon_chip = None
        self.kills_chip = None
        self.coins_chip = None
        self.top_bar = None
        self.chip_row = None
        self.dist_bar_holder = None
        self._top_bar_rect = None
        self._dist_bg_rect = None
        self._dist_fill_rect = None
        self._dist_progress = 0.0
        # Double-coin power-up indicator widgets. Built in build().
        self.dc_panel = None
        self.dc_label = None
        self._dc_bg_color = None
        self._dc_bg_rect = None
        self._dc_fill_color = None
        self._dc_fill_rect = None
        self._dc_flash_color = None
        # Pause / resume — ported from CoinTex's GameScreen pattern. The
        # update loop returns early when self.paused is True; the pause
        # button opens a ConfirmDialog with Quit + Resume choices.
        self.paused = False
        # Auto-play (M12). When ``auto_mode`` is True the AutoPlayer
        # daemon thread drives ``_hero_target_x`` and the touch handlers
        # ignore drag input so the GA can play without interference.
        self.auto_mode = False
        self._auto_paid_for_level = False   # autoplayer charged this level yet?
        self.auto: autoplay.AutoPlayer | None = None
        self.auto_btn = None
        # Multiplayer state (M13). Used only when current_mode != "single".
        #   self.hero is always THIS device's hero (the one local touch
        #   controls). self.opponent_hero is the *other* player's hero,
        #   positioned by client input (on host) or by snapshot (on client).
        # The role helper `_mp_role()` returns "host", "client", or "single".
        self.opponent_hero = None
        self.opponent_target_x = 0.0
        self.opponent_squad = 1
        self.opponent_kills = 0
        self.opponent_coins = 0
        self.opponent_coins_pickups = 0   # p2 ground coins (for client pop)
        self._mp_prev_coin_pickup = 0     # client: last-seen p2 ground total
        self.opponent_alive = True
        # Opponent's auto-fire cooldown + coin remainder. Mirrors the
        # host-side ``_fire_cooldown`` / ``_coin_remainder`` fields but
        # tracks opponent's per-shot rate and fractional kill rewards.
        self._opponent_fire_cooldown = 0.0
        self._opponent_coin_remainder = 0.0
        # Stats for the end-of-match result dialog (versus only).
        self._opponent_squad_peak = 1
        self._opponent_gates_hit = 0
        self._opponent_gates_missed = 0
        # Opponent's equipped weapon + grenade balance. Updated when
        # opponent passes a WEAPON or GRENADE gate. Mirrors the local
        # current_weapon_id / grenade_count so the opponent's auto-fire
        # uses the latest gun and gate effects are symmetric.
        self.opponent_weapon_id = DEFAULT_WEAPON_ID
        self.opponent_grenade_count = 0
        # Opponent's independent 2× COINS power-up timer (mirrors
        # double_coin_until). Lets opponent's coin rewards double for a
        # span after collecting a DOUBLE_COIN pickup, separate from the
        # local player's timer.
        self.opponent_double_coin_until = 0.0
        # Tinted renderer used for the opponent's projectiles.
        self.opponent_projectile_renderer = None
        # Per-hero coloured ground markers — green under the local hero,
        # red under the opponent. Created lazily in on_enter when in
        # versus mode, removed on on_leave or when switching to single.
        self.hero_marker = None
        self.opponent_marker = None
        self.shield_aura = None
        self._mp_tick = 0
        self._last_input_norm_x = None
        # M13 — client sends its equipped weapon to the host once after
        # the game starts so the host can use it for opponent_weapon_id.
        # Flag is set after the first send so we don't spam the channel.
        self._mp_weapon_sent = False
        # 20 Hz snapshot rate (every 3 ticks at 60 fps). Bandwidth-friendly
        # and visually smooth enough — anything faster pushes JSON encoding
        # and TCP send overhead up without obvious win.
        self.SNAPSHOT_INTERVAL_TICKS = 3
        # Boss systems (M10).
        self.boss: boss_module.Boss | None = None
        self.boss_controller: boss_module.BossController | None = None
        self.boss_widget: boss_module.BossWidget | None = None
        # Booster inventory. HUD-visible counters; keyboard shortcuts:
        #   G — grenade (clears nearby enemies, damages boss)
        #   S — shield (brief attrition immunity)
        #   R — reinforcements (instant +squad)
        #   F — freeze (enemies stop for a few seconds)
        #   O — overdrive (fire-rate + damage surge)
        #   M — magnet (pickups home to the hero)
        self.grenade_count = 0
        self.shield_count = 0
        self.reinforce_count = 0
        self.freeze_count = 0
        self.overdrive_count = 0
        self.magnet_count = 0
        # Timed-effect expiries — game-time seconds; <= _run_time = inactive.
        self.shield_active_until = 0.0
        self.freeze_active_until = 0.0
        self.overdrive_active_until = 0.0
        self.magnet_active_until = 0.0
        # Screen shake (M11). The shake offset is applied to root_layout.pos
        # so the whole gameplay frame (stage + HUD) judders together.
        self.shake_intensity = 0.0
        self.shake_x = 0.0
        self.shake_y = 0.0
        # Keyboard binding handle so on_leave can detach cleanly.
        self._key_handler = None

        # The "stage" is the road surface area the hero runs in. Was 66 %
        # wide with green scenery on the sides; that wastes ~1/3 of the
        # screen on phones in portrait, so we now fill the full width.
        # The road's rails + dashed centerline still provide the framing,
        # and HUD widgets float over the stage as semi-transparent chips.
        self.stage = Widget(
            size_hint=(1.0, 1.0),
            pos_hint={"center_x": 0.5, "y": 0},
        )
        self.root_layout.add_widget(self.stage)

        with self.stage.canvas.before:
            # Road surface — a darkened band.
            Color(0.08, 0.10, 0.16, 0.78)
            self._road = Rectangle()

        with self.stage.canvas:
            # Side rails. Line widths scale with density so the road doesn't
            # render hairline-thin on a high-density (Retina) screen.
            Color(1, 1, 1, 0.55)
            self._left_rail = Line(width=graphics.ws(2.0))
            self._right_rail = Line(width=graphics.ws(2.0))
            # Dashed centerline (N stripes that scroll).
            Color(1, 1, 1, 0.30)
            self._stripes = [Line(width=graphics.ws(2.6)) for _ in range(N_STRIPES)]

        self.stage.bind(pos=self._layout_stage, size=self._layout_stage)

        # Top bar — a translucent strip spanning the full width that
        # holds ALL the HUD: title, distance progress, stat chips, and
        # the Auto/Pause corner buttons. Originally 8 % tall with the
        # chip row floating below it; that put the chips at 81-91 % of
        # screen height, which is exactly where the boss and incoming
        # enemies render. The bar is now tall enough (16 %) to contain
        # the chips inside it, so the play area below is fully clear.
        self.top_bar = FloatLayout(
            size_hint=(1.0, 0.16),
            pos_hint={"x": 0.0, "top": 1.0},
        )
        with self.top_bar.canvas.before:
            Color(0.04, 0.05, 0.10, 0.78)
            self._top_bar_rect = Rectangle()
        self.top_bar.bind(
            pos=lambda *_: self._sync_top_bar(),
            size=lambda *_: self._sync_top_bar(),
        )
        self.root_layout.add_widget(self.top_bar)

        # Title — sits in the top portion of the bar. Coordinates are
        # relative to the top_bar's own size (which is now 16 % of
        # screen), so center_y=0.84 keeps the title near the top edge.
        self.title_label = Label(
            text="", font_size=sp(14), bold=True, color=(1, 0.88, 0.2, 1),
            halign="center", valign="middle",
            size_hint=(0.55, 0.30),
            # Sits below the always-on progress bar (which is pinned to the
            # very top of the screen), above the chip row.
            pos_hint={"center_x": 0.5, "center_y": 0.62},
        )
        self.title_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.top_bar.add_widget(self.title_label)

        # Level-progress bar — the single, ALWAYS-visible progress indicator
        # for every level (distance on normal levels, boss-kill progress on
        # boss levels). It lives on the root layout (NOT inside `top_bar`) so
        # the Stats toggle, which dims the band to opacity 0, can never hide
        # it. Styled like the old boss HP bar: a dark rounded track with a
        # rounded fill that grows left→right toward 100 %.
        self.dist_bar_holder = FloatLayout(
            size_hint=(0.6, None), height=dp(20),
            pos_hint={"center_x": 0.5, "top": DIST_BAR_TOP},
        )
        with self.dist_bar_holder.canvas.before:
            Color(0, 0, 0, 0.55)
            self._dist_bg_rect = RoundedRectangle(radius=[dp(4)])
            Color(0.40, 0.85, 0.45, 0.95)
            self._dist_fill_rect = RoundedRectangle(radius=[dp(4)])
        self.dist_bar_holder.bind(
            pos=lambda *_: self._sync_dist_bar(),
            size=lambda *_: self._sync_dist_bar(),
        )
        self._dist_progress = 0.0
        self.root_layout.add_widget(self.dist_bar_holder)

        # Stat chip row — Squad / Weapon / Kills / Coins. Lives at the
        # bottom of the top bar (top=0.91 → covers 0.84-0.91), which is
        # *inside* the bar's vertical range (0.84-1.0). This keeps the
        # gameplay zone below 0.84 fully unobstructed: the boss, gates,
        # and incoming enemies are no longer hidden by stat labels.
        self.chip_row = BoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint=(0.94, 0.07),
            pos_hint={"center_x": 0.5, "top": 0.91},
            padding=(dp(4), 0, dp(4), 0),
        )
        self.squad_chip = _StatChip("SQUAD", "1",
                                    accent=(0.65, 0.85, 1.0, 1.0))
        self.weapon_chip = _StatChip("WEAPON", "Rifle",
                                     accent=(1.0, 0.75, 0.45, 1.0))
        self.kills_chip = _StatChip("KILLS", "0",
                                    accent=(0.95, 0.50, 0.45, 1.0))
        self.coins_chip = _StatChip("COINS", "+0+0",
                                    accent=(1.0, 0.92, 0.40, 1.0))
        for c in (self.squad_chip, self.weapon_chip, self.kills_chip, self.coins_chip):
            self.chip_row.add_widget(c)
        self.root_layout.add_widget(self.chip_row)
        # The old single-line HUD is gone; aliases kept = None so any
        # stray reference (e.g. debug code) fails loud rather than silent.
        self.hud_label = None
        self.coins_label = None

        # Debug overlay (FPS + frame time) — moved down so it sits under
        # the chip row instead of inside it.
        self.debug = graphics.DebugOverlay(
            size_hint=(0.4, 0.05), pos_hint={"x": 0.02, "top": 0.79},
        )
        self.root_layout.add_widget(self.debug)

        # 2× COINS power-up timer. Pill at top-center with a depleting
        # fill bar so the player can see, at a glance, how long the
        # bonus has left. Hidden when the bonus isn't active.
        self.dc_panel = FloatLayout(
            size_hint=(0.34, 0.07),
            pos_hint={"center_x": 0.5, "top": DC_PANEL_TOP},
            opacity=0,
        )
        with self.dc_panel.canvas.before:
            # Outer pill — dim gold so the bright fill stands out.
            self._dc_bg_color = Color(0.40, 0.30, 0.08, 0.92)
            self._dc_bg_rect = RoundedRectangle(radius=[dp(18)])
            # Inner fill — bright gold that shrinks as time runs out.
            self._dc_fill_color = Color(1.0, 0.82, 0.18, 1.0)
            self._dc_fill_rect = RoundedRectangle(radius=[dp(18)])
            # Flash overlay used to pulse the pill in the final seconds.
            self._dc_flash_color = Color(1.0, 1.0, 1.0, 0.0)
            self._dc_flash_rect = RoundedRectangle(radius=[dp(18)])
        self.dc_panel.bind(
            pos=lambda *_: self._redraw_dc_panel(),
            size=lambda *_: self._redraw_dc_panel(),
        )
        self.dc_label = Label(
            text="", font_size=sp(17), bold=True, markup=True,
            color=(0.14, 0.08, 0.0, 1.0),
            halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )
        self.dc_label.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        self.dc_panel.add_widget(self.dc_label)
        self.root_layout.add_widget(self.dc_panel)

        # Pause button — top-right. CoinTex pattern: "II" double-bar glyph.
        self.pause_btn = ui.StyledButton(
            text="II", bg=[0.30, 0.30, 0.40, 0.95], font_size=sp(20), bold=True,
            size_hint=(0.07, 0.08), pos_hint={"right": 0.98, "top": 0.99},
        )
        self.pause_btn.bind(on_release=lambda *_: self._open_pause())
        self.root_layout.add_widget(self.pause_btn)

        # Auto-play toggle (top-left). When green the GA is driving.
        self.auto_btn = ui.StyledButton(
            text="Auto: Off", bg=[0.45, 0.45, 0.5, 1], font_size=sp(14), bold=True,
            size_hint=(0.14, 0.08), pos_hint={"x": 0.02, "top": 0.99},
        )
        self.auto_btn.bind(on_release=lambda *_: self._toggle_auto())
        self.root_layout.add_widget(self.auto_btn)

        # Back button (bottom right)
        self.back_btn = ui.StyledButton(
            text="Back", bg=[0.45, 0.45, 0.5, 1], font_size=sp(16),
            size_hint=(0.14, 0.08), pos_hint={"right": 0.98, "y": 0.03},
        )
        self.back_btn.bind(on_release=lambda *_: self._exit())
        self.root_layout.add_widget(self.back_btn)

        # Bottom-left touch HUD: grenade + shield buttons. Visible during
        # gameplay; tap to fire/activate. Counts update every frame; greyed
        # out when the player has none.
        self.grenade_btn = _IconStyledButton(
            "grenade",
            text="0", bg=[0.20, 0.80, 0.95, 1], font_size=sp(14),
            size_hint=(0.10, 0.10),
            pos_hint={"x": 0.02, "y": 0.03},
        )
        self.grenade_btn.bind(on_release=lambda *_: self._detonate_grenade())
        self.root_layout.add_widget(self.grenade_btn)

        self.shield_btn = _IconStyledButton(
            "shield",
            text="0", bg=[0.50, 0.85, 1.00, 1], font_size=sp(14),
            size_hint=(0.10, 0.10),
            pos_hint={"x": 0.14, "y": 0.03},
        )
        self.shield_btn.bind(on_release=lambda *_: self._activate_shield())
        self.root_layout.add_widget(self.shield_btn)

        # New consumable boosters continue the bottom-left row. Each binds to
        # its activation; counts + active countdowns update in _update_hud.
        for kind, x, activate in (
            ("reinforce", 0.26, self._activate_reinforce),
            ("freeze",    0.38, self._activate_freeze),
            ("overdrive", 0.50, self._activate_overdrive),
            ("magnet",    0.62, self._activate_magnet),
        ):
            # Background is a *darkened* version of the booster's hue so the
            # bright same-hue icon stays clearly visible (a same-color bg made
            # the icon look hidden); the colour identity is preserved.
            btn = _IconStyledButton(
                kind,
                text="0", bg=_dim_color(boosters.BOOSTERS[kind].hud_color),
                font_size=sp(14),
                size_hint=(0.10, 0.10),
                pos_hint={"x": x, "y": 0.03},
            )
            btn.bind(on_release=lambda *_a, _f=activate: _f())
            self.root_layout.add_widget(btn)
            setattr(self, "{}_btn".format(kind), btn)

    # --- layout ----------------------------------------------------------

    def _layout_stage(self, *_):
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        self._road.pos = (sx, sy)
        self._road.size = (sw, sh)
        self._left_rail.points = [sx, sy, sx, sy + sh]
        self._right_rail.points = [sx + sw, sy, sx + sw, sy + sh]
        # Initialize / resize stripe-Y array.
        if len(self._stripe_ys) != N_STRIPES or sh <= 0:
            spacing = sh / N_STRIPES if sh > 0 else 0.0
            self._stripe_ys = [sy + i * spacing for i in range(N_STRIPES)]
        self._paint_stripes()

    def _paint_stripes(self):
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        mid_x = sx + sw * 0.5
        half = graphics.ws(STRIPE_LENGTH) * 0.5
        for i, line in enumerate(self._stripes):
            y = self._stripe_ys[i]
            line.points = [mid_x, y - half, mid_x, y + half]

    # --- lifecycle -------------------------------------------------------

    def _apply_world_tint(self, world: int) -> None:
        """Apply the per-world theme tint to entity renderers (M14).

        Particles pick up the world's accent colour at ~50 % mix with
        white so bursts feel native to each world — green sparks in
        Meadow, orange in Desert, etc. Enemies get a very subtle
        accent tint (~15 % mix) so they still read clearly as enemies
        but blend with the world's palette.
        """
        theme = levels.get_world(world)
        r, g, b = theme["accent"][0], theme["accent"][1], theme["accent"][2]

        def mix(white_share: float):
            return (
                r * (1 - white_share) + 1.0 * white_share,
                g * (1 - white_share) + 1.0 * white_share,
                b * (1 - white_share) + 1.0 * white_share,
                1.0,
            )

        if self.particle_renderer is not None:
            self.particle_renderer.set_tint(mix(0.50))
        # Enemies are now per-world sprites (the atlas swaps in the
        # world's monster art on entry), so no extra accent tint is
        # needed — and the previous 0.85-white mix was washing the
        # real sprites out toward white circles. Reset to identity so
        # the actual art reads cleanly.
        if self.enemy_renderer is not None:
            self.enemy_renderer.set_tint((1.0, 1.0, 1.0, 1.0))

    def on_enter(self):
        running = ui.app()
        # Music + theme per-level for single-player; world 1 for multiplayer.
        if running.current_mode == "single" and running.current_level:
            world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
            theme = levels.get_world(world)
            self.bg.set_theme(theme)
            cfg_preview = levels.get_level(running.current_level)
            if cfg_preview and cfg_preview.get("boss"):
                running.audio.play_boss_music()
            else:
                running.audio.play_level_music(world)
            self.title_label.text = "World {} - {}     Level {}".format(
                world, theme["name"], running.current_level)
        else:
            running.audio.play_level_music(1)
            self.title_label.text = "Multiplayer Versus     ({})".format(running.current_mode)

        # Load the world-specific atlas. M14 ships one atlas per world
        # (world1.png…world6.png), each with a different enemy sprite in
        # the enemy_red slot so each world's pool of enemies looks
        # distinct without changing the rendering code.
        if running.current_mode == "single" and running.current_level:
            atlas_world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
        else:
            atlas_world = 1
        atlas_world = max(1, min(levels.NUM_WORLDS, atlas_world))
        atlas_key = "world{}".format(atlas_world)
        if self._atlas is None:
            png_path, json_path = graphics.find_atlas(atlas_key)
            self._atlas = graphics.SpriteAtlas(png_path, json_path)
            self._atlas_world = atlas_world
        elif getattr(self, "_atlas_world", None) != atlas_world:
            png_path, json_path = graphics.find_atlas(atlas_key)
            self._atlas.reload(png_path, json_path)
            self._atlas_world = atlas_world
            # Bind the swapped texture to every BatchedRenderer mesh
            # that's already alive. Without this, the mesh would keep
            # the previous world's texture object cached at construction.
            for renderer in (self.enemy_renderer, self.projectile_renderer,
                             self.opponent_projectile_renderer,
                             self.particle_renderer, self.squad_renderer,
                             self.opponent_squad_renderer, self.pickup_renderer):
                if renderer is not None and hasattr(renderer, "_mesh"):
                    renderer._mesh.texture = self._atlas.texture

        # Pools + renderers, in draw order: enemy (back) → projectile → particle → hero (front).
        if self.enemy_pool is None:
            self.enemy_pool = graphics.EntityPool(ENEMY_POOL_CAPACITY, self._atlas)
            self.enemy_controller = entities.EnemyController(self.enemy_pool)
            self.enemy_spawner = entities.EnemySpawner(self.enemy_controller, self._atlas)
            self.formation_spawner = entities.FormationSpawner(self.enemy_controller)
            self.enemy_renderer = graphics.BatchedRenderer(
                self.enemy_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.enemy_renderer)

        if self.projectile_pool is None:
            self.projectile_pool = graphics.EntityPool(PROJECTILE_POOL_CAPACITY, self._atlas)
            self.projectile_controller = entities.ProjectileController(self.projectile_pool)
            # M13 — split the rendering by owner so the player can tell
            # which projectiles came from which hero. The local renderer
            # has no tint (texture as-is); a second renderer for
            # opponent shots paints them red. Both read the same pool;
            # owner_array drives the per-slot filter inside rebuild().
            self.projectile_renderer = graphics.BatchedRenderer(
                self.projectile_pool,
                owner_array=self.projectile_controller.owner,
                owner_filter=0,
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.projectile_renderer)
            self.opponent_projectile_renderer = graphics.BatchedRenderer(
                self.projectile_pool,
                tint=(1.0, 0.45, 0.45, 1.0),
                owner_array=self.projectile_controller.owner,
                owner_filter=1,
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.opponent_projectile_renderer)

        if self.particle_pool is None:
            self.particle_pool = graphics.EntityPool(PARTICLE_POOL_CAPACITY, self._atlas)
            self.particle_controller = entities.ParticleController(self.particle_pool)
            self.particle_renderer = graphics.BatchedRenderer(
                self.particle_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.particle_renderer)

        # Pickups (coins + double-coin) — own pool so they draw between
        # projectiles and gates, and so the renderer stays simple.
        if self.pickup_pool is None:
            self.pickup_pool = graphics.EntityPool(PICKUP_POOL_CAPACITY, self._atlas)
            self.pickup_controller = entities.PickupController(self.pickup_pool)
            self.pickup_spawner = entities.PickupSpawner(self.pickup_controller)
            # skip_array hides pickups the local player has already
            # collected — in versus, the slot remains in the pool so the
            # opponent can still grab their own copy.
            self.pickup_renderer = graphics.BatchedRenderer(
                self.pickup_pool,
                skip_array=self.pickup_controller.consumed_by_p1,
                size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.pickup_renderer)

        # Gate layer lives under the hero so the hero appears "passing through".
        if self.gate_layer is None:
            self.gate_layer = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
            self.stage.add_widget(self.gate_layer)
            self.gate_controller = gates.GateController(self.gate_layer)
            self.gate_spawner = gates.GateSpawner(self.gate_controller)

        # Squad follower pool (M8). Capacity = MAX_SQUAD - 1 since the hero is its own widget.
        if self.squad_pool is None:
            self.squad_pool = graphics.EntityPool(MAX_SQUAD - 1, self._atlas)
            self.squad_controller = entities.SquadController(self.squad_pool)
            self.squad_renderer = graphics.BatchedRenderer(
                self.squad_pool, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            )
            self.stage.add_widget(self.squad_renderer)

        # M13 — opponent's squad followers. Same pool size + the same
        # SquadController formation, but the renderer carries a red
        # tint so the player can tell their own squad from the other
        # player's at a glance. Created only in versus mode.
        if running.current_mode != "single":
            if self.opponent_squad_pool is None:
                self.opponent_squad_pool = graphics.EntityPool(
                    MAX_SQUAD - 1, self._atlas,
                )
                self.opponent_squad_controller = entities.SquadController(
                    self.opponent_squad_pool,
                )
                self.opponent_squad_renderer = graphics.BatchedRenderer(
                    self.opponent_squad_pool,
                    tint=(1.0, 0.55, 0.55, 1.0),
                    size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
                )
                self.stage.add_widget(self.opponent_squad_renderer)

        if self.hero is None:
            # M14 — switched from AtlasSprite to per-PNG TextureSprite.
            # The atlas-based Rectangle+tex_coords path went transparent
            # against multi-frame atlases on Kivy 2.3; a one-file
            # texture with default UVs sidesteps the bug AND makes
            # third-party art a drop-in replacement.
            self.hero = graphics.TextureSprite(
                HERO_SPRITE_PATH,
                size_hint=(None, None),
                size=(graphics.ws(HERO_W), graphics.ws(HERO_H)),
            )
            self.stage.add_widget(self.hero)

        if self.aim_reticle is None:
            self.aim_reticle = graphics.AimReticle(
                radius=graphics.ws(graphics.AimReticle.R),
                size_hint=(None, None), size=(1, 1),
            )
            self.stage.add_widget(self.aim_reticle)

        if self.range_line is None:
            self.range_line = graphics.RangeLine(size_hint=(None, None), size=(1, 1))
            self.stage.add_widget(self.range_line)

        # Shield bubble — a glowing aura shown around the hero while a shield
        # is up (replaces the old rectangle tint). Added once, hidden until
        # _activate_shield shows it; repositioned to the hero each frame.
        if self.shield_aura is None:
            self.shield_aura = graphics.ShieldAura(
                size_hint=(None, None),
                size=(graphics.ws(HERO_W * 2.0), graphics.ws(HERO_H * 1.7)),
            )
            self.stage.add_widget(self.shield_aura)

        # M13 — Opponent hero + per-hero ground-ring markers so each
        # player can tell at a glance which figure is theirs. Green
        # under the local hero, red under the opponent. Added BEFORE
        # the sprite so the marker sits behind the runner.
        if running.current_mode != "single":
            if self.hero_marker is None:
                self.hero_marker = _HeroMarker(
                    color=(0.30, 0.85, 0.40, 0.90),
                    size=(graphics.ws(HERO_W * 0.95), graphics.ws(HERO_H * 0.20)),
                )
                # Insert under the hero so the sprite paints over it.
                self.stage.add_widget(self.hero_marker, index=1)
            if self.opponent_hero is None:
                # Different PNG for opponent so the two players read
                # as distinct figures (separate from the green/red
                # marker rings).
                self.opponent_hero = graphics.TextureSprite(
                    OPPONENT_SPRITE_PATH,
                    size_hint=(None, None),
                    size=(graphics.ws(HERO_W), graphics.ws(HERO_H)),
                )
                self.opponent_hero.opacity = 0.70
                self.stage.add_widget(self.opponent_hero)
            if self.opponent_marker is None:
                self.opponent_marker = _HeroMarker(
                    color=(0.95, 0.35, 0.35, 0.90),
                    size=(graphics.ws(HERO_W * 0.95), graphics.ws(HERO_H * 0.20)),
                )
                self.stage.add_widget(self.opponent_marker, index=1)
        elif running.current_mode == "single":
            for widget_attr in ("opponent_hero", "opponent_marker", "hero_marker"):
                w = getattr(self, widget_attr, None)
                if w is not None:
                    if w.parent:
                        w.parent.remove_widget(w)
                    setattr(self, widget_attr, None)

        # Keyboard input for weapon swap (1..4 select; W cycles).
        if self._key_handler is None:
            self._key_handler = self._on_key
            Window.bind(on_key_down=self._key_handler)

        # Reset shooting + squad state.
        self.current_weapon_id = DEFAULT_WEAPON_ID
        self._fire_cooldown = 0.0
        self.kills_total = 0
        self.score_total = 0
        self._pending_score = 0
        self._last_combat_sfx = 0.0
        self._last_score_popup = 0.0
        self._had_kill_this_frame = False
        self._had_hit_this_frame = False
        self.squad_count = 1
        # Highest squad size reached this run — shown in the end-of-level
        # summary so the player sees their crowd peaked at e.g. 47.
        self._squad_peak = 1
        self.attrition_total = 0
        self._level_ended = False
        # Carry over the per-save booster balances into the run; level-end
        # writes back what's left so they persist between runs.
        #
        # The "free starter grenade" used to live here, but it produced a
        # stockpile (5-7 grenades) that made grenades feel like a regular
        # item rather than a rare panic button. The safety it provided is
        # now covered by the pity-gate floor (gates.GateSpawner) so the
        # player can recover from missed pairs without a freebie.
        running_app = ui.app()
        if running_app and running_app.state:
            st = running_app.state
            self.grenade_count = st.get_booster_balance("grenade")
            self.shield_count = st.get_booster_balance("shield")
            self.reinforce_count = st.get_booster_balance("reinforce")
            self.freeze_count = st.get_booster_balance("freeze")
            self.overdrive_count = st.get_booster_balance("overdrive")
            self.magnet_count = st.get_booster_balance("magnet")
        else:
            self.grenade_count = 0
            self.shield_count = 0
            self.reinforce_count = 0
            self.freeze_count = 0
            self.overdrive_count = 0
            self.magnet_count = 0
        self.shield_active_until = 0.0
        self.freeze_active_until = 0.0
        self.overdrive_active_until = 0.0
        self.magnet_active_until = 0.0
        self._run_time = 0.0
        # Coins earned during the run (kill remainder + gate pickup + in-level
        # coin pickups). Persisted to state.coins_balance in _end_level so a
        # partial run still pays the player for whatever they collected.
        self._coins_earned = 0
        # Split tracking: pickups (coins thrown into the level + the coin
        # rain from the double-coin power-up) vs everything else (kill
        # rewards, gate rewards, completion bonus). The in-level HUD shows
        # them as "Coins +X+Y" so the player can see what worked.
        self._coins_pickups = 0
        self._coin_remainder = 0.0      # fractional remainder for kill rewards
        self.double_coin_until = 0.0    # in-run timer; coin rewards 2× while active
        if self.squad_controller is not None:
            self.squad_controller.sync_to_count(0)   # hero alone at level start
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_spawner is not None:
            # Reset the spawner so a fresh level starts past its first interval.
            self.gate_spawner._next_distance = 200.0  # noqa: SLF001 — first-spawn distance
        if self.pickup_spawner is not None:
            self.pickup_spawner.reset_per_level()
        self.lane_centers = []

        # Apply the per-level config now that pools + spawners exist.
        self._apply_level_config()

        # M14 — apply the per-world tint to entity renderers. Done here
        # AFTER pool/renderer creation so the Color instructions exist.
        # Versus uses W1's theme (Meadow) so MP visuals are stable.
        if running.current_mode == "single" and running.current_level:
            tint_world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
        else:
            tint_world = 1
        self._apply_world_tint(tint_world)

        # Stats HUD visibility (Settings toggle; also hides the distance bar
        # on boss levels). Done after the level config is applied so the
        # boss-level check is accurate.
        self._apply_stats_visibility()
        self._apply_debug_visibility()
        self._apply_top_safe_inset()

        # Stage might be size 0 right after on_enter; do the actual reset on
        # the next frame so positions are real.
        Clock.schedule_once(self._reset, 0)

        # One-time hint the first time the player reaches world 2: the shop
        # lets them upgrade weapons. Shown over a paused world with a direct
        # "Go to Shop" button.
        if (running.current_mode == "single"
                and running.current_level == levels.LEVELS_PER_WORLD + 1
                and running_app and running_app.state
                and not running_app.state.world2_hint_shown):
            running_app.state.mark_world2_hint_shown()
            Clock.schedule_once(lambda *_: self._show_world2_hint(), 0.05)

    def _show_world2_hint(self) -> None:
        if self._level_ended:
            return
        self.paused = True
        try:
            ui.app().audio.stop_music()
        except Exception:
            pass
        self._show_pause_dim(True)

        def go_shop():
            self._show_pause_dim(False)
            self.paused = False
            self._level_ended = True
            if self._update_event is not None:
                self._update_event.cancel()
                self._update_event = None
            self._exit_to("shop")

        def later():
            self._show_pause_dim(False)
            self._resume()

        ui.WeaponUpgradeDialog(on_shop=go_shop, on_later=later).open()

    def on_leave(self):
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        if self._key_handler is not None:
            Window.unbind(on_key_down=self._key_handler)
            self._key_handler = None
        for renderer in (self.enemy_renderer, self.projectile_renderer,
                         self.opponent_projectile_renderer,
                         self.particle_renderer, self.squad_renderer,
                         self.opponent_squad_renderer,
                         self.pickup_renderer):
            if renderer is not None and renderer.parent:
                renderer.parent.remove_widget(renderer)
        if self.gate_controller is not None:
            self.gate_controller.clear()
        if self.gate_layer is not None and self.gate_layer.parent:
            self.gate_layer.parent.remove_widget(self.gate_layer)
        self._teardown_boss()
        if self.hero is not None and self.hero.parent:
            self.hero.parent.remove_widget(self.hero)
        # Shield aura follows the hero off the stage (cancel its pulse first).
        if self.shield_aura is not None:
            self.shield_aura.hide()
            if self.shield_aura.parent:
                self.shield_aura.parent.remove_widget(self.shield_aura)
            self.shield_aura = None
        # Cancel the manual-aim reticle's pulse so its Animation doesn't keep
        # ticking on an off-stage widget between levels (the widget itself is
        # reused on re-entry — _reset re-hides and the _update loop re-shows it).
        if self.aim_reticle is not None:
            self.aim_reticle.hide()
        # M13 — also tear the opponent hero off the stage; the on_enter
        # path checks "is None" before creating one, so without this the
        # next versus match would keep the stale ghost AND skip making
        # the new one. Same shape as the hero cleanup just above.
        if self.opponent_hero is not None and self.opponent_hero.parent:
            self.opponent_hero.parent.remove_widget(self.opponent_hero)
        self.opponent_hero = None
        # Markers go with the heroes so they don't dangle on the next entry.
        for marker_attr in ("hero_marker", "opponent_marker"):
            mk = getattr(self, marker_attr, None)
            if mk is not None and mk.parent:
                mk.parent.remove_widget(mk)
            setattr(self, marker_attr, None)
        self.opponent_target_x = 0.0
        self.opponent_squad = 1
        self.opponent_kills = 0
        self.opponent_coins = 0
        self.opponent_coins_pickups = 0   # p2 ground coins (for client pop)
        self._mp_prev_coin_pickup = 0     # client: last-seen p2 ground total
        self.opponent_alive = True
        self.opponent_weapon_id = DEFAULT_WEAPON_ID
        self.opponent_grenade_count = 0
        self.opponent_double_coin_until = 0.0
        self._mp_weapon_sent = False
        self.enemy_pool = None
        self.enemy_controller = None
        self.enemy_spawner = None
        self.enemy_renderer = None
        self.projectile_pool = None
        self.projectile_controller = None
        self.projectile_renderer = None
        self.opponent_projectile_renderer = None
        self.particle_pool = None
        self.particle_controller = None
        self.particle_renderer = None
        self.pickup_pool = None
        self.pickup_controller = None
        self.pickup_spawner = None
        self.pickup_renderer = None
        self.squad_pool = None
        self.squad_controller = None
        self.squad_renderer = None
        self.opponent_squad_pool = None
        self.opponent_squad_controller = None
        self.opponent_squad_renderer = None
        self.gate_layer = None
        self.gate_controller = None
        self.gate_spawner = None
        self.lane_centers = []
        self.hero = None
        self._dragging = False

    def _reset(self, _dt):
        self.distance = 0.0
        if self.formation_spawner is not None:
            self.formation_spawner.reset_per_level(0.0)
        # Reset shake so a fresh level doesn't inherit the previous one's kick.
        self.shake_intensity = 0.0
        self.shake_x = 0.0
        self.shake_y = 0.0
        self.root_layout.pos = (0, 0)
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        if self.hero is not None:
            hero_cx = sx + sw * 0.5
            self.hero.center_x = hero_cx
            self.hero.y = sy + sh * HERO_BOTTOM_FRAC
            self._hero_target_x = hero_cx
            self._aim_lead_x = hero_cx
            self._aim_angle = 0.0
            self._reticle_x = hero_cx
            self._reticle_y = 0.0
        self._aim_mode = "manual"   # manual aim is the only control scheme
        self._auto_target = None
        if self.aim_reticle is not None:
            self.aim_reticle.hide()
        self._update_weapon_range()
        # Boss position was computed in `_apply_level_config` (via `_spawn_boss`)
        # off the *pre-layout* stage size, which is 0/100 right after on_enter —
        # leaving the boss pinned to the bottom-left corner. Now that the stage
        # has its real dimensions, recompute its center (mirrors _spawn_boss).
        if self.boss is not None:
            self.boss.cx = sx + sw * 0.5
            self.boss.cy = sy + sh * 0.82
            if self.boss_widget is not None:
                self.boss_widget.update_from_boss()
        if self._update_event is None:
            self._update_event = Clock.schedule_interval(self._update, 1 / 60.0)
        # Autoplay never carries across levels — each level starts OFF so the
        # player is never charged the per-level cost by surprise. They must
        # re-enable (and re-pay) it explicitly via the Auto button.
        self.auto_mode = False
        self._auto_paid_for_level = False
        if self.auto is not None:
            self.auto.stop()
        self._refresh_auto_button()

    def _apply_level_config(self) -> None:
        """Look up the per-level config and push it to the spawners.

        Boss levels (M10) disable the regular enemy + gate spawners — the
        boss controller handles all enemy spawning, and the player gets a
        head-start squad/weapon so the fight isn't pistol+1.
        """
        running = ui.app()
        # Multiplayer (versus) gets its own dedicated config — fixed
        # 60-second duration regardless of which single-player level was
        # last played. Without this override the MP screen would inherit
        # the last single-player level's distance_goal (20 s on L1,
        # 138 s on L60) which is unpredictable for matchmaking.
        if running.current_mode != "single":
            cfg = levels.build_mp_level()
        else:
            cfg = levels.get_level(running.current_level) if running.current_level else None
            if cfg is None:
                cfg = levels.get_level(1)
        self.level_config = cfg
        # distance_goal / gate_interval_px live in the scroll distance domain,
        # which scales with density (self.distance accumulates scaled scroll).
        # Scaling them keeps level *duration* and gate cadence identical to the
        # density-1.0 build. enemy_speed/chase are left logical here — they are
        # scaled at use in entities (EnemySpawner._spawn_one). No-op at 1.0.
        self.distance_goal = graphics.ws(float(cfg["distance_goal"]))
        is_boss = bool(cfg.get("boss"))

        if self.enemy_spawner is not None:
            # LEGACY: enemy_spawner is no longer ticked — FormationSpawner is the
            # spawn source now. Only `hp_scale` (set in the block below) is still
            # read (copied into formation_spawner). These assignments are inert;
            # kept to avoid churn. Edit FormationSpawner config (below) instead.
            if is_boss:
                # Boss controls all spawning during the fight.
                self.enemy_spawner.interval = 0.0
            else:
                self.enemy_spawner.interval = cfg["enemy_spawn_interval"]
            self.enemy_spawner.enemy_speed = cfg["enemy_speed"]
            self.enemy_spawner.enemy_hp = cfg["enemy_hp"]
            self.enemy_spawner.chase_strength_min = cfg["enemy_chase_min"]
            self.enemy_spawner.chase_strength_max = cfg["enemy_chase_max"]
            # Per-world enemy archetype mix. Boss levels keep the default
            # grunt-only table since the boss controller hard-codes its
            # minions.
            if is_boss:
                self.enemy_spawner.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
                # Boss controls all spawning — no intro delay needed; the
                # opening volley is the threat the player sees immediately.
                self.enemy_spawner.intro_delay = 0.0
            else:
                self.enemy_spawner.spawn_table = [
                    (entities.TYPE_NAMES[name], weight)
                    for name, weight in cfg["allowed_enemy_types"]
                ]
                # World-scaling intro delay: higher worlds get more breathing
                # room because their base spawn rate and enemy speed would
                # otherwise overwhelm the starting squad before the player
                # can react to the first gate. Verified by the difficulty
                # sim against passive (must still fail) and greedy (must
                # survive long enough to pick gates).
                world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
                self.enemy_spawner.intro_delay = 1.5 + 0.5 * (world - 1)
            self.enemy_spawner.reset_per_level()

        if self.gate_spawner is not None:
            if is_boss:
                # Boss levels keep gates available but sparser: ~5 pairs over
                # the whole fight, so the player has rescue options without
                # the gate-stream trivializing the fight.
                self.gate_spawner.interval_px = graphics.ws(1500.0)
                self.gate_spawner.max_grenade_gates = 1
            else:
                self.gate_spawner.interval_px = graphics.ws(cfg["gate_interval_px"])
                self.gate_spawner.max_grenade_gates = int(cfg.get("max_grenade_gates", 0))
            self.gate_spawner.allowed_ops = list(cfg["allowed_ops"])
            self.gate_spawner.allowed_weapons = list(cfg["allowed_weapons"])
            # M14 — equation-difficulty tier on gate labels follows the
            # world. Plain numbers on W1, multi-op expressions on W6.
            self.gate_spawner.world_tier = int(cfg.get("world", 1))
            self.gate_spawner.reset_per_level()

        # Boss spawn / teardown.
        self._teardown_boss()
        if is_boss:
            self._spawn_boss(cfg)
            # Head-start squad + weapon so the fight has weight.
            self.squad_count = int(cfg.get("starting_squad", 1))
            self.current_weapon_id = cfg.get("starting_weapon", DEFAULT_WEAPON_ID)
            self._fire_cooldown = 0.0
        else:
            # Non-boss levels also get a (smaller) starting squad now —
            # `levels.starting_squad` scales 1→6 across W1→W6 so the player
            # can survive the intro before reaching the first gate. Plus
            # the persistent shop bonus (state.squad_bonus) so a player
            # who invested coins gets a tangible boost.
            base = int(cfg.get("starting_squad", 1))
            running_app = ui.app()
            bonus = running_app.state.squad_bonus if (running_app and running_app.state) else 0
            self.squad_count = max(1, base + bonus)
            # Starting weapon: use the player's highest-tier purchased weapon
            # (state.starting_weapon — "pistol" by default). The shop
            # upgrades this for every non-boss level once bought.
            if running_app and running_app.state:
                self.current_weapon_id = running_app.state.starting_weapon

        # Mild power-scaling (#11/#12): snapshot the equipped weapon tier at
        # level start and make enemies proportionally tougher, so an upgraded
        # weapon no longer trivializes early worlds. Damage scales faster than
        # this HP bump, so an upgrade is still a net win.
        if self.enemy_spawner is not None:
            running_app = ui.app()
            tier = (running_app.state.get_weapon_tier(self.current_weapon_id)
                    if (running_app and running_app.state) else 1)
            self.enemy_spawner.hp_scale = 1.0 + 0.25 * (max(1, tier) - 1)
            # Appearance poof for on-screen (top-half) spawns (#16).
            self.enemy_spawner.spawn_poof = self._enemy_spawn_poof

        # Configure the army-formation spawner (non-boss spawn source).
        if self.formation_spawner is not None:
            fs = self.formation_spawner
            fs.columns = int(cfg.get("formation_columns", 6))
            self._rank_interval_start = cfg.get("rank_interval_start", 200.0)
            self._rank_interval_end = cfg.get("rank_interval_end", 120.0)
            fs.enemy_speed = cfg["enemy_speed"]
            fs.enemy_hp = cfg["enemy_hp"]
            fs.hp_scale = self.enemy_spawner.hp_scale if self.enemy_spawner else 1.0
            if cfg.get("boss"):
                fs.spawn_table = [(entities.TYPE_GRUNT, 1.0)]
            else:
                fs.spawn_table = [
                    (entities.TYPE_NAMES[name], weight)
                    for name, weight in cfg["allowed_enemy_types"]
                ]
            fs.reset_per_level(0.0)
        self._update_weapon_range()

    def _update_weapon_range(self) -> None:
        """Recompute the kill-zone for the current weapon and push it to the
        projectile controller + range-line widget. Non-boss only; boss levels
        keep unlimited range so the squad can hit the far boss."""
        if self.stage is None or self.hero is None or self.stage.height < 10:
            return
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        hero_y = sy + sh * HERO_BOTTOM_FRAC
        field_h = (sy + sh) - hero_y
        is_boss = bool(self.level_config and self.level_config.get("boss"))
        running = ui.app()
        is_mp = bool(running and running.current_mode != "single")
        if is_boss or is_mp:
            # Boss levels need the far boss hittable; MP shares the projectile
            # pool so a host's kill line must not clip the opponent's shots.
            self._weapon_range_px = None
        else:
            frac = weapons.get(self.current_weapon_id).range_frac
            self._weapon_range_px = frac * field_h
        kill_y = None if self._weapon_range_px is None else hero_y + self._weapon_range_px
        if self.projectile_controller is not None:
            self.projectile_controller.kill_line_y = kill_y
        if self.range_line is not None:
            if kill_y is None:
                self.range_line.hide()
            else:
                self.range_line.show()
                self.range_line.set_line(sx, sx + sw, kill_y)

    def _enemy_spawn_poof(self, x: float, y: float) -> None:
        """Small particle burst when an enemy spawns on-screen (top half) so it
        appears rather than popping in (#16)."""
        if self.particle_controller is not None:
            self.particle_controller.burst(
                x, y, count=8, speed=180.0, ttl=0.35,
                size=12.0, frame="particle", rng=self._fire_rng,
            )

    def _spawn_boss(self, cfg: dict) -> None:
        if self._atlas is None or self.stage is None:
            return
        sx, sy = self.stage.pos
        sw, sh = self.stage.size
        boss_w = graphics.ws(160.0)
        boss_h = graphics.ws(160.0)
        boss_cx = sx + sw * 0.5
        boss_cy = sy + sh * 0.82
        # Time-scaled HP: sized to the firepower the player ACTUALLY brings to
        # the fight — the boss-level starting squad firing the reference weapon
        # at its current tier — so the fight lasts ~BOSS_TARGET_SECONDS.
        #
        # NOTE: the squad now targets the boss directly (see the fire loop), so
        # this DPS estimate is what really lands. The earlier formula used the
        # squad *cap* (22) as the reference, which — combined with the squad
        # only targeting minions — made the boss take ~80s × (cap/actual) ≈
        # many minutes and effectively unwinnable. Use the real spawn squad.
        running = ui.app()
        wid = cfg.get("starting_weapon", DEFAULT_WEAPON_ID)
        ref_weapon = weapons.get(wid)
        tier = (running.state.get_weapon_tier(wid)
                if running and running.state else 1)
        ref_squad = max(1, min(MAX_SHOOTERS_PER_SHOT,
                               int(cfg.get("starting_squad", 1))))
        ref_dps = (ref_squad * ref_weapon.fire_rate
                   * weapons.tier_damage(ref_weapon, tier))
        boss_hp = max(600, int(round(BOSS_TARGET_SECONDS * ref_dps)))
        self.boss = boss_module.Boss(
            max_hp=boss_hp,
            cx=boss_cx, cy=boss_cy,
            width=boss_w, height=boss_h,
        )
        # M14 — pass the world's main enemy PNG as the boss sprite so
        # the boss reads as a scaled-up version of the world's threat.
        boss_world = getattr(self, "_atlas_world", 1)
        boss_sprite = "assets/sprites/enemy_w{}.png".format(boss_world)
        self.boss_widget = boss_module.BossWidget(
            self.boss, self._atlas,
            sprite_path=boss_sprite,
            size_hint=(None, None), size=(boss_w, boss_h),
        )
        self.stage.add_widget(self.boss_widget)
        # No separate HP bar — the unified top progress bar tracks boss-kill
        # progress, and the boss's body itself shows its health (it turns to
        # grey "stone" from the head down as HP drops).
        # Controller after widgets so an opening volley can render this frame.
        self.boss_controller = boss_module.BossController(
            self.boss, self.enemy_controller,
            minion_hp=int(cfg.get("boss_minion_hp", 1)),
        )
        # Fire one volley now so the player sees an immediate threat.
        self.boss_controller.opening_volley(
            self.hero.center_x if self.hero else boss_cx,
            sx, sy + sh,
        )

    def _teardown_boss(self) -> None:
        if self.boss_widget is not None:
            self.boss_widget.stop()
            if self.boss_widget.parent:
                self.boss_widget.parent.remove_widget(self.boss_widget)
        self.boss = None
        self.boss_widget = None
        self.boss_controller = None

    # --- per-frame update -------------------------------------------------

    # --- M11 polish helpers ----------------------------------------------

    SHAKE_DECAY_PER_SEC = 9.0
    SHAKE_CAP = 18.0

    def _add_shake(self, amount: float) -> None:
        """Bump the shake intensity. Capped so several events in one frame
        don't compound into a window-shattering shake."""
        self.shake_intensity = min(self.SHAKE_CAP,
                                   self.shake_intensity + float(amount))

    def _step_shake(self, dt: float) -> None:
        """Decay shake; pick a random offset within the current intensity."""
        if self.shake_intensity <= 0.05:
            self.shake_intensity = 0.0
            self.shake_x = 0.0
            self.shake_y = 0.0
        else:
            self.shake_x = self._fire_rng.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = self._fire_rng.uniform(-self.shake_intensity, self.shake_intensity)
            # Exponential decay so it feels like a kick rather than a tremor.
            import math as _math
            self.shake_intensity *= _math.exp(-self.SHAKE_DECAY_PER_SEC * dt)
        # Translate the entire screen contents.
        self.root_layout.pos = (self.shake_x, self.shake_y)

    def _spawn_muzzle_polish(self, sx: float, sy: float) -> None:
        """Stationary bright flash + one slow upward smoke wisp."""
        pc = self.particle_controller
        if pc is None:
            return
        # Bright yellow flash — large + brief so it reads as a pop.
        pc.spawn_one(sx, sy, 0.0, 0.0, 22.0, 0.07, "particle")
        # Smoke wisp drifting up.
        smoke_vx = self._fire_rng.uniform(-25.0, 25.0)
        smoke_vy = self._fire_rng.uniform(45.0, 95.0)
        pc.spawn_one(sx, sy + 6.0, smoke_vx, smoke_vy, 10.0, 0.55, "particle")

    def _spawn_death_polish(self, hit_x: float, hit_y: float) -> None:
        """Yellow sparks + red body fragments on enemy death."""
        pc = self.particle_controller
        if pc is None:
            return
        rng = self._fire_rng
        # Hit sparks (yellow).
        pc.burst(hit_x, hit_y, count=4, speed=240.0, ttl=0.32,
                 size=10.0, frame="particle", rng=rng)
        # Body fragments (red shards reusing the enemy_red atlas frame).
        # Smaller + slower than the sparks so they feel like meat, not sparkle.
        pc.burst(hit_x, hit_y, count=5, speed=160.0, ttl=0.48,
                 size=14.0, frame="enemy_red", rng=rng)

    # --- archetype on-death effects --------------------------------------

    BOMBER_AOE_RADIUS = 95.0       # px; squad members in this circle attrited
    BOMBER_MAX_LOSSES = 3          # cap squad losses per bomber explosion

    def _bomber_explode(self, x: float, y: float) -> None:
        """Bomber AOE: extra particle ring + attrition for nearby squad.

        Models the bomber as a melee-style threat: kill it early or pay
        when it pops at the squad's front line.
        """
        if self.particle_controller is not None:
            self.particle_controller.burst(
                x, y, count=14, speed=380.0, ttl=0.45,
                size=14.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                x, y, count=10, speed=260.0, ttl=0.55,
                size=16.0, frame="enemy_red", rng=self._fire_rng,
            )
        self._add_shake(2.2)
        # Squad members in radius take one hit each (capped). Shield AND
        # Freeze block the loss (frozen enemies can't attack).
        if (self.shield_active_until > self._run_time
                or self.freeze_active_until > self._run_time):
            return
        if self.squad_pool is None:
            return
        sp = self.squad_pool
        r2 = self.BOMBER_AOE_RADIUS * self.BOMBER_AOE_RADIUS
        losses = 0
        for i in range(sp.capacity):
            if losses >= self.BOMBER_MAX_LOSSES:
                break
            if not sp.active[i]:
                continue
            dx = sp.cx[i] - x
            dy = sp.cy[i] - y
            if dx * dx + dy * dy <= r2:
                losses += 1
        # Also catch the hero if close.
        hero_caught = False
        if self.hero is not None:
            dx = self.hero.center_x - x
            dy = self.hero.center_y - y
            if dx * dx + dy * dy <= r2:
                hero_caught = True
        total_losses = losses + (1 if hero_caught else 0)
        if total_losses == 0:
            return
        self.squad_count = max(0, self.squad_count - total_losses)
        self.attrition_total += total_losses
        if self.hero is not None:
            self.hero.flash(duration=0.30,
                            color=(1.0, 0.25, 0.25, 0.78))
        ui.app().audio.play_sfx("damage")
        if self.squad_count <= 0:
            self._end_level(won=False)

    def _on_pickup_collect(self, ptype: int, x: float, y: float) -> None:
        """Hero touched a coin or double-coin pickup. Coins go straight to
        the run total (with 2× active if the double-coin timer is up);
        the double-coin pickup starts/refreshes that timer."""
        if ptype == entities.PICKUP_COIN:
            coins = entities.PickupController.COIN_PER_PICKUP
            if self.double_coin_until > self._run_time:
                coins *= 2
            self._coins_earned += coins
            self._coins_pickups += coins
            if self.particle_controller is not None:
                self.particle_controller.burst(
                    x, y, count=10, speed=320.0, ttl=0.40,
                    size=10.0, frame="particle", rng=self._fire_rng,
                )
            # Rising "+N" pop at the coin (ground pickups only — progress
            # coins from kills/gates/completion get no pop), same style as
            # the shop purchase animation.
            self._float_text("+{}".format(coins), (1.0, 0.90, 0.30, 1.0),
                             cx=x, cy=y)
            ui.app().audio.play_sfx("coin")
        else:    # PICKUP_DOUBLE_COIN
            duration = entities.PickupController.DOUBLE_COIN_DURATION_SEC
            self.double_coin_until = self._run_time + duration
            if self.particle_controller is not None:
                self.particle_controller.burst(
                    x, y, count=20, speed=400.0, ttl=0.55,
                    size=14.0, frame="particle", rng=self._fire_rng,
                )
                self.particle_controller.burst(
                    x, y, count=12, speed=240.0, ttl=0.70,
                    size=18.0, frame="projectile", rng=self._fire_rng,
                )
            ui.app().audio.play_sfx("gate_pickup")
            self._add_shake(2.0)

    def _splitter_split(self, x: float, y: float) -> None:
        """Splitter on-death: spawn 3 grunts at the kill location with
        outward velocity. Punishes overkill — if a wave of splitters all
        die at the front line, the squad eats 9 fresh grunts immediately.
        """
        if self.enemy_controller is None:
            return
        # Lower base hp so split grunts don't feel like infinite respawns.
        # Split grunts spawn directly (not via EnemySpawner._spawn_one), so
        # scale their world-px size/speed/offset/chase with density here.
        speed = graphics.ws(self.enemy_spawner.enemy_speed if self.enemy_spawner
                            else 220.0)
        sz = graphics.ws(36.0)
        dx = graphics.ws(35.0)
        for k in (-1, 0, 1):
            self.enemy_controller.spawn(
                x + k * dx, y, sz, sz, "enemy_red",
                hp=1, speed=speed,
                chase=graphics.ws(self._fire_rng.uniform(50.0, 110.0)),
                enemy_type=entities.TYPE_GRUNT,
            )

    def _update(self, dt):
        if self._level_ended or self.paused:
            return
        # M13 — multiplayer role dispatch. Client runs no simulation,
        # only mirrors host state and forwards input.
        role = self._mp_role()
        if role == "client":
            self._mp_client_tick(dt)
            return
        if role == "host":
            # Drain client input BEFORE the sim tick so opponent_target_x
            # reflects the latest steering.
            self._mp_drain_host_inbox()
        # Shake first so the offset applies to everything else this frame.
        self._step_shake(dt)
        self._run_time += dt
        # World scroll rate scales with density so the world moves the same
        # on-screen speed at any resolution; self.distance therefore lives in
        # the scaled domain (distance_goal/gate/pickup thresholds match it).
        scroll = graphics.ws(SCROLL_SPEED_PX_PER_SEC)
        self.distance += scroll * dt

        sx, sy = self.stage.pos
        sw, sh = self.stage.size

        # 1. Scroll the dashed centerline stripes downward (visual sense of
        #    moving forward in a top-down view).
        if sh > 0:
            drop = scroll * dt
            for i in range(len(self._stripe_ys)):
                self._stripe_ys[i] -= drop
                while self._stripe_ys[i] < sy:
                    self._stripe_ys[i] += sh
            self._paint_stripes()

        # 2. Hero X: drag input + lane gravity. When the player isn't
        #    actively dragging, the hero's X relaxes toward the nearest
        #    lane center (empty list in M4 = pure free positioning).
        if self.hero is not None:
            target = self._hero_target_x
            # Lane gravity gently snaps a free-floating hero toward the
            # nearest gate. In auto mode the GA already picks an exact target
            # (a gate center, a deliberate gap-miss, or an enemy dodge), so
            # letting gravity pull it back toward a lane center would fight
            # those choices — skip it while the autoplayer is driving.
            if not self._dragging and not self.auto_mode:
                target = lane_gravity_target(target, self.lane_centers, dt)
                self._hero_target_x = target
            min_x = sx + graphics.ws(HERO_W) * 0.5
            max_x = sx + sw - graphics.ws(HERO_W) * 0.5
            target = max(min_x, min(max_x, target))
            self._hero_target_x = target
            # Hero motion: manual touch already feels smooth because the
            # finger updates target_x incrementally. The GA, however,
            # sets a target far from the current hero position once per
            # retarget tick (~6-12 Hz), so writing center_x directly
            # would teleport the hero. Cap the per-frame slide at
            # AUTO_HERO_MAX_SPEED so it reads like a real player.
            if self.auto_mode:
                desired_dx = target - self.hero.center_x
                max_step = graphics.ws(AUTO_HERO_MAX_SPEED) * dt
                if desired_dx > max_step:
                    self.hero.center_x += max_step
                elif desired_dx < -max_step:
                    self.hero.center_x -= max_step
                else:
                    self.hero.center_x = target
            else:
                self.hero.center_x = target

            # Running bob — vertical sine driven by distance (so it looks
            # right even at varying frame rates).
            bob = math.sin(self.distance / graphics.ws(22.0)) * graphics.ws(5.0)
            self.hero.y = sy + sh * HERO_BOTTOM_FRAC + bob

            # Manual-aim reticle. In manual mode + human control, the reticle
            # is driven by the trailing aim-lead (aim follows steering). In
            # manual mode while the autoplayer drives, it follows the auto-aim
            # target stashed by the fire tick (#9 — show where the GA aims).
            if self._aim_mode == "manual" and self.aim_reticle is not None:
                muzzle_y = self.hero.center_y + graphics.ws(MUZZLE_OFFSET_Y)
                _lead = (self._weapon_range_px
                         if self._weapon_range_px is not None
                         else graphics.ws(RETICLE_LEAD_DIST))
                if self.auto_mode:
                    if self._auto_target is not None:
                        rx, ry = self._auto_target
                    else:
                        rx = self.hero.center_x
                        ry = muzzle_y + _lead
                else:
                    self._aim_lead_x = aim.update_aim_lead(
                        self._aim_lead_x, self._hero_target_x, dt, AIM_LEAD_EASE)
                    offset = self._hero_target_x - self._aim_lead_x
                    self._aim_angle = aim.aim_angle(
                        offset, graphics.ws(AIM_OFFSET_FULL), AIM_MAX_RAD)
                    rx, ry = aim.reticle_point(
                        self.hero.center_x, muzzle_y, self._aim_angle,
                        _lead)
                self._reticle_x, self._reticle_y = rx, ry
                self.aim_reticle.set_endpoints(
                    self.hero.center_x, muzzle_y, rx, ry)
                self.aim_reticle.show()
            elif self.aim_reticle is not None:
                self.aim_reticle.hide()

            # Hero identity marker — green ring under the local hero.
            if self.hero_marker is not None:
                self.hero_marker.center_x = self.hero.center_x
                self.hero_marker.y = self.hero.y - dp(2)

            # M13 — Opponent hero. On the HOST this is driven by client
            # input (already converted to pixel-space in
            # _mp_drain_host_inbox). Moves at the same lateral speed cap
            # as the autoplayer to keep traversal feeling like a player.
            if self.opponent_hero is not None and role == "host":
                ox = self.opponent_hero.center_x
                desired_dx = self.opponent_target_x - ox
                max_step = graphics.ws(AUTO_HERO_MAX_SPEED) * dt
                if desired_dx > max_step:
                    self.opponent_hero.center_x += max_step
                elif desired_dx < -max_step:
                    self.opponent_hero.center_x -= max_step
                else:
                    self.opponent_hero.center_x = self.opponent_target_x
                self.opponent_hero.y = sy + sh * HERO_BOTTOM_FRAC + bob
                if self.opponent_marker is not None:
                    self.opponent_marker.center_x = self.opponent_hero.center_x
                    self.opponent_marker.y = self.opponent_hero.y - dp(2)

        # 3. Enemies: spawner interval can be modulated by level type
        #    (static / hybrid / dynamic), then spawner ticks + enemies update.
        x_min = sx
        y_min = sy
        x_max = sx + sw
        y_max = sy + sh
        # Army formation: ranks spawn on a distance cadence, tightening
        # within the level (denser toward the end). Boss levels spawn no
        # ranks — the boss controller owns minions.
        if (self.formation_spawner is not None
                and self.level_config is not None
                and not self.level_config.get("boss")):
            if self.distance_goal > 0:
                progress = min(1.0, self.distance / self.distance_goal)
            else:
                progress = 0.0
            self.formation_spawner.rank_interval_px = graphics.ws(
                self._rank_interval_start
                + (self._rank_interval_end - self._rank_interval_start) * progress)
            self.formation_spawner.update(
                self.distance, x_min, y_min, x_max, y_max)

        if (self.enemy_controller is not None
                and self.enemy_spawner is not None
                and self.hero is not None):
            # Freeze booster: enemies stop dead — advance their motion with
            # dt=0 so positions hold (and none can escape past the squad)
            # while the squad keeps firing. Attrition + bomber AoE are gated
            # separately (same check as shield).
            enemy_dt = 0.0 if self.freeze_active_until > self._run_time else dt
            # `on_escape` charges the same one-runner cost when an
            # enemy slips off the bottom on a path that
            # `resolve_squad_attrition` doesn't cover.
            self.enemy_controller.update(
                enemy_dt, self.hero.center_x,
                x_min, y_min, x_max, y_max,
                on_escape=self._on_squad_loss,
            )

        # 3a. Pickups: spawner drops coin / double-coin items; controller
        # scrolls them with the world. Hero auto-collects on overlap.
        if (self.pickup_controller is not None
                and self.pickup_spawner is not None
                and self.hero is not None
                and self.level_config is not None
                and not self.level_config.get("boss")):
            self.pickup_spawner.tick(
                self.distance, x_min, x_max, y_max,
                scroll,
            )
            self.pickup_controller.update(dt, y_min)
            # Magnet booster: home every active pickup toward the hero so the
            # normal collection radius vacuums them up — coins fly in.
            if self.magnet_active_until > self._run_time:
                pp = self.pickup_pool
                hx, hy = self.hero.center_x, self.hero.center_y
                step = graphics.ws(boosters.MAGNET_PULL_SPEED) * dt
                for i in range(pp.capacity):
                    if not pp.active[i]:
                        continue
                    dx = hx - pp.cx[i]
                    dy = hy - pp.cy[i]
                    dist = math.hypot(dx, dy)
                    if dist > 1.0:
                        pp.cx[i] += dx / dist * min(step, dist)
                        pp.cy[i] += dy / dist * min(step, dist)
            entities.resolve_pickup_collection(
                self.pickup_controller,
                self.hero.center_x, self.hero.center_y,
                graphics.ws(PICKUP_COLLECT_RADIUS),
                self._on_pickup_collect,
            )
            # M13 — versus: opponent collects pickups independently via
            # the per-player consumed_by_p2 array. The pool slot stays
            # active until the pickup scrolls off, so both players get
            # their own coin from each pickup.
            if (self._mp_role() == "host"
                    and self.opponent_hero is not None
                    and self.opponent_alive):
                entities.resolve_pickup_collection(
                    self.pickup_controller,
                    self.opponent_hero.center_x, self.opponent_hero.center_y,
                    graphics.ws(PICKUP_COLLECT_RADIUS),
                    self._on_opponent_pickup_collect,
                    player_id=1,
                )

        # 3b. Gates: spawner emits a new pair when distance passes the next
        # interval; controller scrolls all gates + checks pass-through.
        if (self.gate_controller is not None
                and self.gate_spawner is not None
                and self.hero is not None):
            self.gate_spawner.tick(self.distance, x_min, x_max, y_max)
            self.gate_controller.update(
                dt, scroll,
                self.hero.center_x, self.hero.center_y,
                self._on_apply_gate,
                on_miss=self._on_miss_gate,
            )
            # Lane gravity follows the active pair's gates.
            self.lane_centers = self.gate_controller.active_lane_centers(
                self.hero.center_y,
            )

        # 3c. Boss (M10): drift + attack patterns. Boss spawns minions through
        # `enemy_controller`; everything else (squad fire, attrition, particles)
        # works on those minions unchanged.
        if (self.boss_controller is not None
                and self.boss is not None
                and self.hero is not None):
            self.boss_controller.update(
                dt, self.hero.center_x, self.hero.center_y,
                x_min, y_min, x_max, y_max,
            )
            # Phase-2 transition fanfare: a one-shot ring of red particles
            # at the boss center + a shake so the player sees it happened.
            if self.boss.phase2_transition_pending:
                self.boss.phase2_transition_pending = False
                if self.particle_controller is not None:
                    self.particle_controller.burst(
                        self.boss.cx, self.boss.cy, count=22, speed=420.0,
                        ttl=0.55, size=15.0, frame="enemy_red",
                        rng=self._fire_rng,
                    )
                self._add_shake(6.0)
                ui.app().audio.play_sfx("hit")

        # 4. Squad: sync pool to squad_count, position followers in formation.
        if (self.squad_controller is not None
                and self.hero is not None):
            self.squad_controller.sync_to_count(self.squad_count - 1)
            self.squad_controller.update_formation(
                self.hero.center_x, self.hero.center_y,
            )
            # The squad renders through ``squad_renderer`` (BatchedRenderer)
            # in a single mesh draw — the pool's (cx, cy, hw, hh) are the
            # source of truth and ``squad_renderer.rebuild()`` picks them up
            # each frame.
        # M13 — also drive opponent's squad on the host so the player can
        # see the other crowd grow / shrink as the opponent picks gates.
        if (role == "host"
                and self.opponent_squad_controller is not None
                and self.opponent_hero is not None
                and self.opponent_alive):
            self.opponent_squad_controller.sync_to_count(
                max(0, self.opponent_squad - 1),
            )
            self.opponent_squad_controller.update_formation(
                self.opponent_hero.center_x, self.opponent_hero.center_y,
            )

        # 5. Auto-fire: cooldown → fire_from_positions(hero + squad) → collision → particles.
        if (self.hero is not None
                and self.projectile_controller is not None
                and self.particle_controller is not None
                and self.enemy_controller is not None
                and self.squad_pool is not None):
            weapon = weapons.get(self.current_weapon_id)
            self._fire_cooldown -= dt
            if self._fire_cooldown <= 0.0:
                manual_human = (self._aim_mode == "manual"
                                and not self.auto_mode)
                if manual_human:
                    # Player-aimed: fire at the reticle the _update block set.
                    target_x, target_y, has_target = (
                        self._reticle_x, self._reticle_y, True)
                else:
                    # Auto-aim (also used when the GA autoplayer drives, even
                    # in manual mode — it aims at monsters per #9). On boss
                    # levels prefer a close add over the boss so adds get
                    # cleared instead of slipping into the squad (#5).
                    target_x = target_y = 0.0
                    has_target = False
                    if self.boss is not None and self.boss.alive:
                        _ti = entities.find_nearest_threat(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller,
                            graphics.ws(BOSS_ADD_THREAT_FRONT))
                        if _ti >= 0:
                            target_x = self.enemy_pool.cx[_ti]
                            target_y = self.enemy_pool.cy[_ti]
                        else:
                            target_x, target_y = self.boss.cx, self.boss.cy
                        has_target = True
                    else:
                        _rng_px = (self._weapon_range_px
                                   if self._weapon_range_px is not None
                                   else graphics.ws(99999.0))
                        _ti = entities.find_nearest_threat(
                            self.hero.center_x, self.hero.center_y,
                            self.enemy_controller, _rng_px)
                        if _ti >= 0:
                            target_x = self.enemy_pool.cx[_ti]
                            target_y = self.enemy_pool.cy[_ti]
                            has_target = True
                    # Stash for the reticle when the GA drives in manual mode.
                    self._auto_target = (target_x, target_y) if has_target else None
                if has_target:
                    # Shooter positions: hero muzzle + every active follower's muzzle.
                    hero_muzzle = (self.hero.center_x,
                                   self.hero.center_y + graphics.ws(MUZZLE_OFFSET_Y))
                    positions = [hero_muzzle]
                    sp = self.squad_pool
                    sc = self.squad_controller
                    squad_muzzle = graphics.ws(sc.MUZZLE_OFFSET_Y)
                    for i in range(sp.capacity):
                        if sp.active[i]:
                            positions.append((sp.cx[i], sp.cy[i] + squad_muzzle))
                    # Sub-linear firepower cap. Above MAX_SHOOTERS_PER_SHOT,
                    # randomly sample so every squad member rotates in over
                    # time (every shot picks a different subset). Squad
                    # redundancy stays meaningful for absorbing attrition but
                    # firepower plateaus — late-world levels with dense
                    # enemies are no longer trivialized by a 100-runner squad.
                    if len(positions) > MAX_SHOOTERS_PER_SHOT:
                        positions = self._fire_rng.sample(positions, MAX_SHOOTERS_PER_SHOT)
                    # Apply weapon-tier damage multiplier from the player's
                    # shop purchases (state.get_weapon_tier). Tier 1 (default)
                    # = 1.0×; tier 4 = 3.0×.
                    running_app = ui.app()
                    tier = (running_app.state.get_weapon_tier(self.current_weapon_id)
                            if running_app and running_app.state else 1)
                    effective_damage = weapons.tier_damage(weapon, tier)
                    # Overdrive booster: extra punch per shot + a faster
                    # cooldown (applied below) for a few seconds.
                    overdrive = self.overdrive_active_until > self._run_time
                    if overdrive:
                        effective_damage = max(
                            1, int(round(effective_damage
                                         * boosters.OVERDRIVE_DAMAGE_MULT)))
                    if self._aim_mode == "manual" and self.aim_reticle is not None:
                        # Lock-flash the reticle when the actual target sits
                        # near the convergence point (clear "you will hit this"
                        # cue). Compare the boss/enemy position to the reticle
                        # in BOTH axes — comparing to target_x would be trivially
                        # true in manual+human mode (target_x IS the reticle).
                        lock_x = graphics.ws(60.0)
                        lock_y = graphics.ws(80.0)
                        locked = False
                        if self.boss is not None and self.boss.alive:
                            locked = (abs(self.boss.cx - self._reticle_x) < lock_x
                                      and abs(self.boss.cy - self._reticle_y) < lock_y)
                        else:
                            near = entities.find_nearest_threat(
                                self.hero.center_x, self.hero.center_y,
                                self.enemy_controller,
                                (self._weapon_range_px
                                 if self._weapon_range_px is not None
                                 else graphics.ws(RETICLE_LEAD_DIST * 1.4)))
                            if near >= 0:
                                locked = (abs(self.enemy_pool.cx[near] - self._reticle_x) < lock_x
                                          and abs(self.enemy_pool.cy[near] - self._reticle_y) < lock_y)
                        self.aim_reticle.set_locked(locked)
                    entities.fire_from_positions(
                        positions, target_x, target_y, weapon,
                        self.projectile_controller, self._fire_rng,
                        damage_override=effective_damage,
                    )
                    self._fire_cooldown = 1.0 / weapon.fire_rate
                    if overdrive:
                        self._fire_cooldown /= boosters.OVERDRIVE_FIRE_MULT
                    # M11 polish: muzzle flash + gun smoke at the hero's muzzle,
                    # plus a tiny recoil shake.
                    self._spawn_muzzle_polish(*hero_muzzle)
                    self._add_shake(0.6)

            self.projectile_controller.update(dt, x_min, y_min, x_max, y_max)

            # Projectile vs enemy collisions. on_kill now also receives
            # the killer (projectile owner) — 0 = local, 1 = opponent —
            # so versus kills route to the right player's stats.
            def _on_kill(hit_x, hit_y, enemy_type, killer, _self=self):
                _self._spawn_death_polish(hit_x, hit_y)
                _self._add_shake(0.35)
                reward = COIN_PARTIAL_REWARD.get(enemy_type, 0.30)
                if _self.double_coin_until > _self._run_time:
                    reward *= 2.0
                if killer == 0:
                    _self._coin_remainder += reward
                    while _self._coin_remainder >= 1.0:
                        _self._coins_earned += 1
                        _self._coin_remainder -= 1.0
                    _self.kills_total += 1
                    _s = combat_juice.score_for_kill(enemy_type)
                    _self._pending_score += _s
                    _self.score_total += _s
                    _self._had_kill_this_frame = True
                else:
                    _self._opponent_coin_remainder += reward
                    while _self._opponent_coin_remainder >= 1.0:
                        _self.opponent_coins += 1
                        _self._opponent_coin_remainder -= 1.0
                    _self.opponent_kills += 1
                if enemy_type == entities.TYPE_BOMBER:
                    _self._bomber_explode(hit_x, hit_y)
                elif enemy_type == entities.TYPE_SPLITTER:
                    _self._splitter_split(hit_x, hit_y)
            def _on_hit(hx, hy, etype, owner, _self=self):
                if owner == 0:
                    _self._had_hit_this_frame = True
            entities.resolve_projectile_collisions(
                self.projectile_controller, self.enemy_controller, self.grid,
                _on_kill, on_hit=_on_hit,
            )

            # Projectile vs boss (M10): AABB-only — boss is one big entity.
            if self.boss_controller is not None and self.boss is not None and self.boss.alive:
                def _on_boss_hit(hit_x, hit_y, died,
                                 _pc=self.particle_controller, _rng=self._fire_rng,
                                 _self=self):
                    _pc.burst(hit_x, hit_y, count=4, speed=200.0, ttl=0.30,
                              size=10.0, frame="particle", rng=_rng)
                    # M11: bigger shake when the boss is reeling + a squash
                    # punch on the sprite so the boss visibly reacts.
                    _self._add_shake(0.9)
                    if _self.boss_widget is not None:
                        _self.boss_widget.on_hit()
                    if died:
                        # Big celebratory burst at the boss center on kill.
                        if _self.boss is not None:
                            _pc.burst(_self.boss.cx, _self.boss.cy,
                                      count=30, speed=380.0, ttl=0.65,
                                      size=14.0, frame="particle", rng=_rng)
                            _pc.burst(_self.boss.cx, _self.boss.cy,
                                      count=18, speed=260.0, ttl=0.80,
                                      size=18.0, frame="enemy_red", rng=_rng)
                        _self._add_shake(_self.SHAKE_CAP)  # max kick on boss death
                        _self._end_level(won=True)
                boss_module.resolve_projectile_vs_boss(
                    self.projectile_controller, self.boss_controller, _on_boss_hit,
                )

            # Combat SFX — one rate-limited cue per window, death-priority.
            _cue = combat_juice.combat_cue(self._had_kill_this_frame,
                                           self._had_hit_this_frame)
            if _cue is not None and combat_juice.sfx_due(
                    self._run_time, self._last_combat_sfx, COMBAT_SFX_INTERVAL):
                ui.app().audio.play_sfx(_cue)
                self._last_combat_sfx = self._run_time
            self._had_kill_this_frame = False
            self._had_hit_this_frame = False

            # Aggregated score popup — one Label per window, never per kill.
            if self._run_time - self._last_score_popup >= SCORE_POPUP_INTERVAL:
                if self._pending_score > 0 and self.hero is not None:
                    self._float_text(
                        "+{}".format(self._pending_score), SCORE_COLOR,
                        cx=self.hero.center_x,
                        cy=self.hero.center_y + graphics.ws(SCORE_POPUP_OFFSET))
                    self._pending_score = 0
                self._last_score_popup = self._run_time

            # M13 — opponent's auto-fire + gate pass on the host's tick.
            # Done here so opponent's projectiles are spawned BEFORE the
            # collision pass below, letting opponent's shots resolve the
            # same frame they're fired.
            if role == "host":
                self._opponent_tick_versus(dt)

            # Squad attrition: enemies that pierce the squad's front line cost one runner each.
            # When squad_count hits 0 the hero falls and the level fails.
            # M13 — in versus, also attrit the opponent's squad when an
            # enemy reaches their front line. Single pass over the enemy
            # pool covers both heroes so the bookkeeping (release +
            # recycle counter) stays consistent.
            if (self._mp_role() == "host"
                    and self.opponent_hero is not None
                    and self.opponent_alive):
                front_offset = graphics.ws(ATTRITION_FRONT_OFFSET)
                zone_half_w = graphics.ws(ATTRITION_ZONE_HALF_W)
                entities.resolve_squad_attrition_dual(
                    self.enemy_controller,
                    self.hero.center_x, self.hero.center_y,
                    self.hero.center_y + front_offset,
                    self._on_squad_loss,
                    self.opponent_hero.center_x, self.opponent_hero.center_y,
                    self.opponent_hero.center_y + front_offset,
                    self._on_opponent_squad_loss,
                    zone_half_w,
                )
            else:
                entities.resolve_squad_attrition(
                    self.enemy_controller,
                    self.hero.center_x, self.hero.center_y,
                    graphics.ws(ATTRITION_ZONE_HALF_W),
                    self.hero.center_y + graphics.ws(ATTRITION_FRONT_OFFSET),
                    self._on_squad_loss,
                )

            self.particle_controller.update(dt)

        # 6. Mesh rebuilds (one canvas write per renderer per frame).
        if self.enemy_renderer is not None:
            self.enemy_renderer.rebuild()
        if self.projectile_renderer is not None:
            self.projectile_renderer.rebuild()
        if self.opponent_projectile_renderer is not None:
            self.opponent_projectile_renderer.rebuild()
        if self.particle_renderer is not None:
            self.particle_renderer.rebuild()
        if self.squad_renderer is not None:
            self.squad_renderer.rebuild()
        if self.opponent_squad_renderer is not None:
            self.opponent_squad_renderer.rebuild()
        if self.pickup_renderer is not None:
            self.pickup_renderer.rebuild()
        # 6b. Boss widget + HP bar follow the underlying data each frame.
        if self.boss_widget is not None:
            self.boss_widget.update_from_boss()
        # 6c. Hero hit-flash decay.
        if self.hero is not None:
            self.hero.tick_flash(dt)
        # 6c-bis. Shield aura tracks the hero while a shield is up.
        if self.shield_aura is not None and self.hero is not None:
            if self.shield_active_until > self._run_time:
                self.shield_aura.center = self.hero.center
                if self.shield_aura.opacity == 0.0:
                    self.shield_aura.show()
            elif self.shield_aura.opacity != 0.0:
                self.shield_aura.hide()
        # 6c-ter. Icy stage tint while Freeze is active.
        self._set_freeze_tint(self.freeze_active_until > self._run_time)

        # 6c. Distance goal reached → level complete (skipped on boss levels —
        #     boss death drives the win condition there).
        is_boss_level = bool(self.level_config and self.level_config.get("boss"))
        if (not self._level_ended
                and not is_boss_level
                and self.distance_goal > 0
                and self.distance >= self.distance_goal):
            self._end_level(won=True)
            return

        # 7. HUD + debug overlay.
        hero_cx = self.hero.center_x if self.hero is not None else 0.0
        enemy_count = self.enemy_pool.active_count if self.enemy_pool is not None else 0
        weapon_name = weapons.get(self.current_weapon_id).name
        progress = "{:.0f} / {:.0f}".format(self.distance, self.distance_goal) \
            if self.distance_goal > 0 else "{:.0f}".format(self.distance)
        # Sync the on-screen booster buttons (count, active countdown, dim).
        self._sync_booster_btn(self.grenade_btn, self.grenade_count,
                               (0.20, 0.80, 0.95, 1), None)
        self._sync_booster_btn(self.shield_btn, self.shield_count,
                               (0.50, 0.85, 1.00, 1), self.shield_active_until)
        self._sync_booster_btn(self.reinforce_btn, self.reinforce_count,
                               _dim_color(boosters.REINFORCE.hud_color), None)
        self._sync_booster_btn(self.freeze_btn, self.freeze_count,
                               _dim_color(boosters.FREEZE.hud_color),
                               self.freeze_active_until)
        self._sync_booster_btn(self.overdrive_btn, self.overdrive_count,
                               _dim_color(boosters.OVERDRIVE.hud_color),
                               self.overdrive_active_until)
        self._sync_booster_btn(self.magnet_btn, self.magnet_count,
                               _dim_color(boosters.MAGNET.hud_color),
                               self.magnet_active_until)
        # Update the standalone 2× COINS power-up indicator (top-center).
        self._update_dc_panel()
        # Top-bar level progress (0..1).
        self._dist_progress = self._level_progress()
        self._sync_dist_bar()
        # Weapon chip — name + current tier from the shop. Boss levels
        # override the starting weapon mid-level and the host's
        # `current_weapon_id` mutates on a WEAPON gate; either way the
        # tier reflects the local player's shop investment, so a
        # mid-level weapon swap shows the same tier the player paid for.
        running_app = ui.app()
        tier = (running_app.state.get_weapon_tier(self.current_weapon_id)
                if running_app and running_app.state else 1)
        # Tier indicator: 1-4 filled diamonds (gold) followed by 0-3
        # empty diamonds — visual at-a-glance tier read that doesn't
        # need the player to parse "Lv3" each time.
        tier = max(1, min(4, tier))
        # Bracket-style tier indicator — single line, fits the chip
        # width regardless of font support for special Unicode glyphs.
        weapon_label = "{} [{}/4]".format(weapon_name, tier)

        # Stat chips.
        if self.squad_chip is not None:
            self.squad_chip.set_value(str(self.squad_count))
            self.weapon_chip.set_value(weapon_label)
            self.kills_chip.set_value(str(self.kills_total))
            other = self._coins_earned - self._coins_pickups
            self.coins_chip.set_value("+{}+{}".format(
                self._coins_pickups, other,
            ))
        if self.squad_count > self._squad_peak:
            self._squad_peak = self.squad_count
        gates_passed = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed = self.gate_controller.missed_total if self.gate_controller else 0
        proj_active = self.projectile_pool.active_count if self.projectile_pool else 0
        part_active = self.particle_pool.active_count if self.particle_pool else 0
        squad_active = self.squad_pool.active_count if self.squad_pool else 0
        self.debug.report_counts(
            dist=int(self.distance),
            enemies=enemy_count, kills=self.kills_total,
            gates=gates_passed, missed=gates_missed,
            squad=squad_active + 1, lost=self.attrition_total,
            projectiles=proj_active, particles=part_active,
        )

        # M13 — host-only: push a snapshot to the client at 20 Hz (every
        # SNAPSHOT_INTERVAL_TICKS frames). Runs at the very end of the
        # tick so the snapshot reflects this frame's resolved state.
        if role == "host":
            self._mp_tick += 1
            if self._mp_tick % self.SNAPSHOT_INTERVAL_TICKS == 0:
                self._mp_send_snapshot()

    # --- gate effect application -----------------------------------------

    def _on_miss_gate(self) -> None:
        """Called once per gate pair the player let scroll past untouched.

        Drives the pity-gate floor on the spawner side — two consecutive
        misses guarantee at least one safe (MUL / ADD) option in the next
        pair so the player can recover.
        """
        if self.gate_spawner is not None:
            self.gate_spawner.consecutive_misses += 1

    def _on_apply_gate(self, gate) -> None:
        """Apply a passed gate's effect: mutate squad_count or swap weapon."""
        if self._level_ended:
            return
        # Player picked a gate → reset the pity-counter, earn small coin reward
        # (with 2× when the pickup is active).
        if self.gate_spawner is not None:
            self.gate_spawner.consecutive_misses = 0
        gate_reward = COIN_REWARD_GATE
        if self.double_coin_until > self._run_time:
            gate_reward *= 2
        self._coins_earned += gate_reward
        _prev_squad = self.squad_count
        if gate.op == gates.OP_MUL:
            self.squad_count = min(MAX_SQUAD, max(1, self.squad_count * int(gate.value)))
        elif gate.op == gates.OP_ADD:
            self.squad_count = min(MAX_SQUAD, self.squad_count + int(gate.value))
        elif gate.op == gates.OP_SUB:
            # SUB can take the squad to zero — game over if that happens.
            self.squad_count = max(0, self.squad_count - int(gate.value))
        elif gate.op == gates.OP_DIV:
            # Divide squad by value (integer floor). At squad=1 ÷2 → 0 = death,
            # so DIV gates only appear from W3 where the player has grown.
            divisor = max(1, int(gate.value))
            self.squad_count = max(0, self.squad_count // divisor)
        elif gate.op == gates.OP_WEAPON:
            if gate.value in weapons.WEAPONS:
                self.current_weapon_id = gate.value
                self._update_weapon_range()
                self._fire_cooldown = 0.0
        elif gate.op == gates.OP_GRENADE:
            self._apply_grenade_effect(int(gate.value))
        elif gate.op == gates.OP_REINFORCE:
            self._apply_reinforce_effect(int(gate.value))
        elif gate.op == gates.OP_FREEZE:
            self._apply_freeze_effect(int(gate.value))
        elif gate.op == gates.OP_OVERDRIVE:
            self._apply_overdrive_effect(int(gate.value))
        elif gate.op == gates.OP_MAGNET:
            self._apply_magnet_effect(int(gate.value))
        # Squad-change popup (distinct from coins): every gate gets feedback.
        if gate.op in (gates.OP_MUL, gates.OP_ADD, gates.OP_SUB, gates.OP_DIV):
            _sym = {gates.OP_MUL: "×", gates.OP_ADD: "+",
                    gates.OP_SUB: "−", gates.OP_DIV: "÷"}[gate.op]
            _delta = self.squad_count - _prev_squad
            _color = GATE_GAIN_COLOR if _delta >= 0 else GATE_LOSS_COLOR
            self._float_text("{}{}".format(_sym, int(gate.value)), _color)
        elif gate.op == gates.OP_WEAPON:
            self._float_text("{}!".format(str(gate.value).upper()),
                             GATE_WEAPON_COLOR)
        # Reward gates pop their own booster float-text from the effect calls.
        # Audio + particle burst at the hero so the pickup reads. Weapon gates
        # get the weapon-swap cue; everything else the generic pickup blip.
        running = ui.app()
        running.audio.play_sfx(
            "weapon_swap" if gate.op == gates.OP_WEAPON else "gate_pickup")
        if self.particle_controller is not None and self.hero is not None:
            self.particle_controller.burst(
                self.hero.center_x, self.hero.center_y + graphics.ws(HERO_H * 0.3),
                count=10, speed=260.0, ttl=0.45, size=12.0,
                frame="particle", rng=self._fire_rng,
            )
        if self.squad_count <= 0:
            self._end_level(won=False)

    def _end_level(self, won: bool) -> None:
        """Cancel the update loop, persist progress, then show banner + dialog.

        The dialog used to open the instant the win/lose condition fired,
        which felt abrupt. M11.5 splits the flow: persist + show a centered
        banner immediately, then open the existing LevelResultDialog after
        a short fade so the moment of resolution reads.
        """
        if self._level_ended:
            return
        self._level_ended = True
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        # Stop the GA but keep auto_mode True — the player wants to keep
        # watching it play. The next level will restart the daemon in
        # _reset() if auto_mode is still on.
        if self.auto is not None:
            self.auto.stop()

        # M13 — broadcast the final scoreboard to the client. The result
        # message is per-recipient (each side gets local_won / local_score
        # framed from their perspective) so the existing single-player
        # LevelResultDialog can render it without role-aware logic.
        if self._mp_role() == "host":
            self._mp_broadcast_result(won)

        running = ui.app()
        final_squad = max(0, self.squad_count)
        gates_applied = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed = self.gate_controller.missed_total if self.gate_controller else 0
        score = levels.score_for(self.kills_total, final_squad, gates_applied, gates_missed)
        level_index = running.current_level
        level_cfg = self.level_config or levels.get_level(level_index) or levels.get_level(1)
        stars = levels.stars_for(level_cfg, won, final_squad)

        # End-of-level coin bonus: 20 for completing + 10 per star (was 50/30
        # before — kills + gates now contribute less so the shop progresses
        # at the right rate when combined with in-level coin pickups).
        # The level-complete coin bonus is a single-player progression reward
        # (it's only persisted in single-player below). Applying it in versus
        # only inflated the host's own displayed coin total *after* the result
        # was already broadcast to the client, so the two windows disagreed.
        if won and running.current_mode == "single":
            self._coins_earned += COIN_BONUS_LEVEL_COMPLETE + COIN_BONUS_PER_STAR * stars

        # Persist for single-player levels. Multiplayer never touches the save.
        if running.current_mode == "single" and level_index:
            running.state.record_result(level_index, score, stars,
                                        distance=int(self.distance))
            if self._coins_earned > 0:
                running.state.add_coins(self._coins_earned)
            # Persist leftover booster balances. No more free-grenade baseline
            # — anything the player has at level end is what they earned or
            # carried into the level.
            for bid, count in (
                ("grenade", self.grenade_count),
                ("shield", self.shield_count),
                ("reinforce", self.reinforce_count),
                ("freeze", self.freeze_count),
                ("overdrive", self.overdrive_count),
                ("magnet", self.magnet_count),
            ):
                delta = count - running.state.get_booster_balance(bid)
                if delta != 0:
                    running.state.add_booster(bid, delta)
            if won:
                running.state.unlock_up_to(level_index + 1)
                running.audio.play_sfx("level_complete")
            else:
                running.audio.play_sfx("death")
        else:
            running.audio.play_sfx("level_complete" if won else "death")

        # Show the banner immediately; dialog opens after a short pause.
        self._show_end_banner(won)
        Clock.schedule_once(
            lambda dt: self._open_result_dialog(won, stars, score, level_cfg, level_index),
            1.0,
        )

    def _show_end_banner(self, won: bool) -> None:
        """Centered, fading-in banner shown the moment the level ends."""
        from kivy.animation import Animation
        text = "VICTORY!" if won else "DEFEATED"
        color = (1.0, 0.88, 0.2, 0.0) if won else (0.95, 0.40, 0.40, 0.0)
        banner = Label(
            text=text, font_size=sp(64), bold=True, color=color,
            size_hint=(0.9, 0.3),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
        )
        self.root_layout.add_widget(banner)
        self._end_banner = banner
        target = (color[0], color[1], color[2], 1.0)
        Animation(color=target, duration=0.45, t="out_quad").start(banner)

    def _open_result_dialog(self, won: bool, stars: int, score: int,
                            level_cfg, level_index) -> None:
        # Dismiss the banner before the modal opens so we don't stack.
        if hasattr(self, "_end_banner") and self._end_banner is not None:
            if self._end_banner.parent is not None:
                self._end_banner.parent.remove_widget(self._end_banner)
            self._end_banner = None

        running = ui.app()
        next_index = (level_index + 1) if (
            level_index and level_index < levels.TOTAL_LEVELS) else None
        if won and next_index is not None:
            def go_next():
                running.start_level(next_index)
            on_next = go_next
        else:
            on_next = None

        level_label = ""
        if level_cfg:
            level_label = "World {} - {}    Level {}".format(
                level_cfg["world"],
                levels.get_world(level_cfg["world"])["name"],
                level_cfg["world_index"],
            )

        # In versus mode neither "next level" nor "retry" makes sense
        # without coordinating with the other player. Both buttons just
        # leave the match — same as the client's _mp_show_result path.
        in_versus = running.current_mode != "single"
        if in_versus:
            on_next = None
            def on_retry():
                self._exit()
            def on_menu():
                self._exit()
            # Versus has no single-player roadmap to return to.
            on_roadmap = None
            level_label = "Versus  -  {}".format(
                "You Win!" if getattr(self, "_mp_local_won", True)
                else "Opponent Wins"
            )
        else:
            def on_retry():
                if level_index:
                    running.start_level(level_index)
                else:
                    running.go("menu")

            def on_menu():
                running.go("menu")

            # Same effect as the in-level Back button: leave the level and
            # return to the world roadmap (levelselect). _exit() handles the
            # GA shutdown + routing for single-player.
            def on_roadmap():
                self._exit()

        gates_hit = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed = self.gate_controller.missed_total if self.gate_controller else 0
        squad_end = max(0, self.squad_count)
        squad_peak = max(squad_end, getattr(self, "_squad_peak", squad_end))
        stats = {
            "coins_total": self._coins_earned,
            "coins_pickup": self._coins_pickups,
            "kills": self.kills_total,
            "gates_hit": gates_hit,
            "gates_missed": gates_missed,
            "squad_end": squad_end,
            "squad_peak": squad_peak,
            "distance": int(self.distance),
            "time": self._run_time,
        }
        # In versus, _mp_broadcast_result has stashed opp_stats; pass it
        # so the host's own dialog shows the side-by-side comparison
        # too. Single-player path just leaves it None.
        dialog = ui.LevelResultDialog(
            won=won, stars=stars, score=score, level_label=level_label,
            on_next=on_next, on_retry=on_retry, on_menu=on_menu,
            on_roadmap=on_roadmap,
            stats=stats,
            opponent_stats=getattr(self, "_mp_opponent_stats", None),
            opponent_score=getattr(self, "_mp_opponent_score", None),
        )
        dialog.open()

    # --- weapon + grenade keyboard ----------------------------------------

    def _on_key(self, _window, _key, _scancode, codepoint, _modifier):
        if not codepoint:
            return False
        if codepoint == "w":
            self.current_weapon_id = weapons.next_id(self.current_weapon_id)
            self._update_weapon_range()
            self._fire_cooldown = 0.0
            ui.app().audio.play_sfx("weapon_swap")
            return True
        if codepoint in ("1", "2", "3", "4"):
            new_id = weapons.by_index(int(codepoint) - 1)
            if new_id is not None:
                self.current_weapon_id = new_id
                self._update_weapon_range()
                self._fire_cooldown = 0.0
                ui.app().audio.play_sfx("weapon_swap")
                return True
        if codepoint == "g":
            self._detonate_grenade()
            return True
        if codepoint == "s":
            self._activate_shield()
            return True
        if codepoint == "r":
            self._activate_reinforce()
            return True
        if codepoint == "f":
            self._activate_freeze()
            return True
        if codepoint == "o":
            self._activate_overdrive()
            return True
        if codepoint == "m":
            self._activate_magnet()
            return True
        return False

    def _activate_shield(self) -> None:
        if self._level_ended:
            return
        if self.shield_count <= 0:
            self._booster_unavailable("shield")
            return
        # Don't waste a shield if one is already up.
        if self.shield_active_until > self._run_time:
            return
        self.shield_count -= 1
        self.shield_active_until = self._run_time + boosters.SHIELD_DURATION_SEC
        ui.app().audio.play_sfx("shield")
        # Glowing shield bubble around the hero (prettier than a flat tint);
        # positioned + hidden in the per-frame update.
        if self.shield_aura is not None and self.hero is not None:
            self.shield_aura.center = self.hero.center
            self.shield_aura.show()
        self._float_text("SHIELD!", boosters.BOOSTERS["shield"].hud_color)
        self._add_shake(1.5)

    def _apply_reinforce_effect(self, scale: int = 1) -> None:
        """Instantly grow the squad by REINFORCE_AMOUNT * scale (no charge)."""
        if self._level_ended or self.squad_count >= MAX_SQUAD:
            return
        amount = boosters.REINFORCE_AMOUNT * max(1, int(scale))
        self.squad_count = min(MAX_SQUAD, self.squad_count + amount)
        ui.app().audio.play_sfx("reinforce")
        if self.hero is not None and self.particle_controller is not None:
            self.particle_controller.burst(
                self.hero.center_x, self.hero.center_y,
                count=20, speed=360.0, ttl=0.55, size=13.0,
                frame="runner_blue", rng=self._fire_rng,
            )
        self._float_text("+{} SQUAD!".format(amount),
                         boosters.BOOSTERS["reinforce"].hud_color)
        self._add_shake(2.0)

    def _activate_reinforce(self) -> None:
        """Burn one reinforcement kit (shop charge): instantly grow the squad."""
        if self._level_ended:
            return
        if self.reinforce_count <= 0:
            self._booster_unavailable("reinforce")
            return
        if self.squad_count >= MAX_SQUAD:
            self._booster_unavailable("reinforce", message="SQUAD FULL!")
            return
        self.reinforce_count -= 1
        self._apply_reinforce_effect(1)

    def _apply_freeze_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.freeze_active_until = boosters.refreshed_until(
            self.freeze_active_until, self._run_time,
            boosters.FREEZE_DURATION_SEC, scale)
        ui.app().audio.play_sfx("freeze")
        # Frosty pop at the hero + an icy-blue tint over the whole stage for
        # the duration (driven in the update loop) so the freeze is obvious.
        self._booster_burst(0.55, 0.85, 1.0)
        self._float_text("FREEZE!", boosters.BOOSTERS["freeze"].hud_color)
        self._add_shake(1.5)

    def _activate_freeze(self) -> None:
        if self._level_ended:
            return
        if self.freeze_count <= 0:
            self._booster_unavailable("freeze")
            return
        if self.freeze_active_until > self._run_time:
            return
        self.freeze_count -= 1
        self._apply_freeze_effect(1)

    def _apply_overdrive_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.overdrive_active_until = boosters.refreshed_until(
            self.overdrive_active_until, self._run_time,
            boosters.OVERDRIVE_DURATION_SEC, scale)
        self._fire_cooldown = 0.0    # let the surge start firing immediately
        ui.app().audio.play_sfx("overdrive")
        # Orange flare on the hero so the fire-rate surge reads visually.
        self._booster_burst(1.0, 0.55, 0.15)
        if self.hero is not None:
            self.hero.flash(duration=0.5, color=(1.0, 0.55, 0.10, 0.6))
        self._float_text("OVERDRIVE!", boosters.BOOSTERS["overdrive"].hud_color)
        self._add_shake(1.5)

    def _activate_overdrive(self) -> None:
        if self._level_ended:
            return
        if self.overdrive_count <= 0:
            self._booster_unavailable("overdrive")
            return
        if self.overdrive_active_until > self._run_time:
            return
        self.overdrive_count -= 1
        self._apply_overdrive_effect(1)

    def _apply_magnet_effect(self, scale: int = 1) -> None:
        if self._level_ended:
            return
        self.magnet_active_until = boosters.refreshed_until(
            self.magnet_active_until, self._run_time,
            boosters.MAGNET_DURATION_SEC, scale)
        ui.app().audio.play_sfx("magnet")
        # Purple pulse on the hero as the magnet switches on.
        self._booster_burst(0.80, 0.45, 0.95)
        if self.hero is not None:
            self.hero.flash(duration=0.5, color=(0.80, 0.45, 0.95, 0.6))
        self._float_text("MAGNET!", boosters.BOOSTERS["magnet"].hud_color)
        self._add_shake(1.2)

    def _activate_magnet(self) -> None:
        if self._level_ended:
            return
        if self.magnet_count <= 0:
            self._booster_unavailable("magnet")
            return
        if self.magnet_active_until > self._run_time:
            return
        self.magnet_count -= 1
        self._apply_magnet_effect(1)

    def _booster_burst(self, r: float, g: float, b: float) -> None:
        """A small celebratory particle pop at the hero for booster activation.
        (Particle frames are fixed-colour; the accompanying hero flash / stage
        tint carries the booster's hue.)"""
        if self.hero is None or self.particle_controller is None:
            return
        self.particle_controller.burst(
            self.hero.center_x, self.hero.center_y + dp(16),
            count=16, speed=360.0, ttl=0.5, size=12.0,
            frame="particle", rng=self._fire_rng,
        )

    def _float_text(self, text: str, color, cx=None, cy=None) -> None:
        """In-level pop text — same feel as the shop purchase pop: bold,
        color-coded, scale-in then rise + fade. Defaults to just above the
        hero. Added to root_layout so it floats over gameplay."""
        if cx is None:
            cx = (self.hero.center_x if self.hero is not None
                  else (self.stage.center_x if self.stage is not None else 0.0))
        if cy is None:
            cy = ((self.hero.center_y + dp(40)) if self.hero is not None
                  else (self.stage.center_y if self.stage is not None else 0.0))
        lbl = Label(
            text="[b]{}[/b]".format(text), font_size=sp(24),
            color=color, markup=True, bold=True,
            halign="center", valign="middle",
            size_hint=(None, None), size=(dp(300), dp(56)),
        )
        lbl.bind(size=lambda l, *_: setattr(l, "text_size", l.size))
        self.root_layout.add_widget(lbl)
        lbl.center = (cx, cy)
        Animation(font_size=sp(30), duration=0.14, t="out_back").start(lbl)
        rise = (Animation(y=lbl.y + dp(45), duration=0.5, t="out_quad")
                + Animation(y=lbl.y + dp(105), opacity=0,
                            duration=0.7, t="in_quad"))
        rise.bind(on_complete=lambda *_, _w=lbl: (
            _w.parent.remove_widget(_w) if _w.parent else None))
        rise.start(lbl)

    def _booster_unavailable(self, booster_id: str, message: str = None) -> None:
        """Empty-press (or can't-use) feedback: error sfx + a red pop."""
        name = boosters.BOOSTERS[booster_id].name
        ui.app().audio.play_sfx("error")
        self._float_text(message or "No {}!".format(name), (1.0, 0.45, 0.40, 1.0))

    def _sync_booster_btn(self, btn, count, base_color, active_until) -> None:
        """Refresh a booster HUD button. While a timed effect is running the
        button hides its icon and shows a large remaining-seconds countdown
        so the active timer is unmistakable; otherwise it shows the count
        (dimmed when empty)."""
        if btn is None:
            return
        if active_until is not None and active_until > self._run_time:
            btn.set_icon_visible(False)
            btn.text = "{:.1f}s".format(active_until - self._run_time)
            btn.font_size = sp(19)
            btn.valign = "middle"
            btn.color = [1, 1, 1, 1]
            btn.bg = [0.12, 0.14, 0.18, 1]    # dark so the countdown pops
            btn.disabled = False
            btn.opacity = 1.0
        else:
            btn.set_icon_visible(True)
            btn.text = "{}".format(count)
            btn.font_size = sp(14)
            btn.valign = "bottom"
            btn.disabled = count <= 0
            btn.bg = list(base_color) if count > 0 else [0.30, 0.30, 0.35, 1]
            # Empty boosters fade out so it's obvious they're unavailable —
            # StyledButton has no built-in disabled visual.
            btn.opacity = 1.0 if count > 0 else 0.4

    def _apply_grenade_effect(self, scale: int = 1) -> None:
        """Detonate a grenade (no charge): kill enemies within a scaled radius."""
        if self.hero is None or self.enemy_controller is None or self._level_ended:
            return
        scale = max(1, int(scale))
        hero_cx = self.hero.center_x
        hero_cy = self.hero.center_y
        grenade_radius = graphics.ws(GRENADE_RADIUS) * (1.0 + 0.5 * (scale - 1))
        r2 = grenade_radius * grenade_radius
        ep = self.enemy_pool
        active = ep.active
        cx = ep.cx
        cy = ep.cy
        kills = 0
        for i in range(ep.capacity):
            if not active[i]:
                continue
            dx = cx[i] - hero_cx
            dy = cy[i] - hero_cy
            if dx * dx + dy * dy <= r2:
                # Lift the existing death polish so the explosion reads consistent
                # with regular projectile kills, plus an outer ring.
                self._spawn_death_polish(cx[i], cy[i])
                ep.release(i)
                self.enemy_controller.recycled_total += 1
                kills += 1
        # Boss takes one grenade's worth of damage if it's within radius.
        if self.boss_controller is not None and self.boss is not None and self.boss.alive:
            dx = self.boss.cx - hero_cx
            dy = self.boss.cy - hero_cy
            if dx * dx + dy * dy <= r2 * 1.6 * 1.6:
                died = self.boss_controller.take_damage(20 * scale)
                if died and not self._level_ended:
                    self._end_level(won=True)
        # Big visual + audio.
        self.kills_total += kills
        if self.particle_controller is not None:
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=24, speed=440.0, ttl=0.55,
                size=14.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                hero_cx, hero_cy + dp(20),
                count=14, speed=280.0, ttl=0.70,
                size=18.0, frame="enemy_red", rng=self._fire_rng,
            )
        self._add_shake(8.0)
        ui.app().audio.play_sfx("explosion")
        self._float_text("GRENADE!", boosters.BOOSTERS["grenade"].hud_color)

    def _detonate_grenade(self) -> None:
        """Burn one grenade (shop charge) and detonate."""
        if self.hero is None or self.enemy_controller is None or self._level_ended:
            return
        if self.grenade_count <= 0:
            self._booster_unavailable("grenade")
            return
        self.grenade_count -= 1
        self._apply_grenade_effect(1)

    # --- input ------------------------------------------------------------

    def on_touch_down(self, touch):
        # Let child widgets (Back button) consume the touch first.
        if super().on_touch_down(touch):
            return True
        # Drag starts when the touch lands in the stage and a hero exists.
        if self.hero is None or not self.stage.collide_point(*touch.pos):
            return False
        # Auto-play locks out manual drag — the GA is steering. Tapping
        # the stage with auto on does nothing (use the Auto button to
        # take back control).
        if self.auto_mode:
            return False
        self._dragging = True
        self._drag_origin_touch_x = touch.x
        self._drag_origin_hero_x = self.hero.center_x
        self._hero_target_x = self.hero.center_x
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        if not self._dragging or self.hero is None or self.auto_mode:
            return False
        delta = touch.x - self._drag_origin_touch_x
        self._hero_target_x = self._drag_origin_hero_x + delta
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._dragging = False
            return True
        return super().on_touch_up(touch)

    # --- exit -------------------------------------------------------------

    def _exit(self):
        self._exit_to(None)

    def _exit_to(self, destination):
        """Leave the level. ``destination`` forces a target screen (e.g.
        "shop" from the pause menu); otherwise route by mode as usual."""
        # Cut the GA loose if we're leaving the level — it'll re-start on
        # the next _reset if auto_mode is still on.
        if self.auto is not None:
            self.auto.stop()
        running = ui.app()
        if running.mp_net is not None:
            try:
                running.mp_net.send_leave()
            except Exception:
                pass
            running.mp_net.stop()
            running.mp_net = None
            running.go("multiplayer")
            return
        if destination:
            running.go(destination)
        elif running.current_mode == "single":
            running.go("levelselect")
        else:
            running.go("menu")

    # --- multiplayer (M13) ----------------------------------------------

    def _mp_role(self) -> str:
        """Returns "host", "client", or "single" — drives the role-aware
        branches in ``_update`` and decides who simulates the world.
        """
        running = ui.app()
        if running.mp_net is None or running.current_mode == "single":
            return "single"
        return "host" if isinstance(running.mp_net, net.NetHost) else "client"

    def _mp_drain_host_inbox(self) -> None:
        """Host side: pull pending input messages from the client and
        update ``opponent_target_x``. Also handle disconnect / leave.
        """
        running = ui.app()
        if running.mp_net is None:
            return
        while True:
            try:
                msg = running.mp_net.inbox.get_nowait()
            except Exception:
                break
            kind = msg.get("t")
            if kind == "input":
                # Client's input is a normalized lateral fraction; convert
                # back to stage-pixel coordinates so it can drive
                # opponent_hero directly.
                tx = float(msg.get("tx", 0.5))
                sx = self.stage.x
                sw = self.stage.width
                self.opponent_target_x = sx + max(0.0, min(1.0, tx)) * sw
            elif kind == "weapon":
                # Client told us which weapon they equipped from their
                # own shop. Validate against the registry before applying.
                w = str(msg.get("weapon", ""))
                if weapons.get(w) is not None:
                    self.opponent_weapon_id = w
            elif kind in ("leave", "_disconnected"):
                # Peer left — fall back to solo so the host can still finish
                # the level. Same shape as _exit's mp_net cleanup.
                running.mp_net.stop()
                running.mp_net = None
                running.current_mode = "single"
                return

    def _mp_send_snapshot(self) -> None:
        """Host side: build + send the per-tick snapshot.

        Schema includes hero positions, per-player stats, distance,
        AND the live entity arrays (gates + enemies) so the client can
        render a populated world. Positions normalised to stage frac
        in [0, 1] so the client doesn't need to know stage geometry.
        Field names are single-letter where possible to keep JSON small.
        """
        running = ui.app()
        if running.mp_net is None or self.hero is None:
            return
        sx = self.stage.x
        sy = self.stage.y
        sw = max(1.0, self.stage.width)
        sh = max(1.0, self.stage.height)
        p1_norm_x = (self.hero.center_x - sx) / sw
        if self.opponent_hero is not None:
            p2_norm_x = (self.opponent_hero.center_x - sx) / sw
        else:
            p2_norm_x = 0.5

        # Live gate pairs. Each pair includes BOTH players' consumed +
        # selected flags so the client can render the gate visual from
        # *its own* perspective (p2). Without per-player flags the
        # client always sees the host's consumed/selected dimming even
        # for gates the client hasn't actually picked yet — that was
        # the "gates only applied to the host" bug.
        gate_pairs = []
        if self.gate_controller is not None:
            for pair in self.gate_controller.pairs:
                left, right = sorted(pair, key=lambda g: g.x)
                y_frac = (left.y - sy) / sh
                gate_pairs.append([
                    round(y_frac, 4),
                    round((left.x - sx) / sw, 4),
                    round(left.width / sw, 4),
                    round(left.height / sh, 4),
                    left.op,
                    left.value,
                    left.label_text,
                    1 if left.consumed else 0,           # c1
                    1 if left.selected else 0,           # s1
                    1 if left.consumed_by_p2 else 0,     # c2
                    1 if left.selected_by_p2 else 0,     # s2
                    round((right.x - sx) / sw, 4),
                    round(right.width / sw, 4),
                    round(right.height / sh, 4),
                    right.op,
                    right.value,
                    right.label_text,
                    1 if right.consumed else 0,
                    1 if right.selected else 0,
                    1 if right.consumed_by_p2 else 0,
                    1 if right.selected_by_p2 else 0,
                ])

        # Live enemies. Compact: [x_frac, y_frac, type_int].
        enemies = []
        if self.enemy_pool is not None:
            pool = self.enemy_pool
            for i in range(pool.capacity):
                if pool.active[i]:
                    enemies.append([
                        round((pool.cx[i] - sx) / sw, 4),
                        round((pool.cy[i] - sy) / sh, 4),
                        int(self.enemy_controller.type[i])
                        if hasattr(self.enemy_controller, "type") else 0,
                    ])

        # Live projectiles. Each row also carries the owner byte so the
        # client can paint them red vs neutral — the player can read
        # whose shots are whose at a glance.
        projectiles = []
        if self.projectile_pool is not None:
            pool = self.projectile_pool
            owner = self.projectile_controller.owner
            for i in range(pool.capacity):
                if pool.active[i]:
                    projectiles.append([
                        round((pool.cx[i] - sx) / sw, 4),
                        round((pool.cy[i] - sy) / sh, 4),
                        int(owner[i]),
                    ])

        # Live squad followers for both heroes. Each player's view
        # needs to see the OTHER player's crowd, and their own crowd
        # gets driven from the (synced) squad counts. The host's
        # SquadController already laid them out in formation — we just
        # snapshot the positions.
        sq_p1 = []
        if self.squad_pool is not None:
            pool = self.squad_pool
            for i in range(pool.capacity):
                if pool.active[i]:
                    sq_p1.append([
                        round((pool.cx[i] - sx) / sw, 4),
                        round((pool.cy[i] - sy) / sh, 4),
                    ])
        sq_p2 = []
        if self.opponent_squad_pool is not None:
            pool = self.opponent_squad_pool
            for i in range(pool.capacity):
                if pool.active[i]:
                    sq_p2.append([
                        round((pool.cx[i] - sx) / sw, 4),
                        round((pool.cy[i] - sy) / sh, 4),
                    ])

        # Live coin / double-coin pickups, FILTERED to those the client
        # hasn't collected yet. Their own ``consumed_by_p2`` flag hides
        # collected pickups from their view while the host can still
        # see (and the slot can still scroll off) their own copy.
        pickups = []
        if self.pickup_pool is not None:
            pool = self.pickup_pool
            ptype = self.pickup_controller.type
            cp2 = self.pickup_controller.consumed_by_p2
            for i in range(pool.capacity):
                if pool.active[i] and not cp2[i]:
                    pickups.append([
                        round((pool.cx[i] - sx) / sw, 4),
                        round((pool.cy[i] - sy) / sh, 4),
                        int(ptype[i]),
                    ])

        running.mp_net.send({
            "t": "snap",
            "tick": self._mp_tick,
            "p1": {
                "x":     round(p1_norm_x, 4),
                "squad": self.squad_count,
                "kills": self.kills_total,
                "coins": self._coins_earned,
                "alive": self.squad_count > 0 and not self._level_ended,
            },
            "p2": {
                "x":     round(p2_norm_x, 4),
                "squad": self.opponent_squad,
                "kills": self.opponent_kills,
                "coins": self.opponent_coins,
                "cpk":   self.opponent_coins_pickups,
                "alive": self.opponent_alive,
            },
            "dist":  round(self.distance, 1),
            "g":     gate_pairs,
            "e":     enemies,
            "pr":    projectiles,
            "pk":    pickups,
            "sq1":   sq_p1,    # host's squad
            "sq2":   sq_p2,    # client's squad
            "ended": self._level_ended,
        })

    def _mp_client_tick(self, dt: float) -> None:
        """Client side: drain snapshots, position both heroes from the
        latest one, send local input to the host.

        The local simulation is skipped entirely — controllers don't
        tick, spawners don't fire, no attrition runs. The client is a
        dumb viewport plus an input forwarder.
        """
        running = ui.app()
        if running.mp_net is None:
            return
        latest = None
        while True:
            try:
                msg = running.mp_net.inbox.get_nowait()
            except Exception:
                break
            kind = msg.get("t")
            if kind == "snap":
                latest = msg
            elif kind == "result":
                # Host declared a winner — show the match-over dialog.
                self._mp_show_result(msg)
                return
            elif kind in ("leave", "_disconnected"):
                self._exit()
                return

        if latest is not None:
            self._mp_apply_snapshot(latest)
            # Mesh-batched renderers rebuild their vertex buffers from
            # pool state, and that rebuild only ever runs from inside
            # the host's _update body — which the client skips. Drive
            # the rebuilds here so client-side enemies and projectiles
            # actually appear on screen.
            if self.enemy_renderer is not None:
                self.enemy_renderer.rebuild()
            if self.projectile_renderer is not None:
                self.projectile_renderer.rebuild()
            if self.opponent_projectile_renderer is not None:
                self.opponent_projectile_renderer.rebuild()
            if self.pickup_renderer is not None:
                self.pickup_renderer.rebuild()
            if self.squad_renderer is not None:
                self.squad_renderer.rebuild()
            if self.opponent_squad_renderer is not None:
                self.opponent_squad_renderer.rebuild()

        # Drive the local centerline-stripe scroll so the world feels
        # alive on the client too — host's distance is authoritative,
        # we just step the stripes by the elapsed dt.
        sx_s, sy_s = self.stage.pos
        sw_s, sh_s = self.stage.size
        if sh_s > 0:
            drop = graphics.ws(SCROLL_SPEED_PX_PER_SEC) * dt
            for i in range(len(self._stripe_ys)):
                self._stripe_ys[i] -= drop
                while self._stripe_ys[i] < sy_s:
                    self._stripe_ys[i] += sh_s
            self._paint_stripes()

        # Sync chips + progress bar from snapshot-driven state.
        self._dist_progress = self._level_progress()
        self._sync_dist_bar()
        if self.squad_chip is not None:
            self.squad_chip.set_value(str(self.squad_count))
            self.kills_chip.set_value(str(self.kills_total))
            other = self._coins_earned - self._coins_pickups
            self.coins_chip.set_value("+{}+{}".format(
                self._coins_pickups, other,
            ))
            # Weapon chip on the client: shows the *client's* own
            # equipped weapon + tier. Host's stat is mirrored only for
            # squad / kills / coins; the weapon a player uses is local
            # info, not part of the snapshot.
            weapon_name = weapons.get(self.current_weapon_id).name
            running_app = ui.app()
            tier = (running_app.state.get_weapon_tier(self.current_weapon_id)
                    if running_app and running_app.state else 1)
            tier = max(1, min(4, tier))
            pips = "*" * tier + "." * (4 - tier)
            tier = max(1, min(4, tier))
            self.weapon_chip.set_value(
                "{} [{}/4]".format(weapon_name, tier))

        # First-tick handshake: tell the host which weapon the client
        # equipped from their own shop. Host uses it as the opponent's
        # starting weapon (without this, opponent always defaults to
        # "pistol" no matter what the client picked).
        if not self._mp_weapon_sent:
            running.mp_net.send({
                "t": "weapon",
                "weapon": self.current_weapon_id,
            })
            self._mp_weapon_sent = True

        # Forward local input to the host. Throttle to once per tick max
        # and only on meaningful change — keeps the channel quiet.
        if self.hero is not None and self.stage.width > 0:
            sx = self.stage.x
            sw = max(1.0, self.stage.width)
            target_norm = (self._hero_target_x - sx) / sw
            target_norm = max(0.0, min(1.0, target_norm))
            if (self._last_input_norm_x is None
                    or abs(target_norm - self._last_input_norm_x) > 0.002):
                running.mp_net.send_input(target_norm, 0.0, False)
                self._last_input_norm_x = target_norm

    def _mp_apply_snapshot(self, snap: dict) -> None:
        """Client side: position both heroes + replicate stats + rebuild
        the visible entities (gates, enemies) from the host's snapshot.

        On the client: self.hero IS p2 (locally controlled); self.opponent_hero
        is p1 (the host's hero, ghosted at 70 % opacity).
        """
        sx = self.stage.x
        sy = self.stage.y
        sw = max(1.0, self.stage.width)
        sh = max(1.0, self.stage.height)
        # --- heroes ---------------------------------------------------
        p1 = snap.get("p1", {})
        p2 = snap.get("p2", {})
        # Compute the hero Y the same way the host's _update does. The
        # client's local loop never runs, so the previous version of
        # this code left hero.y at 0 and the heroes rendered at the
        # very bottom edge of the stage — that's the "player misplaced"
        # bug. Now we drive Y from the host's distance (so the bob
        # matches what the host sees too).
        bob = math.sin(self.distance / 22.0) * 5.0
        hero_y = sy + sh * HERO_BOTTOM_FRAC + bob
        if self.opponent_hero is not None:
            self.opponent_hero.center_x = sx + float(p1.get("x", 0.5)) * sw
            self.opponent_hero.y = hero_y
            if self.opponent_marker is not None:
                self.opponent_marker.center_x = self.opponent_hero.center_x
                self.opponent_marker.y = self.opponent_hero.y - dp(2)
        if self.hero is not None:
            self.hero.center_x = sx + float(p2.get("x", 0.5)) * sw
            self.hero.y = hero_y
            if self.hero_marker is not None:
                self.hero_marker.center_x = self.hero.center_x
                self.hero_marker.y = self.hero.y - dp(2)
        # --- stats ---------------------------------------------------
        self.squad_count    = int(p2.get("squad", self.squad_count))
        self.kills_total    = int(p2.get("kills", self.kills_total))
        self._coins_earned  = int(p2.get("coins", self._coins_earned))
        # Ground-coin pop for the client's own player: the host sends p2's
        # ground-pickup running total ("cpk"); any increase = a coin the
        # client just grabbed → pop "+N" at the client's hero.
        cpk = int(p2.get("cpk", self._mp_prev_coin_pickup))
        if cpk > self._mp_prev_coin_pickup and self.hero is not None:
            self._float_text("+{}".format(cpk - self._mp_prev_coin_pickup),
                             (1.0, 0.90, 0.30, 1.0))
        self._mp_prev_coin_pickup = cpk
        self.opponent_squad = int(p1.get("squad", self.opponent_squad))
        self.opponent_kills = int(p1.get("kills", self.opponent_kills))
        self.opponent_coins = int(p1.get("coins", self.opponent_coins))
        self.opponent_alive = bool(p1.get("alive", True))
        self.distance       = float(snap.get("dist", self.distance))
        # --- gates ----------------------------------------------------
        # Cheapest correct approach: rebuild the gate widgets from the
        # snapshot each tick. 20 Hz × <10 gates is well below any
        # render-cost threshold and avoids tracking gate IDs across
        # the network.
        if self.gate_controller is not None:
            self._mp_rebuild_gates(snap.get("g", []), sx, sy, sw, sh)
        # --- enemies --------------------------------------------------
        # Drop straight into the pool's parallel arrays so the existing
        # BatchedRenderer picks them up on its next vertex rebuild.
        if self.enemy_pool is not None:
            self._mp_apply_enemies(snap.get("e", []), sx, sy, sw, sh)
        # --- projectiles ---------------------------------------------
        if self.projectile_pool is not None:
            self._mp_apply_projectiles(snap.get("pr", []), sx, sy, sw, sh)
        # --- pickups -------------------------------------------------
        if self.pickup_pool is not None:
            self._mp_apply_pickups(snap.get("pk", []), sx, sy, sw, sh)
        # --- squad followers ------------------------------------------
        # On the client: own squad = sq_p2 (client controls p2),
        # opponent squad = sq_p1 (host's hero). Each goes into its
        # respective pool so the local renderer shows blue and the
        # opponent renderer shows red.
        if self.squad_pool is not None:
            self._mp_apply_squad(self.squad_pool,
                                 snap.get("sq2", []), sx, sy, sw, sh)
        if self.opponent_squad_pool is not None:
            self._mp_apply_squad(self.opponent_squad_pool,
                                 snap.get("sq1", []), sx, sy, sw, sh)

    def _mp_rebuild_gates(self, pairs_snap: list, sx: float, sy: float,
                          sw: float, sh: float) -> None:
        """Sync the client's gate widgets to match the host's pairs.

        Clears existing widgets and rebuilds — simpler than diffing,
        and the pair count is small enough that the cost is negligible.
        """
        gc = self.gate_controller
        for pair in gc.pairs:
            for g in pair:
                if g.parent:
                    g.parent.remove_widget(g)
        gc.pairs = []
        for entry in pairs_snap:
            try:
                (y_frac,
                 lx, lw, lh, lop, lval, llabel,
                 lc1, ls1, lc2, ls2,
                 rx, rw, rh, rop, rval, rlabel,
                 rc1, rs1, rc2, rs2) = entry
            except (ValueError, TypeError):
                continue
            y_px = sy + y_frac * sh
            left = gates.Gate(
                lop, lval, llabel,
                size_hint=(None, None),
                size=(lw * sw, lh * sh),
                pos=(sx + lx * sw, y_px),
            )
            right = gates.Gate(
                rop, rval, rlabel,
                size_hint=(None, None),
                size=(rw * sw, rh * sh),
                pos=(sx + rx * sw, y_px),
            )
            # Client renders using p2 flags — host's picks don't dim
            # the client's view, so the player's own gate state stays
            # readable.
            if lc2:
                if ls2: left.mark_selected()
                else:   left.mark_consumed(dim=True)
            if rc2:
                if rs2: right.mark_selected()
                else:   right.mark_consumed(dim=True)
            gc.stage.add_widget(left)
            gc.stage.add_widget(right)
            gc.pairs.append([left, right])

    def _mp_apply_enemies(self, enemies_snap: list, sx: float, sy: float,
                          sw: float, sh: float) -> None:
        """Push host enemy positions into the local pool. We bypass
        EnemySpawner / EnemyController entirely on the client — those
        are sim-side; we just need the pool's parallel arrays populated
        so BatchedRenderer can draw them."""
        pool = self.enemy_pool
        # Zero everything first, then activate the slots we need.
        for i in range(pool.capacity):
            if pool.active[i]:
                pool.active[i] = 0
        pool.active_count = 0
        # Type → atlas frame map for the renderer's UV pickup.
        frame_for_type = {
            entities.TYPE_GRUNT:    "enemy_red",
            entities.TYPE_SWARMER:  "enemy_red",
            entities.TYPE_TANK:     "enemy_red",
            entities.TYPE_BOMBER:   "enemy_red",
            entities.TYPE_SPLITTER: "enemy_red",
        }
        for i, entry in enumerate(enemies_snap):
            if i >= pool.capacity:
                break
            try:
                x_frac, y_frac, type_int = entry
            except (ValueError, TypeError):
                continue
            frame_name = frame_for_type.get(int(type_int), "enemy_red")
            pool.spawn(sx + x_frac * sw, sy + y_frac * sh,
                       0.0, 0.0, 40.0, 40.0, frame_name)

    def _mp_apply_projectiles(self, projectiles_snap: list,
                              sx: float, sy: float,
                              sw: float, sh: float) -> None:
        """Same shape as _mp_apply_enemies — zero the pool, repopulate
        from the snapshot. Each entry is [x_frac, y_frac, owner_byte]
        so the local + opponent renderers can split rendering by owner.
        Backwards-tolerant: rows without owner are treated as local.
        """
        pool = self.projectile_pool
        ctrl = self.projectile_controller
        for i in range(pool.capacity):
            if pool.active[i]:
                pool.active[i] = 0
        pool.active_count = 0
        for i, entry in enumerate(projectiles_snap):
            if i >= pool.capacity:
                break
            try:
                if len(entry) >= 3:
                    x_frac, y_frac, owner_byte = entry[0], entry[1], int(entry[2])
                else:
                    x_frac, y_frac, owner_byte = entry[0], entry[1], 0
            except (ValueError, TypeError, IndexError):
                continue
            idx = pool.spawn(sx + x_frac * sw, sy + y_frac * sh,
                             0.0, 0.0, 14.0, 22.0, "projectile")
            if idx >= 0:
                ctrl.owner[idx] = owner_byte

    def _mp_apply_squad(self, pool, positions_snap: list,
                        sx: float, sy: float,
                        sw: float, sh: float) -> None:
        """Drop the host's squad-position list into the given pool. Used
        for both ``self.squad_pool`` (local crowd) and
        ``self.opponent_squad_pool`` (other player's crowd) on the
        client side — each rendered with its own renderer/tint."""
        for i in range(pool.capacity):
            if pool.active[i]:
                pool.active[i] = 0
        pool.active_count = 0
        for i, entry in enumerate(positions_snap):
            if i >= pool.capacity:
                break
            try:
                x_frac, y_frac = entry[0], entry[1]
            except (ValueError, TypeError, IndexError):
                continue
            pool.spawn(sx + x_frac * sw, sy + y_frac * sh,
                       0.0, 0.0,
                       entities.SquadController.RUNNER_W,
                       entities.SquadController.RUNNER_H,
                       entities.SquadController.FRAME_NAME)

    def _mp_apply_pickups(self, pickups_snap: list,
                          sx: float, sy: float,
                          sw: float, sh: float) -> None:
        """Replicate host pickup positions into the local pickup pool
        so the BatchedRenderer draws coin items on the client. Frame
        choice mirrors PickupController.spawn: COIN -> coin, DOUBLE_COIN
        -> particle. Type byte preserved for visual consistency."""
        pool = self.pickup_pool
        ctrl = self.pickup_controller
        for i in range(pool.capacity):
            if pool.active[i]:
                pool.active[i] = 0
        pool.active_count = 0
        for i, entry in enumerate(pickups_snap):
            if i >= pool.capacity:
                break
            try:
                x_frac, y_frac, ptype = entry[0], entry[1], int(entry[2])
            except (ValueError, TypeError, IndexError):
                continue
            # M14 — dedicated coin / double_coin frames.
            frame = ("coin" if ptype == entities.PICKUP_COIN
                     else "double_coin")
            size = (entities.PickupSpawner.COIN_SIZE
                    if ptype == entities.PICKUP_COIN
                    else entities.PickupSpawner.DOUBLE_SIZE)
            idx = pool.spawn(sx + x_frac * sw, sy + y_frac * sh,
                             0.0, 0.0, size, size, frame)
            if idx >= 0:
                ctrl.type[idx] = ptype

    def _mp_broadcast_result(self, host_completed_won: bool) -> None:
        """Host side: compute scores for both players, declare the winner
        by higher score, and send each side its own framed result message.

        Scoring for now reuses the single-player formula — kills + squad
        survival + gates. p2 doesn't currently earn gates (no client-side
        gate sim yet), so they score only on kills + squad. Replace this
        with a fair shared formula once shared-world entity sync lands.
        """
        running = ui.app()
        if running.mp_net is None:
            return
        gates_hit_p1 = self.gate_controller.applied_total if self.gate_controller else 0
        gates_missed_p1 = self.gate_controller.missed_total if self.gate_controller else 0
        p1_score = levels.score_for(
            self.kills_total, max(0, self.squad_count),
            gates_hit_p1, gates_missed_p1,
        )
        p2_score = levels.score_for(
            self.opponent_kills, max(0, self.opponent_squad),
            self._opponent_gates_hit, self._opponent_gates_missed,
        )
        # Build both stat dicts so each side can render the side-by-side
        # comparison panel in LevelResultDialog.
        host_stats = {
            "coins_total": self._coins_earned,
            "coins_pickup": self._coins_pickups,
            "kills":        self.kills_total,
            "gates_hit":    gates_hit_p1,
            "gates_missed": gates_missed_p1,
            "squad_end":    max(0, self.squad_count),
            "squad_peak":   max(0, self._squad_peak),
            "distance":     int(self.distance),
            "time":         self._run_time,
        }
        opp_stats = {
            "coins_total": self.opponent_coins,
            "coins_pickup": 0,
            "kills":        self.opponent_kills,
            "gates_hit":    self._opponent_gates_hit,
            "gates_missed": self._opponent_gates_missed,
            "squad_end":    max(0, self.opponent_squad),
            "squad_peak":   max(0, self._opponent_squad_peak),
            "distance":     int(self.distance),
            "time":         self._run_time,
        }
        # Send each side its perspective: their score, their stats,
        # opponent's stats. Client renders identical comparison panel.
        running.mp_net.send({
            "t":              "result",
            "local_won":      p2_score > p1_score,
            "local_score":    p2_score,
            "opponent_score": p1_score,     # client's opponent = host
            "local_stats":    opp_stats,    # client's own = host's opponent
            "opponent_stats": host_stats,
        })
        self._mp_local_won = p1_score >= p2_score
        self._mp_opponent_stats = opp_stats
        self._mp_opponent_score = p2_score   # host's opponent = client

    def _mp_show_result(self, msg: dict) -> None:
        """Both sides: the host has declared the match over. Render the
        existing LevelResultDialog with vs scores so the screen flow
        matches single-player level end.
        """
        won = bool(msg.get("local_won", False))
        score = int(msg.get("local_score", 0))
        opponent_score = int(msg.get("opponent_score", 0))
        self._level_ended = True
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None
        # The host packs both stat dicts into the result message so the
        # client renders the same side-by-side YOU/OPP panel.
        local_stats = msg.get("local_stats") or {
            "coins_total": self._coins_earned,
            "coins_pickup": self._coins_pickups,
            "kills":        self.kills_total,
            "gates_hit":    0, "gates_missed": 0,
            "squad_end":    max(0, self.squad_count),
            "squad_peak":   max(0, self._squad_peak),
            "distance":     int(self.distance),
            "time":         self._run_time,
        }
        opponent_stats = msg.get("opponent_stats")
        dialog = ui.LevelResultDialog(
            won=won, stars=0, score=score,
            level_label="Versus  -  {}".format(
                "You Win!" if won else "Opponent Wins"),
            on_next=None, on_retry=self._exit, on_menu=self._exit,
            stats=local_stats,
            opponent_stats=opponent_stats,
            opponent_score=opponent_score,
        )
        dialog.open()

    # --- opponent auto-fire + gate handling (versus only, host) ---------

    def _opponent_tick_versus(self, dt: float) -> None:
        """Host-side: drive the opponent's auto-fire + gate consumption.

        Called from ``_update`` only when role == "host", opponent_hero
        exists, and opponent is still alive. Fires from the opponent's
        muzzle at the nearest enemy (owner=1 so kills route to
        opponent_kills via _on_kill), and walks the live gate pairs to
        apply any the opponent has reached.
        """
        if (self.opponent_hero is None or not self.opponent_alive
                or self.enemy_controller is None
                or self.projectile_controller is None):
            return

        # --- auto-fire ---------------------------------------------------
        # Firepower now scales with opponent_squad — opponent fires
        # min(squad, MAX_SHOOTERS_PER_SHOT) projectiles, simulating the
        # squad's combined volley. Earlier the opponent always shot a
        # single bullet regardless of their squad count, which made
        # +N/×N gate picks feel useless on the opponent's side.
        weapon = weapons.get(self.opponent_weapon_id)
        self._opponent_fire_cooldown -= dt
        if self._opponent_fire_cooldown <= 0.0:
            target = entities.find_nearest_enemy(
                self.opponent_hero.center_x, self.opponent_hero.center_y,
                self.enemy_controller,
            )
            if target >= 0:
                ep = self.enemy_pool
                target_x = ep.cx[target]
                target_y = ep.cy[target]
                # Build a fan of shooter positions around the opponent
                # hero — opponent's squad followers aren't rendered, but
                # their fire contribution still counts.
                n = max(1, min(self.opponent_squad, MAX_SHOOTERS_PER_SHOT))
                positions = []
                muzzle_off = graphics.ws(MUZZLE_OFFSET_Y)
                fan_step = graphics.ws(14.0)
                for i in range(n):
                    offset = (i - (n - 1) / 2.0) * fan_step
                    positions.append((
                        self.opponent_hero.center_x + offset,
                        self.opponent_hero.center_y + muzzle_off,
                    ))
                entities.fire_from_positions(
                    positions, target_x, target_y, weapon,
                    self.projectile_controller, self._fire_rng,
                    owner=1,
                )
            self._opponent_fire_cooldown = 1.0 / weapon.fire_rate

        # --- gate pass-through ------------------------------------------
        if self.gate_controller is None:
            return
        op_cx = self.opponent_hero.center_x
        op_cy = self.opponent_hero.center_y
        for pair in self.gate_controller.pairs:
            # Per-player flag — host's `consumed` doesn't affect opponent.
            if any(g.consumed_by_p2 for g in pair):
                continue
            pair_line_y = pair[0].y + pair[0].height * 0.5
            if pair_line_y > op_cy + pair[0].height * 0.25:
                continue
            picked = None
            for g in pair:
                if g.x <= op_cx <= g.x + g.width:
                    picked = g
                    break
            if picked is not None:
                picked.selected_by_p2 = True
                self._apply_gate_effect_to_opponent(picked)
                self._opponent_gates_hit += 1
            else:
                self._opponent_gates_missed += 1
            for g in pair:
                g.consumed_by_p2 = True
            # Track opponent's squad peak for the end-of-level summary.
            if self.opponent_squad > self._opponent_squad_peak:
                self._opponent_squad_peak = self.opponent_squad

    def _apply_gate_effect_to_opponent(self, gate) -> None:
        """Mirror of _on_apply_gate but writes to opponent state.

        Covers all gate ops: MUL / ADD / SUB / DIV change opponent_squad;
        WEAPON sets opponent_weapon_id (their auto-fire picks it up next
        tick); GRENADE bumps opponent_grenade_count (currently a stats
        counter — opponent has no manual throw, but the count is in the
        snapshot in case future logic wants to auto-throw).
        """
        if gate.op == gates.OP_WEAPON:
            new_weapon = str(gate.value)
            if weapons.get(new_weapon) is not None:
                self.opponent_weapon_id = new_weapon
            return
        if gate.op == gates.OP_GRENADE:
            try:
                self.opponent_grenade_count += int(gate.value)
            except (TypeError, ValueError):
                self.opponent_grenade_count += 1
            return
        try:
            v = int(gate.value)
        except (TypeError, ValueError):
            v = 0
        if gate.op == gates.OP_MUL:
            self.opponent_squad = min(MAX_SQUAD, max(1, self.opponent_squad * v))
        elif gate.op == gates.OP_ADD:
            self.opponent_squad = min(MAX_SQUAD, self.opponent_squad + v)
        elif gate.op == gates.OP_SUB:
            self.opponent_squad = max(0, self.opponent_squad - v)
        elif gate.op == gates.OP_DIV:
            self.opponent_squad = max(0, self.opponent_squad // max(1, v))
        if self.opponent_squad <= 0:
            self.opponent_alive = False

    # --- opponent pickup-collection handler (versus only) ----------------

    def _on_opponent_pickup_collect(self, ptype: int,
                                    x: float, y: float) -> None:
        """Mirror of _on_pickup_collect for the opponent. COIN pickups
        credit opponent_coins (doubled while opponent_double_coin_until
        is in the future); DOUBLE_COIN pickups extend that timer."""
        if ptype == entities.PICKUP_COIN:
            coins = entities.PickupController.COIN_PER_PICKUP
            if self.opponent_double_coin_until > self._run_time:
                coins *= 2
            self.opponent_coins += coins
            # Ground-coin tally for p2 so the client device can pop its own
            # "+N" (the snapshot's total mixes in progress coins).
            self.opponent_coins_pickups += coins
        else:    # PICKUP_DOUBLE_COIN
            duration = entities.PickupController.DOUBLE_COIN_DURATION_SEC
            self.opponent_double_coin_until = self._run_time + duration

    # --- opponent squad-loss handler (versus only, host side) ------------

    def _on_opponent_squad_loss(self, hit_x: float, hit_y: float) -> None:
        """Versus only: an enemy reached the opponent's front line.

        Mirrors _on_squad_loss but writes to opponent_squad instead of
        squad_count, and never ends the level (only the LOCAL player's
        death does that — opponent's loss is opponent's problem and
        will be reflected in their snapshot).
        """
        if self._level_ended or self.opponent_squad <= 0:
            return
        self.opponent_squad -= 1
        if self.particle_controller is not None:
            self.particle_controller.burst(
                hit_x, hit_y, count=6, speed=240.0, ttl=0.4,
                size=10.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                hit_x, hit_y, count=6, speed=180.0, ttl=0.55,
                size=14.0, frame="enemy_red", rng=self._fire_rng,
            )
        if self.opponent_squad <= 0:
            self.opponent_alive = False

    # --- squad-loss handler (shared by attrition and escape) -------------

    def _on_squad_loss(self, hit_x: float, hit_y: float) -> None:
        """One squad runner is removed. Shared by two paths:

        1. ``resolve_squad_attrition`` — an enemy reached the front line
           while in the lateral contact zone.
        2. ``EnemyController.update``'s ``on_escape`` — an enemy slipped
           past the squad off the bottom of the play area.

        Without (2), enemies that traveled down a column far from the
        hero just left the screen for free — the player could dodge
        sideways and the level couldn't fail. Now an escape is treated
        identically to a direct hit: shield blocks it, otherwise the
        squad loses one, sparks + body-fragment burst spawn, hero
        flashes, and squad=0 ends the level.
        """
        if self._level_ended or self.squad_count <= 0:
            return
        # Shield (or Freeze) blocks the loss; the enemy is still consumed (it
        # bounced off the defense) so the player still benefits.
        if (self.shield_active_until > self._run_time
                or self.freeze_active_until > self._run_time):
            if self.particle_controller is not None:
                self.particle_controller.burst(
                    hit_x, hit_y, count=8, speed=300.0, ttl=0.30,
                    size=12.0, frame="particle", rng=self._fire_rng,
                )
            self._add_shake(0.6)
            return
        self.squad_count -= 1
        self.attrition_total += 1
        if self.particle_controller is not None:
            self.particle_controller.burst(
                hit_x, hit_y, count=6, speed=240.0, ttl=0.4,
                size=10.0, frame="particle", rng=self._fire_rng,
            )
            self.particle_controller.burst(
                hit_x, hit_y, count=6, speed=180.0, ttl=0.55,
                size=14.0, frame="enemy_red", rng=self._fire_rng,
            )
        if self.hero is not None:
            self.hero.flash(duration=0.30, color=(1.0, 0.25, 0.25, 0.78))
        self._add_shake(2.5 if self.squad_count > 0 else 9.0)
        ui.app().audio.play_sfx("damage")
        if self.squad_count <= 0:
            self._end_level(won=False)

    # --- HUD sync helpers ------------------------------------------------

    def _sync_top_bar(self) -> None:
        if self._top_bar_rect is None:
            return
        self._top_bar_rect.pos = self.top_bar.pos
        self._top_bar_rect.size = self.top_bar.size

    def _apply_stats_visibility(self) -> None:
        """Show/hide the top statistics HUD per the Settings toggle (off by
        default so the band never covers gameplay / the boss). The toggle
        governs ONLY the statistics — the dark band, title, and stat chips.
        The level-progress bar and the booster HUD are separate and always
        stay visible (the progress bar is pinned to the very top of the
        screen, outside this band)."""
        running = ui.app()
        show = bool(running.state.get_setting("show_stats")) \
            if (running and running.state) else False
        # Only opacity is toggled (no `disabled`): these hold Labels that
        # never grab touches, so a hidden band must not swallow the drag that
        # steers the squad.
        if self.top_bar is not None:
            self.top_bar.opacity = 1.0 if show else 0.0
        if self.chip_row is not None:
            self.chip_row.opacity = 1.0 if show else 0.0

    def _apply_debug_visibility(self) -> None:
        """Show/hide the FPS / debug overlay (FPS, frame ms, entity counts)
        per the Settings toggle. Off by default; independent of show_stats."""
        running = ui.app()
        show = bool(running.state.get_setting("show_debug")) \
            if (running and running.state) else False
        if self.debug is not None:
            self.debug.opacity = 1.0 if show else 0.0

    def _apply_top_safe_inset(self) -> None:
        """Shift the top-center HUD (progress bar + 2x-coins timer) down by the
        player's safe-area inset so a notch / dynamic island doesn't cover them.
        The stats top bar is intentionally left at the very top."""
        running = ui.app()
        inset = running.state.get_setting("top_safe_inset") \
            if (running and running.state) else 0.0
        try:
            inset = float(inset)
        except (TypeError, ValueError):
            inset = 0.0
        inset = max(0.0, min(TOP_SAFE_INSET_MAX, inset))
        if self.dist_bar_holder is not None:
            ph = dict(self.dist_bar_holder.pos_hint)
            ph["top"] = DIST_BAR_TOP - inset
            self.dist_bar_holder.pos_hint = ph
        if self.dc_panel is not None:
            ph = dict(self.dc_panel.pos_hint)
            ph["top"] = DC_PANEL_TOP - inset
            self.dc_panel.pos_hint = ph

    def _level_progress(self) -> float:
        """Fraction of the level completed (0..1), for the top progress bar.

        On boss levels the objective is to deplete the boss, so progress is
        the damage dealt (`1 - hp/max_hp`); the guard on ``self.boss`` also
        covers the multiplayer client, which holds a synced ``Boss`` while a
        boss is active. Otherwise it is forward distance toward the goal.
        """
        if self.boss is not None and self.boss.max_hp > 0:
            return max(0.0, min(1.0, 1.0 - self.boss.hp / self.boss.max_hp))
        if self.distance_goal > 0:
            return min(1.0, self.distance / self.distance_goal)
        return 0.0

    def _sync_dist_bar(self) -> None:
        """Position the level-progress bar (the fill grows in place as the
        progress value advances, or when the holder is resized)."""
        if self._dist_bg_rect is None:
            return
        x, y = self.dist_bar_holder.pos
        w, h = self.dist_bar_holder.size
        self._dist_bg_rect.pos = (x, y)
        self._dist_bg_rect.size = (w, h)
        progress = max(0.0, min(1.0, self._dist_progress))
        self._dist_fill_rect.pos = (x, y)
        self._dist_fill_rect.size = (w * progress, h)

    # --- auto-play toggle (M12) ------------------------------------------

    def _charge_autoplayer(self) -> bool:
        """Spend the per-level autoplayer cost once. Returns True if autoplay
        may run this level (already paid, or just paid); False if the player
        can't afford it. Multiplayer never touches the save, so it's free there."""
        if self._auto_paid_for_level:
            return True
        running = ui.app()
        if (running is None or running.state is None
                or running.current_mode != "single"):
            self._auto_paid_for_level = True
            return True
        if running.state.spend_coins(AUTOPLAYER_COST):
            self._auto_paid_for_level = True
            self._float_text("-{} c".format(AUTOPLAYER_COST), (1.0, 0.45, 0.40, 1.0))
            running.audio.play_sfx("purchase")
            return True
        # Can't afford — feedback, no enable.
        self._float_text("NEED {} COINS".format(AUTOPLAYER_COST),
                         (1.0, 0.45, 0.40, 1.0))
        running.audio.play_sfx("error")
        return False

    def _toggle_auto(self) -> None:
        """Flip auto mode on/off. Same shape as CoinTex's _toggle_auto:
        flip the flag, refresh the button, then start or stop the GA
        daemon. The thread stays dormant when the game isn't active so
        it's safe to call this between levels."""
        if not self.auto_mode:
            # Turning autoplay ON costs coins (once per level); block if broke.
            if not self._charge_autoplayer():
                return
            self.auto_mode = True
            self._refresh_auto_button()
            if self.auto is None:
                self.auto = autoplay.AutoPlayer(self)
            if not self._level_ended and not self.paused:
                self.auto.start()
        else:
            self.auto_mode = False
            self._refresh_auto_button()
            if self.auto is not None:
                self.auto.stop()

    def _refresh_auto_button(self) -> None:
        if self.auto_btn is None:
            return
        if self.auto_mode:
            self.auto_btn.text = "Auto: On"
            self.auto_btn.bg = [0.20, 0.70, 0.40, 1]
        else:
            self.auto_btn.text = "Auto ({}c)".format(AUTOPLAYER_COST)
            self.auto_btn.bg = [0.45, 0.45, 0.5, 1]

    # --- 2× coins power-up indicator -------------------------------------

    def _update_dc_panel(self) -> None:
        """Show / hide and refresh the 2× COINS pill at top-center.

        Layout: a dim outer pill + a bright gold fill whose width tracks
        the time remaining. In the last 3 seconds the pill pulses white
        so the player gets a "hurry up!" cue before the bonus expires.
        """
        panel = self.dc_panel
        if panel is None:
            return
        if self.double_coin_until <= self._run_time:
            if panel.opacity != 0:
                panel.opacity = 0
            return
        remaining = self.double_coin_until - self._run_time
        total = entities.PickupController.DOUBLE_COIN_DURATION_SEC
        progress = max(0.0, min(1.0, remaining / total))
        panel.opacity = 1
        self.dc_label.text = "[b]2× COINS  {:.1f}s[/b]".format(remaining)
        # Update fill width from the new progress value.
        self._redraw_dc_panel(progress=progress)
        # Pulse white in the last 3 seconds — sin-wave alpha so it
        # pumps smoothly rather than blinking.
        if remaining < 3.0:
            pulse = 0.35 + 0.30 * abs(math.sin(self._run_time * 8.0))
            self._dc_flash_color.rgba = (1.0, 1.0, 1.0, pulse * (3.0 - remaining) / 3.0)
        else:
            self._dc_flash_color.rgba = (1.0, 1.0, 1.0, 0.0)

    def _redraw_dc_panel(self, *, progress: float | None = None) -> None:
        """Reposition the pill's canvas rectangles whenever the widget
        is resized OR whenever the fill progress changes.

        ``progress`` is the share of duration remaining in [0, 1]. When
        not passed we reuse the current value so a layout pass doesn't
        suddenly redraw an empty fill.
        """
        if self.dc_panel is None or self._dc_bg_rect is None:
            return
        x, y = self.dc_panel.pos
        w, h = self.dc_panel.size
        self._dc_bg_rect.pos = (x, y)
        self._dc_bg_rect.size = (w, h)
        if progress is None:
            progress = self._dc_fill_rect.size[0] / max(1.0, w)
        self._dc_fill_rect.pos = (x, y)
        self._dc_fill_rect.size = (w * progress, h)
        self._dc_flash_rect.pos = (x, y)
        self._dc_flash_rect.size = (w, h)

    # --- pause / resume (port of CoinTex GameScreen pattern) -------------

    def _set_freeze_tint(self, on: bool) -> None:
        """Translucent icy-blue overlay over the stage while Freeze is active —
        an unmistakable 'time stopped' cue. Created lazily, fades in/out."""
        want = 0.22 if on else 0.0
        if getattr(self, "_freeze_overlay", None) is None:
            if not on:
                return
            ov = Widget()
            with ov.canvas:
                self._freeze_color = Color(0.45, 0.78, 1.0, 0.0)
                self._freeze_rect = Rectangle()
            self._freeze_overlay = ov
            # Sit behind the HUD/hero but over the world: add under hero layer.
            self.stage.add_widget(ov)
            self._freeze_overlay_on = None
        self._freeze_rect.pos = self.stage.pos
        self._freeze_rect.size = self.stage.size
        if getattr(self, "_freeze_overlay_on", None) != on:
            self._freeze_overlay_on = on
            Animation(a=want, duration=0.2).start(self._freeze_color)

    def _show_pause_dim(self, on: bool) -> None:
        """Fade a translucent black overlay over the gameplay while paused so
        the frozen world clearly reads as 'paused' behind the modal."""
        if on:
            if getattr(self, "_pause_dim", None) is None:
                dim = Widget()
                with dim.canvas:
                    self._pause_dim_color = Color(0, 0, 0, 0.0)
                    self._pause_dim_rect = Rectangle()
                self._pause_dim = dim
                self.root_layout.add_widget(dim)
            self._pause_dim_rect.pos = self.root_layout.pos
            self._pause_dim_rect.size = self.root_layout.size
            Animation(a=0.45, duration=0.18).start(self._pause_dim_color)
        elif getattr(self, "_pause_dim", None) is not None:
            Animation(a=0.0, duration=0.18).start(self._pause_dim_color)

    def _open_pause(self) -> None:
        """Open the pause modal (Resume / Shop / Quit). Update loop respects
        self.paused so the world freezes; a dim overlay reads as 'paused'."""
        if self._level_ended or self.paused:
            return
        self.paused = True
        running = ui.app()
        running.audio.play_sfx("pause")
        # Silence music while paused (CoinTex pattern).
        try:
            running.audio.stop_music()
        except Exception:
            pass
        self._show_pause_dim(True)

        def leave_run(destination):
            # Shared teardown for both Quit and Shop — abandons the run.
            self.paused = False
            self._level_ended = True
            self._show_pause_dim(False)
            if self._update_event is not None:
                self._update_event.cancel()
                self._update_event = None
            if destination == "shop":
                self._exit_to("shop")
            else:
                self._exit()

        def on_resume():
            self._show_pause_dim(False)
            self._resume()

        ui.PauseDialog(
            on_resume=on_resume,
            on_shop=lambda: leave_run("shop"),
            on_quit=lambda: leave_run("menu"),
        ).open()

    def _resume(self) -> None:
        """Resume from pause: restart the level music and unblock _update."""
        if self._level_ended:
            return
        self.paused = False
        running = ui.app()
        # Re-pick the right track for the current level.
        if running.current_mode == "single" and running.current_level:
            level_cfg = levels.get_level(running.current_level)
            if level_cfg and level_cfg.get("boss"):
                running.audio.play_boss_music()
            else:
                world = ((running.current_level - 1) // levels.LEVELS_PER_WORLD) + 1
                running.audio.play_level_music(world)
        else:
            running.audio.play_level_music(1)
