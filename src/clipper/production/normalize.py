"""Media normalization + probing helpers for production."""
from __future__ import annotations

import subprocess

from ..probe import VideoInfo, probe_video


def _pix_fmt(path: str) -> str:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", path],
        text=True, timeout=120)
    return out.strip().splitlines()[0].strip() if out.strip() else ""


def normalize_media(src: str, dest: str) -> dict:
    """Transcode to H.264/yuv420p keeping fps, aspect, speed (no upscale)."""
    info = probe_video(src)
    if info.codec in ("h264", "avc") and _pix_fmt(src) == "yuv420p":
        if src != dest:
            import shutil
            shutil.copyfile(src, dest)
        return {"ok": True, "method": "reuse-original",
                "width": info.width, "height": info.height,
                "fps": round(info.fps, 3)}
    vf = f"scale='min(iw,1280)':-2" if info.width > 1280 else "scale=iw:ih"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", dest]
    try:
        subprocess.check_output(cmd, text=True, timeout=3600)
        out = probe_video(dest)
        return {"ok": True, "method": "transcode-h264",
                "width": out.width, "height": out.height,
                "fps": round(out.fps, 3)}
    except Exception as e:
        return {"ok": False, "error": f"normalize: {str(e)[:200]}"}
