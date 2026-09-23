"""Conservative duplicate cleanup (M5).

Policy: false deletion is worse than a missed duplicate. Only HIGH
confidence pairs are merged. Signals allowed: temporal overlap,
frame perceptual-hash similarity, durations, source chronology.
Never declare duplicates from "same camera angle" alone.

- dHash (64-bit, OpenCV/PIL only, no new deps), 8 uniform samples/clip.
- Pair is duplicate iff mean frame Hamming <= 8 AND durations within 25%.
- Overlap in source time (shouldn't happen from M2): keep the longer.
- Winner: longer clip; tie -> earlier clip_start. Loser recorded with
  duplicate_confidence = 1 - mean_hamming/64.
- Replay: no independent detector this round -> replay_rejected = 0 and
  replay_status = "uncertain" unless a hash duplicate was found
  (counted as duplicate, not replay).
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

N_SAMPLES = 8
HAMMING_MAX = 8
DUR_TOL = 0.25
# Global conservative time window (seconds): hash-only auto-delete is
# allowed iff the two windows are this close. Rationale: MLB broadcast
# replays air inside the same at-bat or the next (~15-60s); pairs 90s+
# apart span multiple PAs and are different pitches despite fixed-camera
# similarity. M6 evidence: plausible live/replay gaps 4.7/14.0/26.1/40.1s
# kept-deletable; 90.2/355/371s blocked. One global value, never per-pitcher.
MAX_DUPLICATE_GAP_SEC = 60.0


def dhash(img: Image.Image) -> int:
    g = img.convert("L").resize((9, 8), Image.BILINEAR)
    px = np.asarray(g, dtype=np.int16)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def clip_hashes(path: str, n: int = N_SAMPLES) -> list[int] | None:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if count <= 0:
        cap.release()
        return None
    out = []
    for k in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(count * (k + 0.5) / n))
        ok, fr = cap.read()
        if not ok or fr is None:
            cap.release()
            return None
        out.append(dhash(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))))
    cap.release()
    return out


def _ham(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def time_gap(a: dict, b: dict) -> float | None:
    """Gap between clip windows (start_later - end_earlier); None when
    timestamps are missing ( -> never auto-delete)."""
    try:
        s0, e0, s1, e1 = (float(a["clip_start"]), float(a["clip_end"]),
                          float(b["clip_start"]), float(b["clip_end"]))
    except (KeyError, TypeError, ValueError):
        return None
    if e0 <= s1:
        return s1 - e0
    if e1 <= s0:
        return s0 - e1
    return 0.0  # overlapping


def dedup_clips(clips: list[dict],
                max_gap: float = MAX_DUPLICATE_GAP_SEC) -> dict:
    """clips: [{clip_id, path, clip_start, clip_end, duration}].
    Returns {kept:[...], removed:[...], flagged:[...]}.
    flagged = high-similarity pairs beyond the temporal guard
    (duplicate_status = visually_similar_but_temporally_distant, both kept).
    Sorted output keeps source chronological order (input assumed sorted)."""
    sigs = {c["clip_id"]: clip_hashes(c["path"]) for c in clips}
    removed_ids: dict[str, dict] = {}
    flagged: list[dict] = []
    for i in range(len(clips)):
        for j in range(i + 1, len(clips)):
            a, b = clips[i], clips[j]
            if a["clip_id"] in removed_ids or b["clip_id"] in removed_ids:
                continue
            gap = time_gap(a, b)
            # temporal overlap safety (same source): keep longer.
            # Strict overlap only: merely touching windows are distinct.
            # Missing timestamps -> skip overlap handling (kept safe below).
            try:
                overlap = float(a["clip_end"]) > float(b["clip_start"]) and float(
                    b["clip_end"]) > float(a["clip_start"])
            except (KeyError, TypeError, ValueError):
                overlap = False
            if overlap:
                loser = a if a["duration"] < b["duration"] else b
                winner = b if loser is a else a
                removed_ids[loser["clip_id"]] = {
                    **loser, "duplicate_of": winner["clip_id"],
                    "duplicate_confidence": 1.0, "reason": "time-overlap"}
                continue
            ha, hb = sigs[a["clip_id"]], sigs[b["clip_id"]]
            if not ha or not hb:
                continue
            mean_h = sum(_ham(x, y) for x, y in zip(ha, hb)) / len(ha)
            dur_ok = abs(a["duration"] - b["duration"]) / max(a["duration"],
                                                             b["duration"], 1e-6) <= DUR_TOL
            if mean_h <= HAMMING_MAX and dur_ok:
                if gap is None or gap > max_gap:
                    # high similarity but temporally distant (or timeless):
                    # KEEP BOTH, record only.
                    flagged.append({
                        "clip_a": a["clip_id"], "clip_b": b["clip_id"],
                        "similarity": round(1 - mean_h / 64, 3),
                        "timestamp_gap_sec": gap,
                        "duplicate_status": "visually_similar_but_temporally_distant",
                    })
                    continue
                loser = a if a["duration"] < b["duration"] else b
                winner = b if loser is a else a
                removed_ids[loser["clip_id"]] = {
                    **loser, "duplicate_of": winner["clip_id"],
                    "duplicate_confidence": round(1 - mean_h / 64, 3),
                    "reason": "near-identical-frames"}
    # transitive resolution: duplicate_of must reference a kept clip
    kept_ids = {c["clip_id"] for c in clips if c["clip_id"] not in removed_ids}
    for cid, rec in removed_ids.items():
        seen = {cid}
        while rec["duplicate_of"] not in kept_ids and rec["duplicate_of"] in removed_ids:
            nxt = removed_ids[rec["duplicate_of"]]["duplicate_of"]
            if nxt in seen:
                break
            seen.add(nxt)
            rec["duplicate_of"] = nxt
    kept = [c for c in clips if c["clip_id"] not in removed_ids]
    return {"kept": kept, "removed": list(removed_ids.values()), "flagged": flagged}
