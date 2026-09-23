"""Dev helper: print smoothed tracks for given shots (M2 diagnostics)."""
import csv
import sys
from collections import defaultdict

d = defaultdict(list)
with open("output/m1_ohtani_test/diagnostics/temporal_scores.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        d[r["shot_id"]].append((float(r["t"]), float(r["smoothed"])))

for sid in sys.argv[1:]:
    print("===", sid)
    print(" ".join(f"{t:.1f}:{s:.2f}" for t, s in d[sid]))
