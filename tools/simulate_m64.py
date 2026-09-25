"""M6.4 §10: apply new acceptance to saved artifacts, rebuild finals.

M1 segmentation/classification + M2 untouched and deterministic, so saved
shots/events are bit-identical to a rerun; only acceptance changes:
gate (saved conf) + transition guard + homogeneous-closeup veto
(margin from saved scores + fresh single-frame edge reads).
No downloads. Finals rebuilt from existing raw clips.
"""
import json
import shutil
import sys

sys.path.insert(0, ".")

from pathlib import Path

from src.clipper.production.dedup import dedup_clips
from src.clipper.production.merge import merge_clips
from src.clipper.shot_purity import (MIN_CENTER_FIELD_CONFIDENCE,
                                     assess_closeup, assess_homogeneity,
                                     class_margin)

JOBS = [
    ("shohei-ohtani", "20260923T100612Z", "av5KQk1HNbc", "Shohei_Ohtani_2026_m64.mp4"),
    ("garrett-crochet", "20260923T104950Z", "myyfpqlODso", "Garrett_Crochet_2025_m64.mp4"),
    ("yoshinobu-yamamoto", "20260923T005044Z", "Q8Bl2X4VKuw", "Yoshinobu_Yamamoto_2025_m64.mp4"),
]


def accept(shot, video):
    if shot["view_class"] != "center_field_good":
        return False, "non-cf"
    if shot["confidence"] < MIN_CENTER_FIELD_CONFIDENCE:
        return False, "low_view_confidence"
    sc = {k: round(v, 4) for k, v in (shot.get("scores") or {}).items()}
    if assess_closeup(video, shot["start"], shot["end"], sc)["vetoed"]:
        return False, "homogeneous_closeup"
    if assess_homogeneity(video, shot["start"], shot["end"])["contaminated"]:
        return False, "transition_contaminated"
    return True, "kept"


for slug, run, vid, product in JOBS:
    base = f"output/{slug}/{run}/sources/{vid}"
    out = Path(f"output/recheck/{slug}/{vid}_m64")
    out.mkdir(parents=True, exist_ok=True)
    video = f"{base}/source/original.mp4"
    shots = {s["shot_id"]: s for s in json.load(open(f"{base}/shots.json"))}
    events = json.load(open(f"{base}/events.json"))
    # gate counts over all CF (free, from saved confidences)
    cf_all = [s for s in shots.values() if s["view_class"] == "center_field_good"]
    n_gate = sum(1 for s in cf_all if s["confidence"] < MIN_CENTER_FIELD_CONFIDENCE)
    # full purity evaluation ONLY on event-producing shots (finals depend
    # solely on these; the production pipeline evaluates all CF the same way).
    verdicts = {}
    for e in events:
        sid = e["source_shot_id"]
        if sid in verdicts:
            continue
        ok, why = accept(shots[sid], video)
        verdicts[sid] = why
        print(f"  {sid}: {why}", flush=True)
    from collections import Counter
    print("=" * 30, slug)
    print(f"CF: {len(cf_all)}, gate-drop: {n_gate}")
    kept_ev = [e for e in events if verdicts.get(e["source_shot_id"]) == "kept"]
    drop_ev = [(e["event_id"], e["source_shot_id"]) for e in events
               if verdicts.get(e["source_shot_id"]) != "kept"]
    print(f"events {len(events)} -> {len(kept_ev)}; dropped: {drop_ev}")
    clips = []
    for e in sorted(kept_ev, key=lambda e: e["clip_start"]):
        src = f"{base}/clips/raw/{e['event_id']}.mp4"
        dest = str(out / f"{e['event_id']}.mp4")
        shutil.copy(src, dest)
        clips.append({"clip_id": e["event_id"], "path": dest,
                      "clip_start": e["clip_start"], "clip_end": e["clip_end"],
                      "duration": round(e["clip_end"] - e["clip_start"], 3)})
    dd = dedup_clips(clips)
    kept = sorted(dd["kept"], key=lambda c: c["clip_start"])
    mg = merge_clips([c["path"] for c in kept], str(out / "final.mp4"))
    print("kept:", len(kept), "removed:",
          [(r["clip_id"], r["duplicate_of"]) for r in dd["removed"]],
          "merge:", mg.get("ok"), mg.get("duration"))
    assert mg.get("ok")
    shutil.copy(str(out / "final.mp4"), f"output/recheck/{product}")
    json.dump({"kept_events": [(e["event_id"], e["source_shot_id"]) for e in kept_ev],
               "dropped_events": drop_ev, "kept_clips": len(kept),
               "removed": [(r["clip_id"], r["duplicate_of"]) for r in dd["removed"]],
               "flagged": dd.get("flagged", []),
               "duration": mg["duration"], "codec": mg["codec_info"]},
              open(out / "summary.json", "w"), indent=2)
print("SIMULATION DONE")
