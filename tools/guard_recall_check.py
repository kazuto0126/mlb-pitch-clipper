"""Guard veto check on every event-producing shot (recall impact)."""
import json
import sys

sys.path.insert(0, ".")

from src.clipper.shot_purity import assess_homogeneity

JOBS = [
    ("output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw", "source/original.mp4"),
    ("output/yoshinobu-yamamoto/20260923T005044Z/sources/dYa3bhFPfJ8", "source/original.mp4"),
    ("output/paul-skenes/20260923T095225Z/sources/q2dSaXzowlw", "source/original.mp4"),
    ("output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc", "source/original.mp4"),
    ("output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso", "source/original.mp4"),
    ("output/mason-miller/20260923T111351Z/sources/q7ndAVBppQQ", "source/original.mp4"),
]
for base, rel in JOBS:
    ev = json.load(open(base + "/events.json"))
    sh = {s["shot_id"]: s for s in json.load(open(base + "/shots.json"))}
    vetoed = []
    for e in ev:
        s = sh[e["source_shot_id"]]
        g = assess_homogeneity(base + "/" + rel, s["start"], s["end"])
        if g["contaminated"]:
            vetoed.append(e["source_shot_id"])
    print(base.split("/")[1], "events:", len(ev), "guard-vetoed:", vetoed)
