"""Stratified pick of ~40 calibration window candidates."""
import json

pool = json.load(open("output/pool_dedup.json", encoding="utf-8"))
# add crochet calib shots (absolute video time unknown -> use file-relative;
# store seg base offset)
crochet_base = {"output/calib_crochet/seg00.mp4": 23 * 60 * 0.30 - 10.0,
                "output/calib_crochet/seg02.mp4": 23 * 60 * 0.70 - 10.0}
for i, f in (("00", "output/calib_crochet/seg00.mp4"),
             ("02", "output/calib_crochet/seg02.mp4")):
    for s in json.load(open(f"output/calib_crochet/m1_{i}/shots.json",
                            encoding="utf-8")):
        pool.append({"base": f"crochet:{f}", "file": f, "video": f,
                     "shot_id": s["shot_id"],
                     "start": round(crochet_base[f] + s["start"], 2),
                     "end": round(crochet_base[f] + s["end"], 2),
                     "seg_start": s["start"], "seg_end": s["end"],
                     "duration": s["duration"], "view_class": s["view_class"],
                     "confidence": s["confidence"],
                     "pitcher": "Garrett Crochet", "source": "redsox-broadcast"})

picks = []


def take(pred, n, tag):
    global pool
    got = [p for p in pool if pred(p)][:n]
    for p in got:
        p["pick_tag"] = tag
    picks.extend(got)
    ids = {(p["video"], p["start"]) for p in got}
    pool = [p for p in pool if (p["video"], p["start"]) not in ids]


is_cf = lambda p: p["view_class"] == "center_field_good"
# long CF per pitcher
for pitcher in ["Garrett Crochet", "yoshinobu-yamamoto", "mason-miller",
                "tarik-skubal", "shohei-ohtani", "Shohei Ohtani"]:
    take(lambda p, ph=pitcher: p["pitcher"] == ph and is_cf(p)
         and p["duration"] >= 4.0, 4, "long-cf")
# dev negatives + FPs + shorts
take(lambda p: p["base"] == "dev:mlb_test_ohtani" and not is_cf(p), 6, "dev-neg")
take(lambda p: p["base"] == "dev:mlb_test_ohtani" and is_cf(p)
     and p["duration"] < 3.0, 4, "dev-short-cf")
take(lambda p: p["base"] == "dev:mlb_test_ohtani" and is_cf(p)
     and p["shot_id"] in ("s002", "s019", "s027"), 3, "dev-fp")
# quiet/short CF elsewhere (dead-ball candidates)
take(lambda p: is_cf(p) and p["duration"] < 2.5, 5, "short-cf")
# WBC couple
take(lambda p: p["source"] == "AfUnCJoD4GU" and is_cf(p), 2, "wbc")

json.dump(picks, open("output/calib_picks.json", "w", encoding="utf-8"), indent=1)
print(len(picks))
from collections import Counter
print(Counter((p["pitcher"], p["pick_tag"]) for p in picks))
