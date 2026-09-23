"""Show latest preview_stats per video for a slug."""
import glob
import json
import sys

slug = sys.argv[1]
latest = {}
for d in sorted(glob.glob(f"output/preview/{slug}/*/sources/*/preview_stats.json")):
    r = json.load(open(d, encoding="utf-8"))
    latest[r.get("video_id", d)] = r
for vid, r in latest.items():
    print(vid, r.get("source_type"), r.get("preview_status"),
          r.get("preview_decision"), (r.get("preview_error") or "")[:70],
          "CF=", r.get("center_field_shots"), "ev=", r.get("m2_complete_events"))
