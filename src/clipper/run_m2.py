"""M2 runner: candidates.json (M1, accepted only) -> events.json.

Reads M1 output dir. Never touches M1 files; writes new M2 files:
  events.json, rejected_events.json,
  diagnostics/temporal_scores.csv, diagnostics/event_windows/ (.csv per event),
  manifest_m2.json

Usage:
  python -m src.clipper.run_m2 --run output/<run_id> --video <path>
  (video defaults to manifest.json input.path when reachable)
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
from pathlib import Path

from .events import localize
from .motion import compute_motion, grab_frame, hist_corr

# Mid-shot cut guard (whole-shot continuity, allowed signal):
# shot_start / clip_start / clip_end frames must all look like the same
# camera as the peak frame. Catches M1 under-segmentation (missed cut
# inside a candidate) without re-doing view classification.
CONTINUITY_MIN = 0.45


def continuity_ok(video: str, shot_start: float, clip_start: float,
                  peak: float, clip_end: float,
                  thresh: float = CONTINUITY_MIN) -> tuple[bool, float]:
    refs = [shot_start, (clip_start + peak) / 2.0, clip_end]
    f1 = grab_frame(video, peak)
    if f1 is None:
        return True, 1.0
    corrs = []
    for t in refs:
        f0 = grab_frame(video, t)
        corrs.append(hist_corr(f0, f1) if f0 is not None else 1.0)
    return min(corrs) >= thresh, round(min(corrs), 3)


def run_m2(run_dir: str, video: str | None = None) -> dict:
    run = Path(run_dir)
    shots = json.loads((run / "shots.json").read_text(encoding="utf-8"))
    cands = json.loads((run / "candidates.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if video is None:
        video = manifest["input"]["path"]

    cand_ids = {c["shot_id"] for c in cands}
    assert cand_ids, "no M1 candidates"
    for s in shots:
        if s["shot_id"] in cand_ids:
            assert s["view_class"] == "center_field_good" and s["accepted_for_pitch_detection"], \
                f"M2 input violates M1 contract: {s['shot_id']}"

    ev_dir = run / "diagnostics" / "event_windows"
    ev_dir.mkdir(parents=True, exist_ok=True)

    events: list[dict] = []
    rejected: list[dict] = []
    ev_n = 1
    with open(run / "diagnostics" / "temporal_scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["shot_id", "t", "motion", "smoothed"])
        for c in cands:
            track = compute_motion(video, c["start"], c["end"])
            for t, m, s_ in zip(track.times, track.motion, track.smoothed):
                w.writerow([c["shot_id"], round(t, 3), round(m, 4), round(s_, 4)])
            evs, rejs = localize(c["shot_id"], c["start"], c["end"], track,
                                 start_count=ev_n)
            for e in evs:
                # continuity: same camera across the whole event window?
                ok, corr = continuity_ok(video, c["start"], e.clip_start,
                                         e.motion_peak, e.clip_end)
                if not ok:
                    rejected.append({"source_shot_id": c["shot_id"],
                                     "reject_reason": "shot_discontinuity",
                                     "detail": f"{e.event_id} min_corr={corr}"})
                    continue
                events.append(e.to_dict())
                ev_n += 1
                with open(ev_dir / f"{e.event_id}_{e.source_shot_id}.csv",
                           "w", newline="", encoding="utf-8") as ef:
                    ew = csv.writer(ef)
                    ew.writerow(["t", "motion", "smoothed", "in_clip"])
                    for t, m, s_ in zip(track.times, track.motion, track.smoothed):
                        ew.writerow([round(t, 3), round(m, 4), round(s_, 4),
                                     int(e.clip_start <= t <= e.clip_end)])
            rejected.extend(r.to_dict() for r in rejs)

    events.sort(key=lambda e: e["clip_start"])
    (run / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    (run / "rejected_events.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")

    by_reason: dict[str, int] = {}
    for r in rejected:
        by_reason[r["reject_reason"]] = by_reason.get(r["reject_reason"], 0) + 1
    m2 = {
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "milestone": 2,
        "input_candidates": len(cands),
        "complete_events": len(events),
        "rejected_windows": len(rejected),
        "reject_by_reason": by_reason,
        "notes": "motion_peak is a temporal anchor, not a release/biomechanics point.",
    }
    (run / "manifest_m2.json").write_text(json.dumps(m2, indent=2), encoding="utf-8")
    return m2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--video", default=None)
    args = ap.parse_args()
    print(json.dumps(run_m2(args.run, args.video), indent=2))


if __name__ == "__main__":
    main()
