"""test_autoplayer_cost.py — autoplayer cost constant + spend semantics.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_autoplayer_cost.py"""
from swellfire import game
from swellfire import state


def test_cost_is_30():
    assert game.AUTOPLAYER_COST == 30


def test_spend_deducts_when_affordable():
    s = state.GameState("/tmp/sf_autocost_a")
    s.data["coins_balance"] = 100
    assert s.spend_coins(game.AUTOPLAYER_COST) is True
    assert s.coins_balance == 70


def test_spend_blocked_when_unaffordable():
    s = state.GameState("/tmp/sf_autocost_b")
    s.data["coins_balance"] = 10
    assert s.spend_coins(game.AUTOPLAYER_COST) is False
    assert s.coins_balance == 10


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL AUTOPLAYER COST TESTS PASSED")
