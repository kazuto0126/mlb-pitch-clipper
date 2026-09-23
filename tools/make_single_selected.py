"""Assemble a single-candidate selected_sources.json from a discovery pool."""
import glob
import json
import sys

slug, wanted, out = sys.argv[1], sys.argv[2], sys.argv[3]
cands = sorted(glob.glob(f"output/discovery/{slug}/*/candidates.json"))[-1]
allc = json.load(open(cands, encoding="utf-8"))
hit = next(c for c in allc if c["video_id"] == wanted)
json.dump([hit], open(out, "w", encoding="utf-8"), indent=2)
print(hit["source_type"], (hit["duration"] or 0) // 60, "min|", hit["title"][:80])
