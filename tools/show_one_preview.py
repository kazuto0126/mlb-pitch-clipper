"""Show one source's latest preview record by video id substring."""
import glob
import json
import sys

want = sys.argv[1]
best = None
for d in sorted(glob.glob("output/preview/*/202*/sources/*/preview_stats.json")):
    r = json.load(open(d, encoding="utf-8"))
    if want in r.get("video_id", ""):
        best = (d, r)
d, r = best
print(d)
print(json.dumps({k: r.get(k) for k in
                  ["video_id", "source_type", "preview_status", "preview_decision",
                   "preview_segment_count", "preview_duration_sec", "shot_count",
                   "center_field_shots", "center_field_ratio", "m2_complete_events",
                   "m2_rejected_events", "complete_events_per_minute",
                   "complete_event_yield", "incomplete_rate", "discontinuity_rate",
                   "reject_by_reason", "reasons"]}, indent=1))
