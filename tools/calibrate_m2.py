"""M4.5 calibrator: fixed configs compared under leave-one-pitcher-out.

No fitting inside the loop — configs are fixed a priori; LOPO purely
compares generalization. Selection rule (fixed before seeing results):
maximize mean held-out F1 subject to mean held-out false-window-rate <=
CFG0's + 0.05 AND start_ok rate >= CFG0's. Else keep CFG0.
"""
import json
import sys

sys.path.insert(0, ".")

from src.clipper.events import EventParams, localize
from src.clipper.motion import MotionTrack

import itertools

CONFIGS = {"CFG0-frozen": (EventParams(relative=False), "standard")}
for hi, dc, st, gp, pp in itertools.product(
        (0.35, 0.45), (0.5, 0.7), (0.4, 0.6), (0.3, 0.5), (0.5, 0.8)):
    CONFIGS[f"R-h{int(hi*100)}-d{int(dc*100)}-s{int(st*10)}"
            f"-g{int(gp*10)}-p{int(pp*10)}"] = (
        EventParams(relative=True, high=hi, decay_ratio=dc,
                    min_settle=st, gap_bridge=gp, min_prepared=pp), "standard")


def load_tracks():
    tracks = {}
    for mask in ("standard", "mound"):
        import glob
        for f in glob.glob(f"output/calib_tracks/*_{mask}.json"):
            wid = f.split("\\")[-1].split("_")[0]
            d = json.load(open(f, encoding="utf-8"))
            tracks[(wid, mask)] = MotionTrack(d["times"], d["motion"],
                                              d["smoothed"], 10.0)
    return tracks


def eval_window(w, track, params):
    """Presence-first matching (primary metric).

    complete=true needs >=1 event starting in the first half and ending in
    the last half of the window (proportional bounds: delivery position
    varies with broadcast hold length). complete=false needs 0 events.
    Strict human fields (acceptable_*) are reported as boundary diagnostics,
    not selection gates.
    """
    evs, _ = localize(w["window_id"], w["t0_file"], w["t1_file"], track,
                      params=params)
    dur = w["t1_file"] - w["t0_file"]
    if w["complete_pitch"]:
        for e in evs:
            d = e.to_dict()
            if d["clip_start"] <= w["t0_file"] + 0.5 * dur \
                    and d["clip_end"] >= w["t1_file"] - 0.5 * dur:
                strict_s = d["clip_start"] <= (w["acceptable_clip_start"] or 1e9)
                strict_e = d["clip_end"] >= (w["acceptable_clip_end"] or -1e9)
                return "TP", strict_s, strict_e
        return ("FN-start" if evs else "FN-none"), False, False
    return ("FP" if evs else "TN"), True, True


def metrics(rows):
    tp = sum(1 for r, _, _ in rows if r == "TP")
    fp = sum(1 for r, _, _ in rows if r == "FP")
    fn = sum(1 for r, _, _ in rows if r.startswith("FN"))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    tps = [(s, e) for r, s, e in rows if r == "TP"]
    return {"tp": tp, "fp": fp, "fn": fn, "prec": round(prec, 3),
            "rec": round(rec, 3), "f1": round(f1, 3),
            "strict_start": round(sum(1 for s, _ in tps) / max(1, len(tps)), 3),
            "strict_end": round(sum(1 for _, e in tps) / max(1, len(tps)), 3),
            "false_rate": round(fp / max(1, fp + sum(
                1 for r, _, _ in rows if r == "TN")), 3)}


def main():
    windows = json.load(
        open("validation/calibration_set_v1/windows.jsonl", encoding="utf-8"))
    tracks = load_tracks()
    pitchers = sorted({w["pitcher"] for w in windows})
    report = {}
    for name, (params, mask) in CONFIGS.items():
        per_group, pooled = {}, []
        for held in pitchers:
            rows = [eval_window(w, tracks[(w["window_id"], mask)], params)
                    for w in windows if w["pitcher"] != held]
            held_rows = [eval_window(w, tracks[(w["window_id"], mask)], params)
                         for w in windows if w["pitcher"] == held]
            per_group[held] = {"train": metrics(rows), "held": metrics(held_rows)}
            pooled.extend(held_rows)
        # pooled over held-out predictions only (each window held out once)
        report[name] = {"lopo": per_group, "pooled_heldout": metrics(pooled),
                        "full_fit": metrics(
                            [eval_window(w, tracks[(w["window_id"], mask)], params)
                             for w in windows])}
    json.dump(report, open("output/calib_report.json", "w", encoding="utf-8"), indent=1)
    for name, r in report.items():
        print(name, r["pooled_heldout"], "full:", r["full_fit"])


if __name__ == "__main__":
    main()
