"""Deterministic capture harness for Swellfire screenshots and video frames.

Boots the app in capture mode, drives the sim at a fixed dt with the GA
autoplayer stepped inline (repeatable; no wall-clock thread), grabs each GL
frame, and writes a frames dir + audio-event JSON.

Usage examples:
  # one screenshot of a meta screen
  venv/bin/python tools/capture.py --screen menu --shot out/menu.png --size 1280x720
  # a gameplay segment of level 2 for N frames at 1080p
  venv/bin/python tools/capture.py --level 2 --frames 600 --out out/seg_w1_lvl \
      --size 1920x1080 --audio out/seg_w1_lvl.json
"""

import argparse
import json
import os
import sys

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make the repo root importable (`main`, `autoplay`, `tools.*`) regardless of
# how this script is launched (as `tools/capture.py`, sys.path[0] is `tools/`).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
from PIL import Image


def _parse_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def _build_argparser():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", default=None, help="meta screen name for a screenshot")
    ap.add_argument("--level", type=int, default=None, help="level index 1..60 to play")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=30, help="frames to settle before capturing")
    ap.add_argument("--shot", default=None, help="single PNG output path (implies 1 frame)")
    ap.add_argument("--out", default=None, help="frames dir for a sequence")
    ap.add_argument("--audio", default=None, help="audio-event JSON output path")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--win", action="store_true",
                    help="(level mode) drive the squad to the distance goal so "
                         "the level-complete + stars dialog fires, then capture it")
    return ap


def main(argv=None):
    args = _build_argparser().parse_args(argv)

    w, h = _parse_size(args.size)

    # Kivy parses sys.argv at import time and would choke on our CLI flags
    # (printing its own usage). Neutralise argv before importing anything Kivy.
    sys.argv = ["main"]
    from kivy.config import Config
    Config.set("graphics", "width", str(w))
    Config.set("graphics", "height", str(h))
    Config.set("graphics", "resizable", "1")
    # Create the Kivy Window NOW, at our (screen-fitting) capture size, BEFORE
    # importing main.py. main sets Config to the portrait game size (540x960) at
    # import time and one of its submodules creates the Window; on a display
    # shorter than 960px that window can't be created (SDL resize_window error).
    # Kivy's Window is a singleton, so creating it here first pins our size and
    # main's import-time Config is ignored. Callers must keep --size on-screen.
    from kivy.core.window import Window

    import main as appmod
    from kivy.clock import Clock
    from tools.capture_core import grab_frame
    import autoplay

    app = appmod.SwellfireApp()
    state = {"frame": 0, "simt": 0.0, "ap_accum": 0.0, "done": False,
             "settle": 0, "ready": False, "won_triggered": False,
             "modal_settle": 0, "modal_seen": False}
    DT = 1.0 / 60.0
    # The Xwayland/SDL2 window ignores Config width/height and opens at 800x600;
    # we force Window.size after build, but the resize is not always honoured by
    # the first rendered frame, so we let a few Clock frames pass (and re-assert
    # the size) until the backbuffer actually matches before capturing anything.
    SETTLE_FRAMES = 8

    def after_build(_dt):
        Window.size = (w, h)
        # sim clock for the audio timeline
        app.audio.start_capture_log(clock=lambda: state["simt"])

        # On a fresh save the menu auto-routes to the one-shot tutorial, which
        # would steal focus from the level we want to capture. Mark it seen so
        # that deferred navigation is suppressed.
        try:
            app.state.set_setting("tutorial_seen", True)
        except Exception:
            pass

        if args.screen is not None:
            app.go(args.screen)
        else:
            app.start_level(args.level)

        Clock.schedule_once(_drive, 0)

    def _game_screen():
        return app.sm.get_screen("game") if app.sm.has_screen("game") else None

    def _enter_ready(gs):
        """For a level capture, confirm we're actually in the running game.

        `start_level` may bounce through other screens (and a fresh save's
        menu may have queued a tutorial nav), so we re-assert "game" until the
        screen is current with a live hero. Once there, we cancel the game's
        own Clock-scheduled `_update` so this harness is the sole, fixed-dt
        driver (deterministic frame pacing; no double-stepping).
        """
        if app.sm.current != "game" or gs is None or gs.hero is None:
            if app.sm.current not in ("game", "levelselect"):
                app.start_level(args.level)
            return False
        if gs._update_event is not None:
            gs._update_event.cancel()
            gs._update_event = None
        if gs._level_ended:
            # Cancelled before _reset finished; wait one more frame.
            return False
        # Hide the debug FPS/counter overlay so captured frames are clean
        # marketing shots (the overlay is a dev aid, never shipped UI).
        if getattr(gs, "debug", None) is not None:
            gs.debug.opacity = 0.0
        state["ready"] = True
        return True

    def _drive(_dt):
        # Let the forced Window.size settle before the first grab: re-assert it
        # and wait until the GL backbuffer reports the requested dimensions.
        if state["settle"] < SETTLE_FRAMES or tuple(Window.size) != (w, h):
            if tuple(Window.size) != (w, h):
                Window.size = (w, h)
            state["settle"] += 1
            Clock.schedule_once(_drive, 0)
            return

        gs = _game_screen()

        # For a level capture, block until the running game is actually live.
        if args.level is not None and not state["ready"]:
            _enter_ready(gs)
            if not state["ready"]:
                Clock.schedule_once(_drive, 0)
                return

        # --win: once the squad has grown (after `warmup` steps), shove the
        # distance to the goal so the next `_update` fires the genuine
        # level-complete path (_end_level(won=True) -> VICTORY banner + the
        # LevelResultDialog with real stars/score). We then wait for that modal
        # to actually open before grabbing (it's deferred ~1s real-time).
        if (args.win and args.level is not None and gs is not None
                and state["ready"] and not state["won_triggered"]
                and state["frame"] >= args.warmup
                and not gs._level_ended and gs.distance_goal > 0):
            gs.distance = gs.distance_goal
            state["won_triggered"] = True

        # Drive a fixed number of fixed-dt steps, grabbing each rendered frame.
        if args.level is not None and gs is not None and app.sm.current == "game":
            # Step the sim by a fixed dt (decoupled from real time).
            gs._update(DT)
            # Inline GA decision every RETARGET_DELAY of sim time.
            state["ap_accum"] += DT
            if state["ap_accum"] >= autoplay.RETARGET_DELAY:
                state["ap_accum"] = 0.0
                snap = autoplay.sense(gs)
                if snap is not None:
                    dec = autoplay._decide(snap)
                    seeds = [snap["hero_x_frac"]]
                    if snap["gate"]:
                        g = snap["gate"]
                        seeds += [g["left_x"] + g["left_w"] * 0.5,
                                  g["right_x"] + g["right_w"] * 0.5]
                    if dec:
                        seeds.append(dec["desired_x"])
                    best = max(seeds, key=lambda f: autoplay.fitness(snap, f, dec, None))
                    gs._hero_target_x = snap["road_left"] + best * snap["road_w"]
        state["simt"] += DT

        # --win: hold off grabbing until the level-complete ModalView is open
        # (the dialog is scheduled ~1s of real time after _end_level fires;
        # the busy loop lets that wall-clock time elapse). Then grab it.
        if args.win:
            from kivy.uix.modalview import ModalView
            modal_open = any(isinstance(c, ModalView) for c in Window.children)
            # The ModalView registers as a Window child the instant it opens,
            # but its content (stars/score) needs a few frames to lay out and
            # fade in (_fade_in_modal, ~0.18s). Once the modal is detected, let
            # `modal_settle` frames pass so the dialog is fully drawn.
            if state["won_triggered"] and modal_open:
                state["modal_seen"] = True
            if state["modal_seen"]:
                state["modal_settle"] += 1
            ready = state["modal_seen"] and state["modal_settle"] >= 30
            if not ready:
                state["frame"] += 1
                # Once the win has fired we're just waiting for the dialog,
                # which is scheduled ~1s of *real* time later. A zero-delay
                # reschedule starves the wall clock (the sim runs far faster
                # than real time), so step on a small real delay post-trigger
                # to let that timer elapse in a bounded number of frames.
                delay = 1.0 / 120.0 if state["won_triggered"] else 0
                Clock.schedule_once(_drive, delay)
                return
            arr = grab_frame(Window)
            os.makedirs(os.path.dirname(args.shot) or ".", exist_ok=True)
            Image.fromarray(arr).save(args.shot)
            _finish()
            return

        # Grab after warmup.
        if state["frame"] >= args.warmup:
            arr = grab_frame(Window)
            idx = state["frame"] - args.warmup
            if args.shot is not None:
                os.makedirs(os.path.dirname(args.shot) or ".", exist_ok=True)
                Image.fromarray(arr).save(args.shot)
                _finish()
                return
            if args.out is not None:
                os.makedirs(args.out, exist_ok=True)
                Image.fromarray(arr).save(os.path.join(args.out, "f%05d.png" % idx))
            if idx + 1 >= args.frames:
                _finish()
                return
        state["frame"] += 1
        Clock.schedule_once(_drive, 0)

    def _finish():
        if args.audio is not None:
            os.makedirs(os.path.dirname(args.audio) or ".", exist_ok=True)
            with open(args.audio, "w") as f:
                json.dump({"fps": 60, "events": app.audio.capture_log or []}, f)
        state["done"] = True
        app.stop()

    Clock.schedule_once(after_build, 0.3)
    app.run()


if __name__ == "__main__":
    main()
