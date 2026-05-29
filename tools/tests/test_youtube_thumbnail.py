import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PIL import Image
from tools import make_youtube_thumbnail as yt

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def test_thumbnail_dims_and_written():
    yt.main()
    p = os.path.join(ROOT, "swellfire_media", "youtube_thumbnail_1280x720.png")
    assert os.path.exists(p)
    assert Image.open(p).size == (1280, 720)
