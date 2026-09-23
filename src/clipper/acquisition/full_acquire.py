"""Full acquisition (M5): complete selected source download.

- yt-dlp only, no DRM circumvention, no login/paywalled content handling.
- Per-source failure never crashes the run (returns status dict).
- Post-download media must probe; original metadata saved.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..probe import probe_video


def _build_cmd(url: str, out: Path) -> list[str]:
    # NOTE: never add --print here: yt-dlp skips the download and only
    # prints (exit 0, no file). Metadata already comes from discovery.
    return ["yt-dlp", url, "-f", "bv*[height<=720]+ba/b[height<=720]/b",
            "--merge-output-format", "mp4", "-o", str(out),
            "--quiet", "--no-warnings", "--no-playlist"]


def acquire_full(url: str, out_path: str, meta_path: str | None = None,
                 timeout: int = 1800) -> dict:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = _build_cmd(url, out)
    try:
        subprocess.check_output(cmd, text=True, timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": f"download: {str(e)[:200]}"}
    if not out.exists() or out.stat().st_size == 0:
        return {"ok": False, "error": "download: empty/missing file"}
    try:
        info = probe_video(str(out))
    except Exception as e:
        return {"ok": False, "error": f"probe: {str(e)[:200]}"}
    if meta_path:
        meta = {"path": str(out), "bytes": out.stat().st_size,
                "width": info.width, "height": info.height,
                "fps": round(info.fps, 3), "duration": round(info.duration, 3),
                "codec": info.codec}
        Path(meta_path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "method": "yt-dlp-full",
            "duration": round(info.duration, 3)}
