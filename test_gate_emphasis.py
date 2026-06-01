"""test_gate_emphasis.py — #3: the gate emphasis pop must not reflow/wrap text.
Run: SDL_AUDIODRIVER=dummy venv/bin/python test_gate_emphasis.py"""
import gates


def _make_gate():
    # "reinforce" is a valid bonus op (gates.OP_COLORS); "REINFORCE" is a long
    # word label that used to wrap to "REINFORC"/"E" when font_size grew.
    g = gates.Gate("reinforce", 1, "REINFORCE")
    g.size = (120, 112)
    g.pos = (0, 0)
    return g


def test_emph_scale_does_not_reflow_label():
    g = _make_gate()
    lbl = g._name_label
    fs0, txt0, ts0 = lbl.font_size, lbl.text, tuple(lbl.text_size)
    g.emph_scale = 1.18           # simulate the emphasis peak
    assert lbl.font_size == fs0, "font_size must not change (would reflow)"
    assert lbl.text == txt0
    assert tuple(lbl.text_size) == ts0
    assert abs(g._scale.x - 1.18) < 1e-6
    assert abs(g._scale.y - 1.18) < 1e-6


def test_emphasize_sets_flag_and_leaves_font_untouched():
    g = _make_gate()
    lbl = g._name_label
    fs0 = lbl.font_size
    g.emphasize()
    assert g._emphasized is True
    assert lbl.font_size == fs0   # emphasize animates emph_scale, not font


def test_mark_selected_does_not_reflow_label():
    g = _make_gate()
    lbl = g._name_label
    fs0, txt0, ts0 = lbl.font_size, lbl.text, tuple(lbl.text_size)
    g.mark_selected()
    assert lbl.font_size == fs0, "mark_selected must not change font_size (reflow)"
    assert lbl.text == txt0
    assert tuple(lbl.text_size) == ts0
    assert abs(g._scale.x - 1.14) < 1e-6   # enlarged via transform instead


def test_scale_origin_tracks_center_on_sync():
    g = _make_gate()
    g.pos = (40, 60)              # triggers _sync via the pos bind
    assert tuple(g._scale.origin)[:2] == (g.center_x, g.center_y)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL GATE EMPHASIS TESTS PASSED")
