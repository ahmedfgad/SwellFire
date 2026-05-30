import os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PIL import Image
from tools import upscale_screenshots as up

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def test_upscales_all_to_1080p():
    up.main()
    out = sorted(glob.glob(os.path.join(ROOT, "swellfire_media", "tablet_screenshots", "0*_*.png")))
    assert len(out) == 8
    for p in out:
        assert Image.open(p).size == (1080, 1920)
