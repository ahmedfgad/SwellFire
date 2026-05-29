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


def test_presplash_is_1920x1080():
    img = g.make_presplash()
    assert img.size == (1920, 1080)


def test_main_writes_files():
    g.main()
    assert os.path.exists(os.path.join(ROOT, "icon.png"))
    assert os.path.exists(os.path.join(ROOT, "presplash.png"))
    assert os.path.exists(os.path.join(ROOT, "swellfire_media", "icon.png"))
    assert Image.open(os.path.join(ROOT, "icon.png")).size == (512, 512)
    assert Image.open(os.path.join(ROOT, "presplash.png")).size == (1920, 1080)
