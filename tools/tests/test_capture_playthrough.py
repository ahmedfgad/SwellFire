import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class _FakeState:
    """Mimics state.GameState.data; .save() must NOT be called by the seed."""
    def __init__(self):
        self.data = {"equipped_weapon": "pistol",
                     "weapon_tiers": {"pistol": 1, "rifle": 1, "shotgun": 1, "sniper": 1},
                     "squad_bonus": 0}
        self.saved = False

    def save(self):
        self.saved = True


def test_seed_strong_squad_maxes_weapon_and_squad_in_memory():
    from tools.capture import seed_strong_squad
    st = _FakeState()
    seed_strong_squad(st)
    assert st.data["equipped_weapon"] == "rifle"
    assert st.data["weapon_tiers"] == {"pistol": 4, "rifle": 4, "shotgun": 4, "sniper": 4}
    assert st.data["squad_bonus"] == 6
    assert st.saved is False  # seeding must never persist to the real save


def test_seed_strong_squad_tolerates_missing_keys():
    from tools.capture import seed_strong_squad
    st = _FakeState()
    st.data = {}
    seed_strong_squad(st)
    assert st.data["equipped_weapon"] == "rifle"
    assert st.data["weapon_tiers"]["sniper"] == 4
    assert st.data["squad_bonus"] == 6


def test_playthrough_flag_parses():
    from tools.capture import _build_argparser
    ns = _build_argparser().parse_args(
        ["--level", "6", "--out", "x", "--playthrough"])
    assert ns.playthrough is True


def test_playthrough_defaults_false():
    from tools.capture import _build_argparser
    ns = _build_argparser().parse_args(["--level", "6", "--out", "x"])
    assert ns.playthrough is False
