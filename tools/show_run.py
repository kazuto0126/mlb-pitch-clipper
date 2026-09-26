"""Show latest run manifest results for a slug."""
import glob
import json
import sys

slug = sys.argv[1]
d = sorted(glob.glob(f"output/{slug}/*/run_manifest.json"))[-1]
m = json.load(open(d, encoding="utf-8"))
print(d, m.get("status"), m.get("source_selection_mode"))
for r in m.get("results", []):
    print(r.get("video_id"), r.get("status"), "|",
          (r.get("source_title") or "")[:75], "|", r.get("game_year"),
          r.get("game_year_confidence"), "| shots:", r.get("shot_count"),
          "CF:", r.get("center_field_candidates"), "ev:",
          r.get("complete_events"), "final:", r.get("final_clip_count"),
          r.get("final_duration_sec"), r.get("final_codec"))
