"""Veto volume: edge density on all margin<0.4 CF shots (production runs)."""
import glob
import json
import sys

sys.path.insert(0, ".")

import cv2

from src.clipper.motion import grab_frame

NON_CF = ["closeup_bad", "batter_bad", "field_bad", "graphic_bad",
          "other_bad", "side_fullbody_acceptable"]


def edge(f):
    a = cv2.resize(f, (256, 144))
    a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    return round(float(cv2.Canny(gray, 80, 160).mean() / 255.0), 4)


for d in sorted(glob.glob("output/*/202*/sources/*/shots.json")):
    base = d.replace("shots.json", "")
    tag = d.replace("\\", "/").split("output/")[1].split("/sources")[0]
    vids = glob.glob(base + "source/original.mp4") or glob.glob(base + "../*.mp4")
    # resolve actual video: production layout has source/original.mp4
    import os
    cand = [base + "source/original.mp4", base + "m1/../x"]
    video = next((c for c in [base + "source/original.mp4"] if os.path.exists(c)), None)
    if video is None:  # dev run layout
        video = r"C:\Users\lingz\AppData\Local\Temp\opencode\mlb_test_ohtani.mp4"
    shots = json.load(open(d, encoding="utf-8"))
    ev = set()
    try:
        ev = {e["source_shot_id"] for e in json.load(open(base + "events.json"))}
    except FileNotFoundError:
        pass
    n_cf = n_low = n_veto = 0
    veto_ev = []
    for s in shots:
        if s["view_class"] != "center_field_good":
            continue
        n_cf += 1
        sc = s.get("scores") or {}
        m = sc.get("center_field_good", 0) - max(sc.get(k, 0) for k in NON_CF)
        if m >= 0.4:
            continue
        n_low += 1
        f = grab_frame(video, (s["start"] + s["end"]) / 2)
        e = edge(f) if f is not None else 1.0
        if e < 0.10:
            n_veto += 1
            if s["shot_id"] in ev:
                veto_ev.append(s["shot_id"])
    print(f"{tag} CF={n_cf} margin<0.4:{n_low} vetoed:{n_veto} vetoed-events:{veto_ev}")
