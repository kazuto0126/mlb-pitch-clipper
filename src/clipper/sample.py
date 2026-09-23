"""Frame sampling helper (seek-based, no analysis)."""
from __future__ import annotations

import cv2
from PIL import Image


def sample_frames(path: str, timestamps: list[float], max_dim: int = 512) -> list[Image.Image]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    out: list[Image.Image] = []
    for t in timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t * 1000.0))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        scale = min(1.0, max_dim / max(h, w))
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        out.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    cap.release()
    _ = fps
    return out


def shot_sample_times(start: float, end: float) -> list[float]:
    d = end - start
    if d <= 0:
        return [start]
    return [start + d * 0.2, start + d * 0.5, start + d * 0.8]
