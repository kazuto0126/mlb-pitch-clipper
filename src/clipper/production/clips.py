"""Exact clip extraction from the normalized source.

- Accurate seek (post-input -ss) + single H.264/yuv420p re-encode so the
  later concat demuxer can -c copy without another generation.
- No title cards, crops, slow-mo, overlays; original speed kept.
- Every clip is probed (playable, duration > 0, video stream); bad files
  are rejected and never enter final.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..probe import probe_video


def extract_clip(src: str, start: float, end: float, dest: str) -> dict:
    dur = max(0.0, end - start)
    if dur <= 0.2:
        return {"ok": False, "error": "non-positive duration"}
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac",
           "-movflags", "+faststart", dest]
    try:
        subprocess.check_output(cmd, text=True, timeout=600)
    except Exception as e:
        return {"ok": False, "error": f"extract: {str(e)[:200]}"}
    try:
        info = probe_video(dest)
    except Exception as e:
        return {"ok": False, "error": f"clip-probe: {str(e)[:200]}"}
    if info.duration <= 0:
        return {"ok": False, "error": "clip-probe: zero duration"}
    return {"ok": True, "duration": round(info.duration, 3),
            "width": info.width, "height": info.height}
