"""Pitch-delivery plausibility of M2 events (M7.7, production only).

M2 normalizes motion per shot, so a batter stepping out, or a catcher and
umpire moving while the pitcher only holds the set, reaches the same
normalized level as a delivery. The center-field view has a fixed layout:
the pitcher stands left of and below the batter, catcher and umpire. A
delivery (stride, arm swing) puts much of the motion in the pitcher's
area; when the pitcher never delivers, the batter's area dominates.

Feature: `p_frac` = motion energy (frame difference + optical flow) in a
fixed pitcher box / (pitcher box + batter box), summed over
[motion_onset, settle_time]. Broad fixed geometry only: no person
detection, tracking, body parts or identity (same signal family as M2).

Evidence (validation/regression_cases/m7_7_delivery_check/): 63 audited
events from 10 sources. No-delivery events with p_frac < 0.44 sit at
0.283-0.420 and every delivered pitch at >= 0.457. Rejects 8/13
no-delivery events and 0/45 delivered pitches; the rest overlap with
deliveries and are left to the operator audit.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

PITCHER_BOX = (0.19, 0.50, 0.35, 0.82)  # x0, x1, y0, y1 (fractions of frame)
BATTER_BOX = (0.50, 0.81, 0.10, 0.55)
DELIVERY_MIN_PFRAC = 0.44
DELIVERY_SHORT_ACTIVE = 1.4  # s; a short event needs a larger pitcher share
DELIVERY_SHORT_MIN_PFRAC = 0.48
SAMPLE_FPS = 10.0
WIDTH = 320


def _box_mean(m: np.ndarray, b: tuple) -> float:
    h, w = m.shape
    return float(m[int(h * b[2]):int(h * b[3]), int(w * b[0]):int(w * b[1])].mean())


def pitcher_share(video: str, onset: float, settle: float) -> float | None:
    """Pitcher-box share of the event's motion energy, or None if unreadable."""
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        return None
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / SAMPLE_FPS)))
    i0 = int(round(onset * src_fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, i0)
    frames, i = [], i0
    while i / src_fps <= settle:
        if not cap.grab():
            break
        if (i - i0) % step == 0:
            ok, f = cap.retrieve()
            if ok:
                g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
                frames.append(cv2.resize(g, (WIDTH, int(g.shape[0] * WIDTH / g.shape[1]))))
        i += 1
    cap.release()
    p = b = 0.0
    for f0, f1 in zip(frames, frames[1:]):
        flow = cv2.calcOpticalFlowFarneback(f0, f1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        e = cv2.absdiff(f1, f0).astype(np.float32) + 5.0 * np.hypot(flow[..., 0], flow[..., 1])
        p += _box_mean(e, PITCHER_BOX)
        b += _box_mean(e, BATTER_BOX)
    return p / (p + b) if p + b > 0 else None


def no_delivery_reason(p_frac: float | None, active: float) -> str | None:
    if p_frac is None:
        return None  # unreadable: keep (never veto on missing evidence)
    if p_frac < DELIVERY_MIN_PFRAC:
        return f"pitcher area quiet (share {p_frac:.3f} < {DELIVERY_MIN_PFRAC})"
    if active < DELIVERY_SHORT_ACTIVE and p_frac < DELIVERY_SHORT_MIN_PFRAC:
        return (f"short event ({active:.2f}s) without pitcher-area motion "
                f"(share {p_frac:.3f} < {DELIVERY_SHORT_MIN_PFRAC})")
    return None


def apply_delivery_veto(m2_dir: str, video: str) -> dict:
    """Move events without a plausible delivery from events.json to
    rejected_events.json (reject_reason no_delivery_suspected).

    Returns {"status", "checked", "vetoed": [event_id, ...]}."""
    d = Path(m2_dir)
    events = json.loads((d / "events.json").read_text(encoding="utf-8"))
    rejected = json.loads((d / "rejected_events.json").read_text(encoding="utf-8"))
    kept, vetoed = [], []
    for e in events:
        share = pitcher_share(video, e["motion_onset"], e["settle_time"])
        e["pitcher_share"] = None if share is None else round(share, 4)
        why = no_delivery_reason(share, e["settle_time"] - e["motion_onset"])
        if why:
            rejected.append({"source_shot_id": e["source_shot_id"],
                             "reject_reason": "no_delivery_suspected",
                             "detail": f"{e['event_id']}: {why}",
                             "event": e})  # times kept for the operator audit
            vetoed.append(e["event_id"])
        else:
            kept.append(e)
    (d / "events.json").write_text(json.dumps(kept, indent=2), encoding="utf-8")
    (d / "rejected_events.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    return {"status": "applied", "checked": len(events), "vetoed": vetoed}
