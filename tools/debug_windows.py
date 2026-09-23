"""Debug raw events per config on chosen windows."""
import json
import sys

sys.path.insert(0, ".")

from src.clipper.events import EventParams, localize
from src.clipper.motion import MotionTrack

windows = json.load(
    open("validation/calibration_set_v1/windows.jsonl", encoding="utf-8"))
for wid in sys.argv[1:]:
    w = next(x for x in windows if x["window_id"] == wid)
    for mask in ("standard",):
        d = json.load(open(f"output/calib_tracks/{wid}_{mask}.json"))
        t = MotionTrack(d["times"], d["motion"], d["smoothed"], 10.0)
        cfgs = {"WINNER": EventParams(relative=True, high=0.45,
                                      decay_ratio=0.7, min_settle=0.6,
                                      gap_bridge=0.5, min_prepared=0.8)}
        for name, p in cfgs.items():
            evs, rejs = localize(wid, w["t0_file"], w["t1_file"], t, params=p)
            print(wid, mask, name,
                  [(e.clip_start, e.motion_onset, e.motion_peak, e.settle_time, e.clip_end)
                   for e in evs],
                  [r.reject_reason for r in rejs])
