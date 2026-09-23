"""Precompute motion tracks (both masks) for calibration windows."""
import json
import sys

sys.path.insert(0, ".")

from src.clipper.motion import compute_motion

windows = json.load(
    open("validation/calibration_set_v1/windows.jsonl", encoding="utf-8"))
import os
os.makedirs("output/calib_tracks", exist_ok=True)
for w in windows:
    for mask in ("standard", "mound"):
        t = compute_motion(w["video_file"], w["t0_file"], w["t1_file"],
                           mask=mask)
        json.dump({"times": t.times, "motion": t.motion,
                   "smoothed": t.smoothed},
                  open(f"output/calib_tracks/{w['window_id']}_{mask}.json", "w"))
    print(w["window_id"], len(t.times), "samples")
