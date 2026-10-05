"""Preview sampling + partial acquisition.

Sampling: 5 x 20s at 10/30/50/70/90% of duration (skips intro/outro by
construction). Short videos (<150s): 3 segments. Very short (<60s): 1.
Original speed, original order, no title cards, no cropping.

Acquisition: yt-dlp --download-sections first (retried once on transient
failure, M7.2); fallback full-then-trim; method recorded per segment —
never claim success falsely.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .schemas import PreviewSegmentPlan
from .ytdlp import cleanup_partials, js_runtime_args, run_download

FRACTIONS = (0.10, 0.30, 0.50, 0.70, 0.90)
SEGMENT_SEC = 20.0
SECTION_ATTEMPTS = 2


def plan_segments(duration: float | None,
                  n: int = 5, seg_len: float = SEGMENT_SEC,
                  fractions: tuple = FRACTIONS) -> list[PreviewSegmentPlan]:
    if duration is None or duration <= 0:
        # unknown duration: take from 60s onward, spaced 5 min apart
        return [PreviewSegmentPlan(i, 60.0 + i * 300.0, seg_len)
                for i in range(3)]
    if duration < 60:
        return [PreviewSegmentPlan(0, max(0.0, duration / 2 - seg_len / 2),
                                   min(seg_len, duration))]
    count = 3 if duration < 150 else n
    fracs = [fractions[i * len(fractions) // count] for i in range(count)]
    plans = []
    for i, f in enumerate(fracs):
        center = duration * f
        start = max(0.0, min(center - seg_len / 2, duration - seg_len))
        plans.append(PreviewSegmentPlan(i, round(start, 1), seg_len))
    return plans


def plan_expansion(duration: float | None,
                   existing: list[tuple[float, float]],
                   fractions: tuple,
                   seg_len: float = SEGMENT_SEC) -> list[PreviewSegmentPlan]:
    """Deterministic extra segments at new fractions, skipping anything
    overlapping already-downloaded ranges (1s tolerance)."""
    if duration is None or duration <= 0:
        base = max((e for _, e in existing), default=60.0)
        return [PreviewSegmentPlan(i, base + 60.0 + i * 300.0, seg_len)
                for i in range(len(fractions))]
    plans = []
    for i, f in enumerate(fractions):
        center = duration * f
        start = max(0.0, min(center - seg_len / 2, duration - seg_len))
        end = start + seg_len
        if any(s < end + 1.0 and start < e + 1.0 for s, e in existing):
            continue
        plans.append(PreviewSegmentPlan(i, round(start, 1), seg_len))
    return plans


def _fmt_ts(sec: float) -> str:
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def download_section(url: str, start: float, duration: float,
                     out_path: str, runner=subprocess.run,
                     sleep=time.sleep) -> PreviewSegmentPlan:
    """Try section download, else full-then-trim. Returns plan with method.

    The cheap section download is retried (transient HTTP 403) before
    falling back; the full-then-trim fallback downloads the whole source,
    so it gets a single attempt and its leftovers are removed on failure."""
    plan = PreviewSegmentPlan(0, start, duration)
    end = start + duration
    section = f"*{_fmt_ts(start)}-{_fmt_ts(end)}"
    out = Path(out_path)
    cmd = ["yt-dlp", url, "-f", "bv*[height<=720]+ba/b[height<=720]/b",
           "--merge-output-format", "mp4", "--download-sections", section,
           "--force-keyframes-at-cuts", "-o", out_path,
           "--quiet", "--no-warnings", "--ignore-errors", *js_runtime_args()]
    ok, attempts, err = run_download(cmd, out, 300, attempts=SECTION_ATTEMPTS,
                                     runner=runner, sleep=sleep)
    if ok:
        plan.method = "yt-dlp-section"
        plan.file = out_path
        return plan
    plan.error = f"section: {err} (attempts={attempts})"
    cleanup_partials(out)
    # fallback: full download then ffmpeg trim
    full = Path(out_path.replace(".mp4", ".full.mp4"))
    ok, _, err = run_download(
        ["yt-dlp", url, "-f", "bv*[height<=720]+ba/b[height<=720]/b",
         "--merge-output-format", "mp4", "-o", str(full),
         "--quiet", "--no-warnings", *js_runtime_args()],
        full, 1200, attempts=1, runner=runner, sleep=sleep)
    if ok:
        try:
            subprocess.check_output(
                ["ffmpeg", "-y", "-v", "error", "-ss", str(start),
                 "-i", str(full), "-t", str(duration), "-c", "copy", out_path],
                text=True, timeout=300)
        except Exception as e:
            err = f"trim: {str(e)[:150]}"
        full.unlink(missing_ok=True)
        if out.exists() and out.stat().st_size > 0:
            plan.method = "full-then-trim"
            plan.file = out_path
            return plan
    plan.error += f" | full: {err}"
    cleanup_partials(full)
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
