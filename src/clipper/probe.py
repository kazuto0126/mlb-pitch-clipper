"""Video probing via ffprobe. No frame content analysis here."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    n_frames: int | None = None


def _eval_fps(s: str) -> float:
    # ffprobe returns e.g. "30000/1001"
    if "/" in s:
        num, den = s.split("/", 1)
        den_f = float(den)
        if den_f == 0:
            return 0.0
        return float(num) / den_f
    return float(s)


def probe_video(path: str) -> VideoInfo:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not streams:
        raise ValueError(f"no video stream: {path}")
    v = streams[0]
    fmt = data.get("format", {})
    fps = _eval_fps(v.get("avg_frame_rate", v.get("r_frame_rate", "30/1")))
    duration = float(fmt.get("duration", v.get("duration", 0.0)))
    return VideoInfo(
        path=path,
        width=int(v.get("width", 0)),
        height=int(v.get("height", 0)),
        fps=fps,
        duration=duration,
        codec=str(v.get("codec_name", "")),
    )
