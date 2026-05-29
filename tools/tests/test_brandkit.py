import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PIL import Image
from tools import brandkit


def test_palette_has_locked_ember_colors():
    p = brandkit.EMBER
    assert p["red"] == (214, 31, 31)
    assert p["orange"] == (255, 122, 24)
    assert p["gold"] == (255, 211, 77)
    assert p["ember_black"] == (22, 6, 4)


def test_vertical_gradient_size_and_mode():
    img = brandkit.vertical_gradient((40, 20), (0, 0, 0), (255, 255, 255))
    assert img.size == (40, 20)
    assert img.mode == "RGB"
    # top darker than bottom
    assert sum(img.getpixel((0, 0))) < sum(img.getpixel((0, 19)))


def test_logo_glyph_draws_nonblank_on_transparent():
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    brandkit.draw_logo_glyph(img, (10, 10, 190, 190))
    # at least some opaque pixels were drawn
    alpha = img.split()[3]
    assert alpha.getextrema()[1] > 0


def test_font_loads_at_size():
    f = brandkit.load_font(48)
    assert f is not None
