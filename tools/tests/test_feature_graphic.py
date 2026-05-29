import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PIL import Image
from tools import make_feature_graphic as fg

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def test_feature_graphic_dims_and_written():
    fg.main()
    p = os.path.join(ROOT, "swellfire_media", "feature_graphic_1024x500.png")
    assert os.path.exists(p)
    im = Image.open(p)
    assert im.size == (1024, 500)
