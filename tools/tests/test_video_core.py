import os, sys, subprocess, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import numpy as np
from PIL import Image
from tools import video_core


def _probe(path):
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    # ffmpeg can report stream info on stderr with -i
    r = subprocess.run([exe, "-i", path], capture_output=True, text=True)
    return r.stderr


def test_encode_clip_has_video_audio_and_size(tmp_path):
    frames = tmp_path / "f"
    frames.mkdir()
    for i in range(30):
        arr = (np.ones((180, 320, 3), np.uint8) * (i * 6 % 255))
        Image.fromarray(arr).save(frames / ("f%05d.png" % i))
    # 1s of silence wav
    import wave
    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes((np.zeros(44100, np.int16)).tobytes())
    out = tmp_path / "clip.mp4"
    video_core.encode_clip(str(frames), str(wav), str(out), fps=30, size=(640, 360))
    assert out.exists() and out.stat().st_size > 0
    info = _probe(str(out))
    assert "Video:" in info and "Audio:" in info
    assert "640x360" in info
