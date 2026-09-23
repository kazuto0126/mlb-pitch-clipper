"""Print latest preview record per video_id."""
import glob
import json

latest = {}
for d in sorted(glob.glob("output/preview/*/202*/sources/*/preview_stats.json")):
    r = json.load(open(d, encoding="utf-8"))
    latest[r.get("video_id", d)] = r
for vid, r in latest.items():
    print("-" * 100)
    print(f"{vid} | {r.get('title', '')[:65]}")
    print(f"  type={r.get('source_type')} ctx={r.get('competition_context')} "
          f"status={r.get('preview_status')} decision={r.get('preview_decision')}")
    print(f"  segs={r.get('preview_segment_count')} dur={r.get('preview_duration_sec')}s "
          f"shots={r.get('shot_count')} edge_skip={r.get('edge_skipped_shots')} "
          f"CF={r.get('center_field_shots')} cf_ratio={r.get('center_field_ratio')}")
    print(f"  events={r.get('m2_complete_events')} rejected={r.get('m2_rejected_events')} "
          f"yield={r.get('complete_event_yield')} per_min={r.get('complete_events_per_minute')} "
          f"incomplete={r.get('incomplete_rate')} disc={r.get('discontinuity_rate')}")
    print(f"  reasons={r.get('reject_by_reason')} | {r.get('reasons')}")
