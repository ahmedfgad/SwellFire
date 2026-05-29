"""Capture-core: read the Kivy GL framebuffer into a numpy RGB array.

grab_frame(window) returns an (H, W, 3) uint8 array (top-row-first) of exactly
what is currently on the GL backbuffer. Used by the capture harness for both
screenshots and video frames.

Proven path on this machine (Kivy/SDL2, Linux): `glReadPixels` with GL_RGB /
GL_UNSIGNED_BYTE works and returns a bytes buffer of w*h*3. OpenGL's origin is
bottom-left, so we np.flipud to top-row-first (image convention). If a future
Kivy build makes glReadPixels awkward, fall back to Window.screenshot() (writes
a PNG you reload with PIL) while keeping this same (H, W, 3) uint8 contract.
"""

import numpy as np
from kivy.graphics.opengl import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE


def grab_frame(window):
    w, h = window.size
    data = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
    arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)
    # OpenGL origin is bottom-left; flip to top-row-first (image convention).
    return np.flipud(arr).copy()
