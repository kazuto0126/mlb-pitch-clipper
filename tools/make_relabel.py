"""Dense 6-frame sheets for relabel review."""
import json
import subprocess

picks = {n: p for n, p in
         enumerate(json.load(open("output/calib_picks.json", encoding="utf-8")))}
WANT = {"w03": 3, "w07": 7, "w10": 10, "w11": 11, "w41": 41, "w12": 12,
        "w13": 13, "w14": 14}
import os
os.makedirs("output/relabel", exist_ok=True)
for wid, n in WANT.items():
    p = picks[n]
    video = p["video"] if p["base"] == "dev:mlb_test_ohtani" else p["file"]
    t0 = p["start"] if p["base"] == "dev:mlb_test_ohtani" else p["seg_start"]
    t1 = p["end"] if p["base"] == "dev:mlb_test_ohtani" else p["seg_end"]
    outs = []
    for k in range(6):
        t = t0 + (t1 - t0) * (k + 0.5) / 6
        o = f"output/relabel/{wid}_{k}.jpg"
        subprocess.check_output(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, t):.2f}",
             "-i", video, "-frames:v", "1", "-vf", "scale=240:-1", o])
        outs.append(o)
    args = []
    for o in outs:
        args += ["-i", o]
    subprocess.check_output(
        ["ffmpeg", "-y", "-v", "error", *args, "-filter_complex",
         "hstack=inputs=6", f"output/relabel/{wid}.jpg"])
print("done")
