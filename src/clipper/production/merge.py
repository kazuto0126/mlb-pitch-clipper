"""Final merge: chronological concat -> H.264/avc1 yuv420p final.mp4.

Clips are already uniform H.264/yuv420p from extraction, so the concat
demuxer runs -c copy (no extra generation, no speed change, no cards,
no overlays, no audio processing beyond stream copy).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..probe import probe_video


def merge_clips(clip_paths: list[str], dest: str) -> dict:
    if not clip_paths:
        return {"ok": False, "error": "no clips to merge"}
    # absolute paths: the concat demuxer resolves list entries relative to
    # the list file, not the CWD (Windows backslash paths break otherwise).
    lst = Path(dest).parent / "_concat.txt"
    lst.write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n"
                           for p in clip_paths), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
           "-i", str(lst), "-c", "copy", "-movflags", "+faststart", dest]
    try:
        subprocess.check_output(cmd, text=True, timeout=1200)
    except Exception as e:
        return {"ok": False, "error": f"merge: {str(e)[:200]}"}
    try:
        info = probe_video(dest)
    except Exception as e:
        return {"ok": False, "error": f"final-probe: {str(e)[:200]}"}
    if info.duration <= 0:
        return {"ok": False, "error": "final-probe: zero duration"}
    pix = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,pix_fmt,width,height",
         "-of", "csv=p=0", dest], text=True, timeout=120).strip()
    return {"ok": True, "duration": round(info.duration, 3),
            "codec_info": pix, "fps": round(info.fps, 3)}
