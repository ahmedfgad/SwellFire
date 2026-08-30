"""test_reward_gates_label.py — reward-gate xN strength + two-line label.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_reward_gates_label.py"""
from swellfire import gates


def test_bonus_value_in_range():
    sp = gates.GateSpawner(controller=None, seed=1)
    sp.world_tier = 6
    vals = {sp._bonus_value(gates.OP_FREEZE) for _ in range(200)}
    assert vals <= {1, 2, 3} and len(vals) >= 1
    sp2 = gates.GateSpawner(controller=None, seed=1)
    sp2.world_tier = 1
    assert all(sp2._bonus_value(gates.OP_FREEZE) in (1, 2, 3) for _ in range(50))


def test_build_bonus_pair_emits_xN_label():
    sp = gates.GateSpawner(controller=None, seed=3)
    sp.world_tier = 5
    sp.allowed_ops = ["reinforce", "freeze", "overdrive", "magnet"]
    sp.allowed_weapons = []
    got = False
    for _ in range(40):
        pair = sp._build_bonus_pair()
        if pair is None:
            continue
        for op, value, label in pair:
            assert value in (1, 2, 3)
            assert label == "{} x{}".format(
                gates.CONSUMABLE_BONUS[op], value), label
            got = True
    assert got, "no bonus pair produced"


def test_consumable_gate_renders_two_lines():
    g = gates.Gate("freeze", 2, "FREEZE x2")
    g.size = (120, 112)
    g.pos = (0, 0)
    assert g._name_label.text == "FREEZE"
    assert "2" in g._factor_label.text
    assert g.label_text == "FREEZE x2"   # canonical ASCII preserved


def test_weapon_gate_stays_single_line():
    g = gates.Gate("weapon", "rifle", "RIFLE")
    g.size = (120, 112)
    g.pos = (0, 0)
    assert g._name_label.text == "RIFLE"
    assert getattr(g, "_factor_label", None) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL REWARD GATE LABEL TESTS PASSED")
