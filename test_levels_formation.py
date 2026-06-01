"""test_levels_formation.py — per-level formation params.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_levels_formation.py"""
import levels


def test_formation_keys_present():
    cfg = levels.get_level(1)
    for k in ("formation_columns", "rank_interval_start", "rank_interval_end"):
        assert k in cfg, k


def test_ranks_get_denser_toward_end_of_level():
    cfg = levels.get_level(1)
    # Smaller interval = denser. End interval < start interval.
    assert cfg["rank_interval_end"] < cfg["rank_interval_start"]


def test_later_worlds_are_denser_or_wider():
    early = levels.get_level(1)
    late = levels.get_level(55)   # W6
    assert (late["formation_columns"] >= early["formation_columns"]
            and late["rank_interval_end"] <= early["rank_interval_end"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL LEVELS FORMATION TESTS PASSED")
