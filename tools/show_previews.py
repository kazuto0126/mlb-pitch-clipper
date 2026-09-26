"""Show all preview records for a slug (all runs)."""
import glob
import json
import sys

slug = sys.argv[1]
for d in sorted(glob.glob(f"output/preview/{slug}/*/sources/*/preview_stats.json")):
    r = json.load(open(d, encoding="utf-8"))
    tag = d.replace("\\", "/").split(f"preview/{slug}/")[1][:17]
    print(tag, r.get("video_id"), r.get("preview_status"),
          r.get("preview_decision"), "CF=", r.get("center_field_shots"),
          "ev=", r.get("m2_complete_events"),
          (r.get("preview_error") or "")[:60])
