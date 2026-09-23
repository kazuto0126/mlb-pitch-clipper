"""Inspect one preview segment: rejected reasons + s-track + dump frames."""
import csv
import json
import subprocess
import sys

segdir, shot = sys.argv[1], sys.argv[2]
print(json.dumps(json.load(open(segdir + "/rejected_events.json")), indent=1))
rows = list(csv.DictReader(open(segdir + "/diagnostics/temporal_scores.csv")))
sel = [r for r in rows if r["shot_id"] == shot]
print(len(sel), "samples for", shot)
print(" ".join(f"{float(r['t']):.1f}:{float(r['smoothed']):.2f}" for r in sel[::2]))
