"""M6.1 regression: recompute dedup on existing M6 run artifacts (no download)."""
import glob
import json
import sys

sys.path.insert(0, ".")

from src.clipper.production.dedup import dedup_clips

for dd_path in sorted(glob.glob("output/*/202*/sources/*/dedup.json")):
    dd = json.load(open(dd_path, encoding="utf-8"))
    clips = []
    for c in dd["kept"] + dd["removed"]:
        clips.append({k: c[k] for k in ("clip_id", "path", "clip_start",
                                       "clip_end", "duration") if k in c})
    clips.sort(key=lambda c: c.get("clip_start", 0))
    import os
    clips = [c for c in clips if os.path.exists(c.get("path", ""))]
    if not clips:
        print(dd_path, "NO CLIP FILES - skip")
        continue
    out = dedup_clips(clips)
    old_kept = sorted(c["clip_id"] for c in dd["kept"])
    new_kept = sorted(c["clip_id"] for c in out["kept"])
    order_ok = [c["clip_id"] for c in out["kept"]] == sorted(
        [c["clip_id"] for c in out["kept"]],
        key=lambda i: next(x["clip_start"] for x in clips if x["clip_id"] == i))
    print("=" * 30)
    print(dd_path.replace("\\", "/").split("output/")[1].split("/sources")[0])
    print("old kept:", old_kept)
    print("new kept:", new_kept)
    print("removed:", [(r["clip_id"], r["duplicate_of"], r["duplicate_confidence"],
                        r["reason"]) for r in out["removed"]])
    print("flagged:", out["flagged"])
    print("order-chronological:", order_ok)
