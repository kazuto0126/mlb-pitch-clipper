"""M6.3 §13 recheck: local-video production with hardened M1.

Mirrors production/run_source steps 2-7 (normalize already H.264 ->
reuse; frozen M1 with purity gate+guard -> frozen M2 DEFAULT_PARAMS ->
clips -> existing dedup -> merge). No discovery/preview/download.
Writes output/recheck/<slug>/<video_id>/ (M6 artifacts untouched).
"""
import json
import shutil
import sys

sys.path.insert(0, ".")

from pathlib import Path

from src.clipper.pipeline import run_pipeline as run_m1
from src.clipper.production.clips import extract_clip
from src.clipper.production.dedup import dedup_clips
from src.clipper.production.merge import merge_clips
from src.clipper.run_m2 import run_m2

JOBS = [
    ("shohei-ohtani", "av5KQk1HNbc",
     "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc/source/original.mp4",
     "Shohei_Ohtani_2026_m63.mp4"),
    ("garrett-crochet", "myyfpqlODso",
     "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4",
     "Garrett_Crochet_2025_m63.mp4"),
]

for slug, vid, src, product in JOBS:
    out = Path(f"output/recheck/{slug}/{vid}")
    (out / "clips").mkdir(parents=True, exist_ok=True)
    run_m1(src, str(out / "m1"), prefer_clip=True)
    shots = json.load(open(out / "m1/shots.json"))
    cands = json.load(open(out / "m1/candidates.json"))
    run_m2(str(out / "m1"), video=src)
    events = json.load(open(out / "m1/events.json"))
    rejected = json.load(open(out / "m1/rejected_events.json"))
    from collections import Counter
    byr = Counter(r["reject_reason"] for r in rejected)
    byr.update({"m1_" + k: v for k, v in
                Counter(s["reject_reason"] for s in shots
                        if not s["accepted_for_pitch_detection"]).items()})
    events.sort(key=lambda e: e["clip_start"])
    clips = []
    for e in events:
        dest = str(out / "clips" / f"{e['event_id']}.mp4")
        r = extract_clip(src, e["clip_start"], e["clip_end"], dest)
        if r.get("ok"):
            clips.append({"clip_id": e["event_id"], "path": dest,
                          "clip_start": e["clip_start"],
                          "clip_end": e["clip_end"], "duration": r["duration"]})
    dd = dedup_clips(clips)
    kept = sorted(dd["kept"], key=lambda c: c["clip_start"])
    mg = merge_clips([c["path"] for c in kept], str(out / "final_raw.mp4"))
    print(slug, "shots:", len(shots), "CF-cands:", len(cands),
          "events:", len(events), "clips:", len(clips),
          "kept:", len(kept), "merge:", mg.get("ok"), mg.get("duration"))
    print("  reject reasons:", dict(byr))
    print("  removed:", [(r["clip_id"], r["duplicate_of"]) for r in dd["removed"]])
    if mg.get("ok"):
        shutil.copy(str(out / "final_raw.mp4"), f"output/recheck/{product}")
        json.dump({"shots": len(shots), "candidates": len(cands),
                   "events": len(events), "kept": len(kept),
                   "rejects": dict(byr), "duration": mg["duration"],
                   "codec": mg["codec_info"]},
                  open(out / "summary.json", "w"), indent=2)
print("RECHECK DONE")
