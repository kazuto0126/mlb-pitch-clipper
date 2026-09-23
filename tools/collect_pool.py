"""Collect M1 shots from dev run + all M4 preview segs into a window pool."""
import glob
import json
import re

pool = []
# dev run (absolute times already)
for s in json.load(open("output/m1_ohtani_test/shots.json", encoding="utf-8")):
    pool.append({
        "base": "dev:mlb_test_ohtani", "file": None,
        "video": r"C:\Users\lingz\AppData\Local\Temp\opencode\mlb_test_ohtani.mp4",
        "shot_id": s["shot_id"], "start": s["start"], "end": s["end"],
        "duration": s["duration"], "view_class": s["view_class"],
        "confidence": s["confidence"],
        "pitcher": "Shohei Ohtani", "source": "dodgers-snla",
    })
# preview segs: seg-relative -> absolute via filename offset
for shots_path in glob.glob("output/preview/*/202*/sources/*/m1m2/seg*/shots.json"):
    norm = shots_path.replace("\\", "/")
    m = re.search(r"sources/([^/]+)/m1m2/(seg\d+)/shots.json", norm)
    if not m:
        continue
    vid, seg = m.group(1), m.group(2)
    segfiles = glob.glob(f"output/preview/*/202*/sources/{vid}/segments/{seg}_*.mp4")
    if not segfiles:
        continue
    segfile = segfiles[0]
    off = float(re.search(r"_(\d+)s\.mp4", segfile.replace("\\", "/")).group(1))
    slug = norm.split("output/preview/")[1].split("/")[0]
    for s in json.load(open(shots_path, encoding="utf-8")):
        pool.append({
            "base": f"preview:{vid}/{seg}", "file": segfile, "video": segfile,
            "shot_id": s["shot_id"], "start": round(off + s["start"], 2),
            "end": round(off + s["end"], 2),
            "seg_start": s["start"], "seg_end": s["end"],
            "duration": s["duration"], "view_class": s["view_class"],
            "confidence": s["confidence"],
            "pitcher": slug, "source": vid,
        })

json.dump(pool, open("output/pool.json", "w", encoding="utf-8"), indent=1)
print(len(pool), "windows in pool")
from collections import Counter
print(Counter((p["pitcher"], p["view_class"]) for p in pool))
