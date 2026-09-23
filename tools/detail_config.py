"""Per-window LOPO-heldout detail for one config."""
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from calibrate_m2 import CONFIGS, eval_window, load_tracks

want = sys.argv[1] if len(sys.argv) > 1 else "R-h45-d50-s6-g3"
windows = json.load(
    open("validation/calibration_set_v1/windows.jsonl", encoding="utf-8"))
tracks = load_tracks()
params, mask = CONFIGS[want]
for w in windows:
    from src.clipper.events import localize
    t = tracks[(w["window_id"], mask)]
    evs, rejs = localize(w["window_id"], w["t0_file"], w["t1_file"], t,
                         params=params)
    res = eval_window(w, t, params)[0]
    print(w["window_id"], "pos" if w["complete_pitch"] else "neg", res,
          [(round(e.clip_start, 1), round(e.motion_onset, 1),
            round(e.clip_end, 1)) for e in evs],
          [r.reject_reason for r in rejs])
