"""test_early_game_levels.py — W1 onboarding tuning.
Run: SDL_AUDIODRIVER=dummy .venv/bin/python tests/test_early_game_levels.py"""
from swellfire import levels


def test_w1_starting_squad_is_5():
    assert levels.get_level(1)["starting_squad"] == 5      # W1-L1, non-boss


def test_starting_squad_grows_by_world():
    assert levels.get_level(11)["starting_squad"] == 6     # W2-L1
    assert levels.get_level(51)["starting_squad"] == 10    # W6-L1


def test_w1_density_softened():
    c = levels.get_level(1)
    assert c["formation_columns"] == 4
    assert abs(c["rank_interval_start"] - 420.0) < 1e-6
    assert abs(c["rank_interval_end"] - 280.0) < 1e-6


def test_late_density_high_end():
    c = levels.get_level(60)                                # W6 last, t=1
    assert c["formation_columns"] == 6
    assert abs(c["rank_interval_start"] - 390.0) < 1e-6
    assert abs(c["rank_interval_end"] - 260.0) < 1e-6


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL EARLY GAME LEVELS TESTS PASSED")
