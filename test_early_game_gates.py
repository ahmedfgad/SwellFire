"""test_early_game_gates.py — stable launch and survivable gate choices.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py"""
import gates


def test_regular_mul_pool_is_stable_x2():
    sp = gates.GateSpawner(controller=None, seed=1)
    sp.world_tier = 1
    vals = set()
    for _ in range(300):
        op, value, label = sp._pick_op(exclude_op=None, allowed=["mul"])
        vals.add(value)
    assert vals == {2}


class _RecCtrl:
    def __init__(self):
        self.pairs = []
    def spawn_pair(self, a, b):
        self.pairs.append((a, b))


def _first_pair_ops(seed):
    sp = gates.GateSpawner(controller=_RecCtrl(), seed=seed)
    sp.allowed_ops = ["mul", "add", "sub", "div"]
    sp.interval_px = 100.0
    sp.reset_per_level()
    sp.tick(10_000.0, 0.0, 400.0, 1000.0)   # well past _next_distance -> spawns
    a, b = sp.controller.pairs[-1]
    return {a[4], b[4]}                       # index 4 = op in the spawn tuple


def test_first_pair_offers_a_gain_across_seeds():
    gains = {gates.OP_MUL, gates.OP_ADD}
    for seed in range(30):
        assert _first_pair_ops(seed) & gains, seed   # always a gain in the opener


def test_addition_rewards_scale_with_world_pressure():
    early = gates.GateSpawner(controller=None, seed=4)
    early.world_tier = 1
    late = gates.GateSpawner(controller=None, seed=4)
    late.world_tier = 6
    early_values = {early._pick_op(None, ["add"])[1] for _ in range(100)}
    late_values = {late._pick_op(None, ["add"])[1] for _ in range(100)}
    assert early_values == {3, 5, 7}
    assert late_values == {8, 12, 16}


def test_launch_sequence_is_x3_then_two_x2_choices():
    for seed in range(30):
        ctrl = _RecCtrl()
        sp = gates.GateSpawner(controller=ctrl, seed=seed)
        sp.allowed_ops = ["mul", "add", "sub", "div"]
        values = []
        for step in range(3):
            sp.tick(10_000.0 + step * 1000.0, 0.0, 400.0, 1000.0)
            multipliers = [spec for spec in ctrl.pairs[-1]
                           if spec[4] == gates.OP_MUL]
            assert len(multipliers) == 1
            values.append(multipliers[0][5])
        assert values == [3, 2, 2]


def test_every_math_pair_has_a_non_damaging_choice():
    gains = {gates.OP_MUL, gates.OP_ADD}
    for seed in range(30):
        ctrl = _RecCtrl()
        sp = gates.GateSpawner(controller=ctrl, seed=seed)
        sp.allowed_ops = ["mul", "add", "sub", "div"]
        sp.BONUS_PAIR_CHANCE = 0.0
        sp.interval_px = 100.0
        for step in range(30):
            sp.tick(10_000.0 + step * 100.0, 0.0, 400.0, 1000.0)
            assert {spec[4] for spec in ctrl.pairs[-1]} & gains


def test_pair_counter_advances():
    sp = gates.GateSpawner(controller=_RecCtrl(), seed=1)
    sp.allowed_ops = ["mul", "add", "sub", "div"]
    sp.interval_px = 100.0
    sp.reset_per_level()
    assert sp._pairs_spawned == 0
    sp.tick(10_000.0, 0.0, 400.0, 1000.0)
    assert sp._pairs_spawned == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL EARLY GAME GATES TESTS PASSED")
