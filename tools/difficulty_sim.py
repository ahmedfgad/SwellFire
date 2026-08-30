"""Headless difficulty sim across all 60 levels.

For each level, runs three agents:

    * PASSIVE     — never drags or picks a gate.
    * GREEDY      — chooses the higher-value gate with a fresh default loadout.
    * PROGRESSION — uses the same gate logic with the upgrades available in
                    that world. This is the all-level playability profile.

Output: per-world summary + overall pass-rate table.

The sim uses Kivy's normal run loop but schedules a tight inner loop that
calls `GameScreen._update(dt)` many times per real-time tick. A complete
three-profile sweep takes several minutes on a typical development machine.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import traceback
import types
from dataclasses import dataclass

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kivy.clock import Clock        # noqa: E402

from swellfire import gates as gates_mod           # noqa: E402
from swellfire import levels                       # noqa: E402
import main as m                    # noqa: E402


SIM_DT = 1.0 / 60.0
SIM_MAX_SECONDS = 160.0   # W6L9 is 138 s; allow headroom for greedy to finish


@dataclass
class RunResult:
    level: int
    world: int
    in_world: int
    mode: str
    won: bool
    seconds: float
    final_squad: int
    kills: int
    gates_applied: int
    gates_missed: int
    attrition: int


def _op_value(gate, squad: int) -> float:
    squad = max(0, int(squad))
    if gate.op == gates_mod.OP_MUL:
        outcome = min(100, squad * int(gate.value))
    elif gate.op == gates_mod.OP_ADD:
        outcome = min(100, squad + int(gate.value))
    elif gate.op == gates_mod.OP_SUB:
        outcome = max(0, squad - int(gate.value))
    elif gate.op == gates_mod.OP_DIV:
        divisor = max(1, int(gate.value))
        outcome = squad // divisor
    elif gate.op in gates_mod.BONUS_OPS:
        return 0.1 * gate.value if isinstance(gate.value, int) else 0.1
    else:
        return -1000.0
    return float(outcome - squad)


def _greedy_target(gs) -> float | None:
    if gs.gate_controller is None or gs.hero is None:
        return None
    best_pair = None
    best_y = float("inf")
    for pair in gs.gate_controller.pairs:
        if all(g.consumed for g in pair):
            continue
        if pair[0].center_y > gs.hero.center_y and pair[0].center_y < best_y:
            best_y = pair[0].center_y
            best_pair = pair
    if best_pair is None:
        return None
    scored = [(_op_value(g, gs.squad_count), g) for g in best_pair]
    scored.sort(key=lambda item: item[0], reverse=True)
    g = scored[0][1]
    return g.x + g.width * 0.5


# Sim state across Clock callbacks.
class SimState:
    def __init__(self, app, level_list, modes):
        self.app = app
        self.level_list = list(level_list)
        self.modes = list(modes)
        self.results: list[RunResult] = []
        # Index into (mode_i * levels + level_i).
        self._level_idx = 0
        self._mode_idx = 0
        self._level_seconds = 0.0
        self._restart_pending = True
        # Set True once we've seen _reset run for the current level (the only
        # signal we have that `self.distance` etc. have been zeroed).
        self._reset_observed = False
        self._end_hook_installed = False

    def _install_end_hook(self, gs) -> None:
        """End a simulated run without dialogs, save writes, or delayed UI.

        The production ``_end_level`` persists results and schedules a modal.
        That is correct in the game but made this diagnostic mutate the real
        player save and stall behind result/world-intro dialogs after L1.
        """
        if self._end_hook_installed:
            return

        def finish(screen, won: bool) -> None:
            if screen._level_ended:
                return
            screen._sim_won = bool(won)
            screen._level_ended = True
            if screen._update_event is not None:
                screen._update_event.cancel()
                screen._update_event = None

        gs._end_level = types.MethodType(finish, gs)
        self._end_hook_installed = True

    def _prepare_isolated_state(self) -> None:
        """Use a stable isolated loadout and suppress one-time modal pauses."""
        state = self.app.state
        state.data = state._default()
        if self.current_mode() == "progression":
            world = ((self.current_level() - 1) // levels.LEVELS_PER_WORLD) + 1
            state.data["highest_unlocked"] = self.current_level()
            state.data["weapon_tiers"]["rifle"] = world
            state.data["equipped_weapon"] = "rifle"
            state.data["squad_bonus"] = max(0, world - 1)
        settings = state.data["settings"]
        settings["music_on"] = False
        settings["sfx_on"] = False
        settings["tutorial_seen"] = True
        for world in range(2, levels.NUM_WORLDS + 1):
            settings["intro_seen_w{}".format(world)] = True

    def current_mode(self):
        return self.modes[self._mode_idx]

    def current_level(self):
        return self.level_list[self._level_idx]

    def done(self) -> bool:
        return self._mode_idx >= len(self.modes)

    def step(self):
        """One real-time tick: pump many sim updates until level ends / cap."""
        if self.done():
            self.app.stop()
            return
        gs = self.app.sm.get_screen("game")
        self._install_end_hook(gs)
        if self._restart_pending:
            # Start (or restart) the current level.
            gs._sim_won = False
            self._prepare_isolated_state()
            self.app.start_level(self.current_level())
            self._restart_pending = False
            self._level_seconds = 0.0
            self._reset_observed = False
            return

        # Cancel the auto-scheduled Clock tick once we see it appear (after
        # `_reset` ran). We drive `_update` ourselves at SIM_DT, and we mark
        # the level "ready" so subsequent ticks know `self.distance` was zeroed.
        if not self._reset_observed:
            if (gs is None or gs.hero is None or gs.enemy_pool is None
                    or self.app.sm.current != "game"
                    or gs._update_event is None):
                return
            gs._update_event.cancel()
            gs._update_event = None
            self._reset_observed = True
            # On_enter sets `_level_ended = False`; if it's True now it's because
            # we cancelled too early — bail and wait one more tick.
            if gs._level_ended:
                self._reset_observed = False
                return

        mode = self.current_mode()
        # Inner loop: drive many updates per real tick.
        BATCH = 240   # ~4 sim-seconds per real tick
        for _ in range(BATCH):
            if gs._level_ended or self._level_seconds >= SIM_MAX_SECONDS:
                break
            if mode == "passive":
                gs._dragging = False
            elif mode in ("greedy", "progression"):
                t = _greedy_target(gs)
                if t is not None:
                    gs._hero_target_x = t
                    gs._dragging = True
                else:
                    gs._dragging = False
            gs._update(SIM_DT)
            self._level_seconds += SIM_DT

        if gs._level_ended or self._level_seconds >= SIM_MAX_SECONDS:
            won = bool(getattr(gs, "_sim_won", False))
            r = RunResult(
                level=self.current_level(),
                world=((self.current_level() - 1) // levels.LEVELS_PER_WORLD) + 1,
                in_world=((self.current_level() - 1) % levels.LEVELS_PER_WORLD) + 1,
                mode=mode,
                won=won,
                seconds=self._level_seconds,
                final_squad=max(0, gs.squad_count),
                kills=gs.kills_total,
                gates_applied=gs.gate_controller.applied_total if gs.gate_controller else 0,
                gates_missed=gs.gate_controller.missed_total if gs.gate_controller else 0,
                attrition=gs.attrition_total,
            )
            self.results.append(r)
            tag = "W" if r.won else "L"
            print(f"  [{mode:7s}] L{r.level:2d}  W{r.world}-L{r.in_world:2d}  "
                  f"{tag}  {r.seconds:5.1f}s  squad={r.final_squad:3d}  "
                  f"kills={r.kills:3d}  gates {r.gates_applied}/{r.gates_missed}  "
                  f"attr={r.attrition}")
            # Advance.
            self._level_idx += 1
            if self._level_idx >= len(self.level_list):
                self._level_idx = 0
                self._mode_idx += 1
            self._restart_pending = True


class SimulationApp(m.SwellfireApp):
    """Swellfire app whose GameState lives only for this simulation run."""

    def __init__(self, storage_dir: str, **kwargs):
        self._simulation_storage_dir = storage_dir
        bootstrap = m.GameState(storage_dir)
        bootstrap.data = bootstrap._default()
        settings = bootstrap.data["settings"]
        settings["music_on"] = False
        settings["sfx_on"] = False
        settings["tutorial_seen"] = True
        for world in range(2, levels.NUM_WORLDS + 1):
            settings["intro_seen_w{}".format(world)] = True
        bootstrap.save()
        super().__init__(**kwargs)

    @property
    def user_data_dir(self) -> str:
        return self._simulation_storage_dir


def main() -> int:
    modes = ("passive", "greedy", "progression")
    print("Difficulty sim — 60 levels × {} via GameScreen._update at 60Hz".format(
        ", ".join(modes)))
    print()
    storage = tempfile.TemporaryDirectory(prefix="swellfire-difficulty-")
    app = SimulationApp(storage.name)
    sim = SimState(app, level_list=range(1, levels.TOTAL_LEVELS + 1),
                   modes=modes)

    def tick(_dt):
        sim.step()

    Clock.schedule_interval(tick, 0)
    try:
        app.run()
    finally:
        storage.cleanup()

    # Summary
    by_world: dict[tuple[int, str], list[RunResult]] = {}
    for r in sim.results:
        by_world.setdefault((r.world, r.mode), []).append(r)

    print()
    print("=== Per-world summary ===")
    print(f"{'World':<6}{'Mode':<10}{'PassRate':>10}{'AvgSec':>10}{'AvgSquad':>10}")
    for world in range(1, levels.NUM_WORLDS + 1):
        for mode in modes:
            results = by_world.get((world, mode), [])
            if not results:
                continue
            pass_rate = sum(1 for r in results if r.won) / len(results)
            avg_sec = statistics.mean(r.seconds for r in results)
            avg_squad = statistics.mean(r.final_squad for r in results)
            print(f"{world:<6}{mode:<10}{pass_rate*100:>9.0f}% {avg_sec:>9.1f}s {avg_squad:>9.1f}")

    print()
    print("=== Pass rates ===")
    for mode in modes:
        total = sum(1 for r in sim.results if r.mode == mode)
        passes = sum(1 for r in sim.results if r.mode == mode and r.won)
        if total > 0:
            print(f"  {mode:7s}  {passes}/{total}  ({passes/total*100:.0f}%)")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
