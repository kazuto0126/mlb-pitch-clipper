"""Pre-flight environment check (runs before any discovery).

Missing tools fail HERE with a clear message — never mid-pipeline.
Does not modify the user system.
"""
from __future__ import annotations

import shutil
import sys

REQUIRED_BINS = ("ffmpeg", "ffprobe", "yt-dlp")
REQUIRED_MODS = ("cv2", "numpy", "PIL", "open_clip", "torch")


def check(bins=REQUIRED_BINS, mods=REQUIRED_MODS,
          which=shutil.which) -> list[str]:
    problems = []
    if sys.version_info < (3, 10):
        problems.append(f"Python 3.10+ required (found {sys.version.split()[0]}).")
    for b in bins:
        if not which(b):
            if b == "ffmpeg":
                problems.append("FFmpeg not found. Install FFmpeg and ensure "
                                "ffmpeg/ffprobe are available on PATH.")
            elif b == "ffprobe":
                problems.append("ffprobe not found (ships with FFmpeg). "
                                "Install FFmpeg and ensure it is on PATH.")
            else:
                problems.append(f"{b} not found. Install it (pip install {b}) "
                                "and ensure it is available on PATH.")
    for m in mods:
        try:
            __import__(m)
        except Exception:
            problems.append(f"Python package '{m}' is not importable. "
                            "Run: pip install -r requirements.txt")
    return problems
