"""Dump CF confidence extremes per production source."""
import glob
import json

for d in sorted(glob.glob("output/*/202*/sources/*/shots.json")):
    shots = json.load(open(d, encoding="utf-8"))
    cf = sorted([s for s in shots if s["view_class"] == "center_field_good"],
                key=lambda s: s["confidence"])
    tag = d.replace("\\", "/").split("output/")[1].split("/sources")[0]
    print("=" * 20, tag)
    print(" CF n=", len(cf), "of", len(shots))
    print(" lowest5:", [(s["shot_id"], round(s["start"], 1),
                         round(s["end"], 1), s["confidence"]) for s in cf[:5]])
    print(" highest5:", [(s["shot_id"], round(s["start"], 1),
                          round(s["end"], 1), s["confidence"]) for s in cf[-5:]])
