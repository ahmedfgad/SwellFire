import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PIL import Image
from tools import gen_brand_assets as g

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def test_icon_is_512_square_rgba_nonblank():
    img = g.make_icon()
    assert img.size == (512, 512)
    assert img.mode == "RGBA"
    assert img.getextrema()[3][1] > 0  # some opaque pixels


def test_presplash_matches_source_size():
    # presplash is the hand-authored portrait splash from marketing/re/.
    img = g.make_presplash()
    src = Image.open(g.PRESPLASH_SRC)
    assert img.size == src.size


def test_main_writes_files():
    g.main()
    assert os.path.exists(os.path.join(ROOT, "icon.png"))
    assert os.path.exists(os.path.join(ROOT, "presplash.png"))
    assert os.path.exists(os.path.join(ROOT, "marketing", "icon.png"))
    assert os.path.exists(os.path.join(ROOT, "marketing", "presplash.png"))
    assert Image.open(os.path.join(ROOT, "icon.png")).size == (512, 512)
