"""Shot / scene segmentation.

Order enforced by product spec:
  scene segmentation -> center-field qualification -> (M2) pitch event search.
Forbidden: whole-video motion peaks -> guess pitch. This module knows
nothing about pitching; it only finds shot boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RawShot:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def _hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    return float(cv2.compareHist(a, b, cv2.HISTCMP_CORREL))


def segment_shots(
    path: str,
    sample_fps: float = 5.0,
    hist_thresh: float = 0.55,
    min_shot_sec: float = 0.4,
) -> list[RawShot]:
    """Histogram-based hard-cut detector (deterministic, no ML).

    - Downsamples to sample_fps for speed; boundary timestamps snapped
      to sampled grid (accurate to 1/sample_fps).
    - Uses HSV H-S histogram correlation; hard cut when corr < thresh.
    - Suppresses single-frame flashes by requiring the *next* sampled
      frame to also differ from pre-cut frame.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total / src_fps if src_fps > 0 else 0.0
    step = max(1, int(round(src_fps / sample_fps)))

    prev_hist = None
    prev_idx = 0
    hists: list[tuple[int, np.ndarray]] = []
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok2, frame = cap.retrieve()
            if not ok2 or frame is None:
                idx += 1
                continue
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            hists.append((idx, hist))
        idx += 1
    cap.release()

    if not hists:
        return [RawShot(0.0, duration)]

    cuts = [0.0]
    for k in range(1, len(hists)):
        corr = _hist_corr(hists[k - 1][1], hists[k][1])
        if corr < hist_thresh:
            # flash suppression: next sample must confirm the change
            if k + 1 < len(hists):
                corr_next = _hist_corr(hists[k - 1][1], hists[k + 1][1])
                if corr_next >= hist_thresh:
                    continue
            t = hists[k][0] / src_fps if src_fps > 0 else 0.0
            if t - cuts[-1] >= min_shot_sec:
                cuts.append(t)
    cuts.append(duration)

    shots = [RawShot(start=cuts[i], end=cuts[i + 1]) for i in range(len(cuts) - 1)]
    # merge trailing slivers
    merged: list[RawShot] = []
    for s in shots:
        if s.duration <= 0:
            continue
        if merged and (s.duration < min_shot_sec or merged[-1].duration < min_shot_sec):
            merged[-1] = RawShot(merged[-1].start, s.end)
        else:
            merged.append(s)
    return merged
