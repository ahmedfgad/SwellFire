"""Encode/concat helpers over the pip-bundled static ffmpeg (imageio-ffmpeg).
Dev/build-time only. No system ffmpeg or sudo required."""

import os
import subprocess

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def encode_clip(frames_dir, wav_path, out_path, fps=60, size=None):
    """frames_dir/f%05d.png + wav -> H.264/AAC mp4. Optional (w,h) scale."""
    vf = []
    if size is not None:
        vf = ["-vf", "scale={}:{}:flags=lanczos".format(size[0], size[1])]
    cmd = [FFMPEG, "-y",
           "-framerate", str(fps), "-i", os.path.join(frames_dir, "f%05d.png"),
           "-i", wav_path,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-shortest"] + vf + [out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def concat_clips(clip_paths, out_path):
    """Concatenate mp4s (re-encode for safety) into one file."""
    listfile = out_path + ".txt"
    with open(listfile, "w") as f:
        for p in clip_paths:
            f.write("file '{}'\n".format(os.path.abspath(p)))
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(listfile)
    return out_path
