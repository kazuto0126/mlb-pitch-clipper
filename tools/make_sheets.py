"""Contact sheets (3 frames) per calibration pick for human labeling."""
import json
import subprocess

picks = json.load(open("output/calib_picks.json", encoding="utf-8"))
import os
os.makedirs("output/calib_sheets", exist_ok=True)
for n, p in enumerate(picks):
    if p["base"] == "dev:mlb_test_ohtani":
        video = p["video"]
        t0, t1 = p["start"], p["end"]
    else:
        video = p["file"]
        t0, t1 = p["seg_start"], p["seg_end"]
    if t1 - t0 < 1.2:
        ts = [t0 + (t1 - t0) / 2]
    else:
        ts = [t0 + 0.4, (t0 + t1) / 2, t1 - 0.4]
    outs = []
    for k, t in enumerate(ts):
        o = f"output/calib_sheets/w{n:02d}_{k}.jpg"
        subprocess.check_output(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, t):.2f}",
             "-i", video, "-frames:v", "1", "-vf", "scale=320:-1", o])
        outs.append(o)
    if len(outs) == 3:
        subprocess.check_output(
            ["ffmpeg", "-y", "-v", "error", *[x for pair in
             zip(["-i"] * 3, outs) for x in pair],
             "-filter_complex", "hstack=inputs=3",
             f"output/calib_sheets/w{n:02d}.jpg"])
print("done", len(picks))
