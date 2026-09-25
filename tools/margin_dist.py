"""Margin distribution over all production CF shots + event-shot margins."""
import glob
import json
import sys

sys.path.insert(0, ".")

NON_CF = ["closeup_bad", "batter_bad", "field_bad", "graphic_bad",
          "other_bad", "side_fullbody_acceptable"]

for d in sorted(glob.glob("output/*/202*/sources/*/shots.json")):
    tag = d.replace("\\", "/").split("output/")[1].split("/sources")[0]
    shots = json.load(open(d, encoding="utf-8"))
    cf = [s for s in shots if s["view_class"] == "center_field_good"]
    ev = json.load(open(d.replace("shots.json", "events.json")))
    evshots = {e["source_shot_id"] for e in ev}
    bands = {"<0.1": 0, "0.1-0.3": 0, "0.3-0.4": 0, "0.4-0.6": 0, ">=0.6": 0}
    mid = []
    evlow = []
    for s in cf:
        sc = s.get("scores") or {}
        m = sc.get("center_field_good", 0) - max(sc.get(k, 0) for k in NON_CF)
        if m < 0.1:
            bands["<0.1"] += 1
        elif m < 0.3:
            bands["0.1-0.3"] += 1
        elif m < 0.4:
            bands["0.3-0.4"] += 1
            mid.append((s["shot_id"], round(s["start"], 1), round(s["end"], 1),
                        round(s["confidence"], 3), s["shot_id"] in evshots))
        elif m < 0.6:
            bands["0.4-0.6"] += 1
            mid.append((s["shot_id"], round(s["start"], 1), round(s["end"], 1),
                        round(s["confidence"], 3), s["shot_id"] in evshots))
        else:
            bands[">=0.6"] += 1
        if s["shot_id"] in evshots and m < 0.4:
            evlow.append((s["shot_id"], round(m, 3)))
    print(tag, "CF:", len(cf), bands)
    print("  0.3-0.6 band:", mid)
    print("  event-shots margin<0.4:", evlow)
