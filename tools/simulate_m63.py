"""M6.3 §13 simulation: apply new M1 acceptance to saved M6 artifacts.

Valid because the rerun would execute BIT-IDENTICAL code paths:
segment.py / view_classifier.py / M2 untouched and deterministic, so
shots/candidates/events would be identical; only the acceptance rule
(gate + guard) changed, which is exactly what is applied here.
Guard sampling reads the same local videos. No downloads.
"""
import json
import shutil
import sys

sys.path.insert(0, ".")

from pathlib import Path

from src.clipper.production.dedup import dedup_clips
from src.clipper.production.merge import merge_clips
from src.clipper.shot_purity import MIN_CENTER_FIELD_CONFIDENCE, assess_homogeneity

JOBS = [
    ("shohei-ohtani", "20260923T100612Z", "av5KQk1HNbc",
     "Shohei_Ohtani_2026_m63.mp4"),
    ("garrett-crochet", "20260923T104950Z", "myyfpqlODso",
     "Garrett_Crochet_2025_m63.mp4"),
]

for slug, run, vid, product in JOBS:
    base = f"output/{slug}/{run}/sources/{vid}"
    out = Path(f"output/recheck/{slug}/{vid}")
    out.mkdir(parents=True, exist_ok=True)
    video = f"{base}/source/original.mp4"
    shots = json.load(open(f"{base}/shots.json", encoding="utf-8"))
    events = json.load(open(f"{base}/events.json", encoding="utf-8"))
    # new acceptance
    keep_ids, guard_veto, gate_drop = set(), [], []
    for s in shots:
        if s["view_class"] != "center_field_good":
            continue
        if s["confidence"] < MIN_CENTER_FIELD_CONFIDENCE:
            gate_drop.append(s["shot_id"])
            continue
        g = assess_homogeneity(video, s["start"], s["end"])
        if g["contaminated"]:
            guard_veto.append(s["shot_id"])
            continue
        keep_ids.add(s["shot_id"])
    ev_kept = [e for e in events if e["source_shot_id"] in keep_ids]
    ev_drop = [e for e in events if e["source_shot_id"] not in keep_ids]
    print("=" * 30, slug)
    print(f"CF shots: {sum(1 for s in shots if s['view_class']=='center_field_good')} "
          f"-> accepted: {len(keep_ids)} (gate-drop {len(gate_drop)}, "
          f"guard-veto {len(guard_veto)})")
    print(f"events: {len(events)} -> {len(ev_kept)}; "
          f"dropped: {[(e['event_id'], e['source_shot_id']) for e in ev_drop]}")
    # clips: reuse existing raw files for kept events
    clips = []
    for e in sorted(ev_kept, key=lambda e: e["clip_start"]):
        src = f"{base}/clips/raw/{e['event_id']}.mp4"
        dest = str(out / f"{e['event_id']}.mp4")
        shutil.copy(src, dest)
        import subprocess
        dur = e["clip_end"] - e["clip_start"]
        clips.append({"clip_id": e["event_id"], "path": dest,
                      "clip_start": e["clip_start"], "clip_end": e["clip_end"],
                      "duration": round(dur, 3)})
    dd = dedup_clips(clips)
    kept = sorted(dd["kept"], key=lambda c: c["clip_start"])
    mg = merge_clips([c["path"] for c in kept], str(out / "final.mp4"))
    print("kept clips:", len(kept), "removed:",
          [(r["clip_id"], r["duplicate_of"]) for r in dd["removed"]],
          "merge:", mg.get("ok"), mg.get("duration"))
    assert mg.get("ok")
    shutil.copy(str(out / "final.mp4"), f"output/recheck/{product}")
    json.dump({"kept_events": [(e["event_id"], e["source_shot_id"]) for e in ev_kept],
               "dropped_events": [(e["event_id"], e["source_shot_id"]) for e in ev_drop],
               "gate_drop": gate_drop, "guard_veto": guard_veto,
               "kept_clips": len(kept),
               "removed": [(r["clip_id"], r["duplicate_of"]) for r in dd["removed"]],
               "duration": mg["duration"], "codec": mg["codec_info"]},
              open(out / "summary.json", "w"), indent=2)
print("SIMULATION DONE")
