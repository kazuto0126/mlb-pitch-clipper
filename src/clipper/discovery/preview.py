"""M3 lightweight preview suitability check — architecture + local-file path.

Concept: for top candidates, uniformly sample a few preview segments and
estimate center-field proportion, average shot duration, rapid-cut rate,
graphic/montage proportion. Want: high center-field + long hold + low cuts.

This milestone implements:
  - preview_stats_for_local_file(): full logic on a LOCAL video file
    (reuses frozen M1 segment.py + view classifier; never M2, never pose).
  - preview_stats_for_url(): STUB — segment-download wiring for M4
    (yt-dlp --download-sections N x 20s), then delegates to the local path.

No body analysis, no pitch mechanics — only "does this look like
long-hold center-field broadcast".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class PreviewStats:
    n_sample_frames: int = 0
    center_field_ratio: float = 0.0
    avg_shot_duration: float = 0.0
    rapid_cut_rate: float = 0.0   # shots < 2s / all shots
    graphic_ratio: float = 0.0
    verdict: str = "unknown"      # suitable | marginal | unsuitable


def preview_stats_for_local_file(path: str, n_samples: int = 12) -> PreviewStats:
    from ..probe import probe_video
    from ..sample import sample_frames
    from ..segment import segment_shots
    from ..view_classifier import load_classifier

    info = probe_video(path)
    shots = segment_shots(path)
    if not shots:
        return PreviewStats()
    durs = [s.duration for s in shots]
    avg_hold = sum(durs) / len(durs)
    rapid = sum(1 for d in durs if d < 2.0) / len(durs)

    clf = load_classifier()
    cf = graphic = 0
    total = 0
    span = max(1.0, info.duration - 1.0)
    for k in range(n_samples):
        t = 0.5 + span * k / n_samples
        frames = sample_frames(path, [t])
        if not frames:
            continue
        r = clf.classify(frames)
        total += 1
        if r.view_class == "center_field_good":
            cf += 1
        if r.view_class == "graphic_bad":
            graphic += 1
    stats = PreviewStats(
        n_sample_frames=total,
        center_field_ratio=round(cf / total, 3) if total else 0.0,
        avg_shot_duration=round(avg_hold, 2),
        rapid_cut_rate=round(rapid, 3),
        graphic_ratio=round(graphic / total, 3) if total else 0.0,
    )
    if stats.center_field_ratio >= 0.5 and avg_hold >= 4.0 and rapid <= 0.4:
        stats.verdict = "suitable"
    elif stats.center_field_ratio >= 0.3 and rapid <= 0.6:
        stats.verdict = "marginal"
    else:
        stats.verdict = "unsuitable"
    return stats


def preview_stats_for_url(url: str, segments: int = 3,
                          segment_sec: int = 20) -> dict:
    """STUB (M4): download N x 20s uniformly-spaced sections via
    yt-dlp --download-sections, run preview_stats_for_local_file on each,
    average the stats. Not wired in M3 (no acquisition this round)."""
    return {"status": "not_implemented_in_m3", "url": url,
            "plan": {"segments": segments, "segment_sec": segment_sec,
                     "then": "preview_stats_for_local_file"}}
