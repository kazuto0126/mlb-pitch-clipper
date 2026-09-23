"""M2 temporal motion signal (shot/clip level only).

Allowed signals: frame difference, optical flow magnitude, temporal
smoothing, center/mound broad-region motion, shot continuity, camera
stability, motion onset/peak/decay/settle, duration constraints.

Forbidden: body-part / joint / landmark localization. The central region
is a *broad static weighting* (suppress batter-box jitter, scoreboard
animation, crowd edges) — not person tracking.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class MotionTrack:
    times: list[float]
    motion: list[float]
    smoothed: list[float]
    fps_sample: float


def grab_frame(path: str, t: float, width: int = 160) -> np.ndarray | None:
    """Single small BGR frame for continuity checks (no analysis)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t * 1000.0))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    h, w = frame.shape[:2]
    scale = width / w
    return cv2.resize(frame, (width, int(h * scale)))


def hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    ha = cv2.calcHist([cv2.cvtColor(a, cv2.COLOR_BGR2HSV)], [0, 1], None,
                      [50, 60], [0, 180, 0, 256])
    hb = cv2.calcHist([cv2.cvtColor(b, cv2.COLOR_BGR2HSV)], [0, 1], None,
                      [50, 60], [0, 180, 0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    return float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))


def _central_mask(h: int, w: int) -> np.ndarray:
    # Broad static region: center 62% width x 72% height.
    # No detection, no tracking — fixed geometry only.
    m = np.zeros((h, w), dtype=np.float32)
    x0, x1 = int(w * 0.19), int(w * 0.81)
    y0, y1 = int(h * 0.10), int(h * 0.82)
    m[y0:y1, x0:x1] = 1.0
    return m


def _mound_mask(h: int, w: int) -> np.ndarray:
    # Scene-layout weighting variant: mound-dominant center kept at full
    # weight; extreme bottom band (catcher/batter routine zone) and side
    # edges down-weighted. Fixed geometry — still no person detection.
    m = _central_mask(h, w)
    m[int(h * 0.75):, :] *= 0.35
    m[:, :int(w * 0.10)] *= 0.5
    m[:, int(w * 0.90):] *= 0.5
    return m


_MASKS = {"standard": _central_mask, "mound": _mound_mask}


def compute_motion(
    path: str,
    start: float,
    end: float,
    sample_fps: float = 10.0,
    width: int = 320,
    smooth_win: float = 0.4,
    flow_weight: float = 0.5,
    mask: str = "standard",
) -> MotionTrack:
    """Frame-diff + Farneback flow magnitude, fused and smoothed."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / sample_fps)))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start * 1000.0))

    frames: list[np.ndarray] = []
    times: list[float] = []
    idx0 = int(start * src_fps)
    idx = idx0
    while True:
        ok = cap.grab()
        if not ok:
            break
        t = idx / src_fps if src_fps > 0 else 0.0
        if t > end:
            break
        if (idx - idx0) % step == 0 and t >= start:
            ok2, frame = cap.retrieve()
            if ok2 and frame is not None:
                g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h0, w0 = g.shape
                scale = width / w0
                g = cv2.resize(g, (width, int(h0 * scale)))
                frames.append(g)
                times.append(t)
        idx += 1
    cap.release()

    if len(frames) < 3:
        return MotionTrack(times, [0.0] * len(times), [0.0] * len(times), sample_fps)
    h, w = frames[0].shape
    mask_fn = _MASKS.get(mask, _central_mask)
    mask_arr = mask_fn(h, w)
    denom = mask_arr.sum() or 1.0

    raw: list[float] = [0.0]
    prev = frames[0]
    for f in frames[1:]:
        diff = cv2.absdiff(f, prev).astype(np.float32)
        d = float((diff * mask_arr).sum() / denom)
        flow = cv2.calcOpticalFlowFarneback(prev, f, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        fl = float((mag * mask_arr).sum() / denom)
        raw.append(d + flow_weight * fl * 10.0)
        prev = f
    # Spike-suppressing smoother (structural): single-frame cut-transition
    # spikes previously survived averaging at delivery-like levels (~0.3-0.5)
    # and also anchored p99. A 0.3s median kills 1-2 frame spikes while
    # preserving sustained (>=0.3s) delivery motion — applied BEFORE
    # normalization so spikes anchor neither the scale nor the shape.
    # Temporal/scene-level denoising only — no body semantics.
    mw = max(3, int(round(0.3 * sample_fps)))
    med = []
    for i in range(len(raw)):
        lo = max(0, i - mw // 2)
        hi = min(len(raw), i + mw // 2 + 1)
        med.append(float(np.median(raw[lo:hi])))

    # normalize 0..1 by near-max of the despiked signal so thresholds stay
    # comparable across shots. (p95 over-amplifies quiet floors; keep p99.)
    mx = float(np.percentile(med, 99)) or 1.0
    raw = [min(1.0, v / mx) for v in raw]
    med = [min(1.0, v / mx) for v in med]

    k = max(1, int(round(smooth_win * sample_fps)))
    sm = []
    for i in range(len(med)):
        lo = max(0, i - k + 1)
        sm.append(sum(med[lo:i + 1]) / (i + 1 - lo))
    return MotionTrack(times, raw, sm, sample_fps)
