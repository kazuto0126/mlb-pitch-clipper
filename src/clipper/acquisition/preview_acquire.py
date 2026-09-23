"""Preview sampling + partial acquisition.

Sampling: 5 x 20s at 10/30/50/70/90% of duration (skips intro/outro by
construction). Short videos (<150s): 3 segments. Very short (<60s): 1.
Original speed, original order, no title cards, no cropping.

Acquisition: yt-dlp --download-sections first; fallback full-then-trim;
method recorded per segment — never claim success falsely.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .schemas import PreviewSegmentPlan

FRACTIONS = (0.10, 0.30, 0.50, 0.70, 0.90)
SEGMENT_SEC = 20.0


def plan_segments(duration: float | None,
                  n: int = 5, seg_len: float = SEGMENT_SEC) -> list[PreviewSegmentPlan]:
    if duration is None or duration <= 0:
        # unknown duration: take from 60s onward, spaced 5 min apart
        return [PreviewSegmentPlan(i, 60.0 + i * 300.0, seg_len)
                for i in range(3)]
    if duration < 60:
        return [PreviewSegmentPlan(0, max(0.0, duration / 2 - seg_len / 2),
                                   min(seg_len, duration))]
    count = 3 if duration < 150 else n
    fracs = [FRACTIONS[i * len(FRACTIONS) // count] for i in range(count)]
    plans = []
    for i, f in enumerate(fracs):
        center = duration * f
        start = max(0.0, min(center - seg_len / 2, duration - seg_len))
        plans.append(PreviewSegmentPlan(i, round(start, 1), seg_len))
    return plans


def _fmt_ts(sec: float) -> str:
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def download_section(url: str, start: float, duration: float,
                     out_path: str) -> PreviewSegmentPlan:
    """Try section download, else full-then-trim. Returns plan with method."""
    plan = PreviewSegmentPlan(0, start, duration)
    end = start + duration
    section = f"*{_fmt_ts(start)}-{_fmt_ts(end)}"
    cmd = ["yt-dlp", url, "-f", "bv*[height<=720]+ba/b[height<=720]/b",
           "--merge-output-format", "mp4", "--download-sections", section,
           "--force-keyframes-at-cuts", "-o", out_path,
           "--quiet", "--no-warnings", "--ignore-errors"]
    try:
        subprocess.check_output(cmd, text=True, timeout=300)
        if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
            plan.method = "yt-dlp-section"
            plan.file = out_path
            return plan
    except Exception as e:
        plan.error = f"section: {str(e)[:150]}"
    # fallback: full download then ffmpeg trim
    try:
        full = out_path.replace(".mp4", ".full.mp4")
        subprocess.check_output(
            ["yt-dlp", url, "-f", "bv*[height<=720]+ba/b[height<=720]/b",
             "--merge-output-format", "mp4", "-o", full,
             "--quiet", "--no-warnings"], text=True, timeout=1200)
        subprocess.check_output(
            ["ffmpeg", "-y", "-v", "error", "-ss", str(start),
             "-i", full, "-t", str(duration), "-c", "copy", out_path],
            text=True, timeout=300)
        Path(full).unlink(missing_ok=True)
        if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
            plan.method = "full-then-trim"
            plan.file = out_path
            return plan
    except Exception as e:
        plan.error += f" | full: {str(e)[:150]}"
    plan.method = "failed"
    return plan


def acquire_preview_segments(url: str, duration: float | None, seg_dir: str,
                             downloader=download_section) -> list[PreviewSegmentPlan]:
    seg_dir_p = Path(seg_dir)
    seg_dir_p.mkdir(parents=True, exist_ok=True)
    out = []
    for p in plan_segments(duration):
        dest = str(seg_dir_p / f"seg{p.index:02d}_{int(p.start)}s.mp4")
        try:
            got = downloader(url, p.start, p.duration, dest)
        except Exception as e:  # downloader must never crash the gate
            got = PreviewSegmentPlan(p.index, p.start, p.duration,
                                     method="failed", error=str(e)[:200])
        got.index = p.index
        out.append(got)
    return out
