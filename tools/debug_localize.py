"""Debug localize() on a real track CSV."""
import csv
import sys

sys.path.insert(0, ".")


from src.clipper.events import localize
from src.clipper.motion import MotionTrack

segdir, shot = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(segdir + "/diagnostics/temporal_scores.csv")))
sel = [r for r in rows if r["shot_id"] == shot]
ts = [float(r["t"]) for r in sel]
sm = [float(r["smoothed"]) for r in sel]
mo = [float(r["motion"]) for r in sel]
track = MotionTrack(ts, mo, sm, 10.0)
s = __import__("json").load(open(segdir + "/shots.json"))
info = next(x for x in s if x["shot_id"] == shot)
evs, rejs = localize(shot, info["start"], info["end"], track)
print("events:", [e.to_dict() for e in evs])
print("rejected:", [r.to_dict() for r in rejs])
print("max sm:", max(sm), "n:", len(sm))
