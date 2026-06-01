"""test_early_game_gates.py — x3 multiplier + first-pair-gain bias.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_early_game_gates.py"""
import gates


def test_mul_pool_includes_3():
    sp = gates.GateSpawner(controller=None, seed=1)
    sp.world_tier = 1
    vals = set()
    for _ in range(300):
        op, value, label = sp._pick_op(exclude_op=None, allowed=["mul"])
        vals.add(value)
    assert vals == {2, 3}   # MUL can now be x2 or x3


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
