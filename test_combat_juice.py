"""test_combat_juice.py — pure combat-feedback helpers.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_combat_juice.py
(pure helpers need no SDL; the mapping check imports entities under SDL dummy.)"""
import combat_juice


def test_score_for_kill_by_type():
    # grunt=0:10, tank=1:50, bomber=2:25, splitter=3:20, swarmer=4:8
    assert combat_juice.score_for_kill(0) == 10
    assert combat_juice.score_for_kill(1) == 50
    assert combat_juice.score_for_kill(4) == 8
    assert combat_juice.score_for_kill(999) == 10   # unknown → default 10


def test_combat_cue_kill_is_silent():
    # The noisy enemy-death "smash" crunch was removed: kill windows are silent;
    # only a non-lethal impact (no kill) plays "enemy_hit".
    assert combat_juice.combat_cue(True, True) is None
    assert combat_juice.combat_cue(True, False) is None
    assert combat_juice.combat_cue(False, True) == "enemy_hit"
    assert combat_juice.combat_cue(False, False) is None


def test_sfx_due_respects_interval():
    assert combat_juice.sfx_due(now=1.0, last=0.90, interval=0.07) is True
    assert combat_juice.sfx_due(now=1.0, last=0.95, interval=0.07) is False


def test_score_table_keys_match_entity_types():
    import entities
    assert set(combat_juice.SCORE_PER_KILL) == {
        entities.TYPE_GRUNT, entities.TYPE_TANK, entities.TYPE_BOMBER,
        entities.TYPE_SPLITTER, entities.TYPE_SWARMER,
    }


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL COMBAT JUICE TESTS PASSED")
