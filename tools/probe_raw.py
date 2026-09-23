"""Probe: does the RAW (unnormalized) fused motion separate delivers vs rest?"""
import json
import sys

sys.path.insert(0, ".")
import cv2
import numpy as np

from src.clipper.motion import _central_mask


def raw_series(path, start, end, sample_fps=10.0, width=320):
    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / sample_fps)))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start * 1000.0))
    frames, idx0, idx = [], int(start * src_fps), int(start * src_fps)
    while True:
        if not cap.grab():
            break
        t = idx / src_fps if src_fps > 0 else 0.0
        if t > end:
            break
        if (idx - idx0) % step == 0 and t >= start:
            ok, fr = cap.retrieve()
            if ok and fr is not None:
                g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                h0, w0 = g.shape
                g = cv2.resize(g, (width, int(h0 * width / w0)))
                frames.append(g)
        idx += 1
    cap.release()
    h, w = frames[0].shape
    mask = _central_mask(h, w)
    den = mask.sum()
    out, prev = [], frames[0]
    for f in frames[1:]:
        d = float((cv2.absdiff(f, prev).astype(np.float32) * mask).sum() / den)
        flow = cv2.calcOpticalFlowFarneback(prev, f, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        fl = float((mag * mask).sum() / den)
        out.append(d + 0.5 * fl * 10.0)
        prev = f
    return out


windows = json.load(
    open("validation/calibration_set_v1/windows.jsonl", encoding="utf-8"))
for w in windows:
    raw = raw_series(w["video_file"], w["t0_file"], w["t1_file"])
    a = np.array(raw)
    print(w["window_id"], "pos" if w["complete_pitch"] else "neg",
          "med", round(float(np.median(a)), 2),
          "p90", round(float(np.percentile(a, 90)), 2),
          "max", round(float(a.max()), 2))
