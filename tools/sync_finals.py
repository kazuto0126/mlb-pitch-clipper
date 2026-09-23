"""STEP 0: rebuild finals from existing raw clips with current dedup.

No discovery/preview/download/normalize/M1/M2. Only:
current dedup -> chronological order -> merge -> manifest counters.
Overwrites the same product filenames.
"""
import json
import shutil
import subprocess
import sys

sys.path.insert(0, ".")

from src.clipper.production.dedup import dedup_clips
from src.clipper.production.merge import merge_clips

JOBS = [
    ("output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw",
     "output/yoshinobu-yamamoto/20260923T005044Z/Yoshinobu_Yamamoto_2025.mp4"),
    ("output/mason-miller/20260923T111351Z/sources/q7ndAVBppQQ",
     "output/mason-miller/20260923T111351Z/Mason_Miller_2023.mp4"),
]


def verify(path):
    info = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,pix_fmt,width,height",
         "-show_entries", "format=duration",
         "-of", "json", path], text=True, timeout=120)
    d = json.loads(info)
    st = d["streams"][0]
    Navigator = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"],
        text=True, timeout=600)
    return {"codec": st["codec_name"], "pix_fmt": st["pix_fmt"],
            "duration": float(d["format"]["duration"]),
            "decode_clean": Navigator == "",
            "width": st["width"], "height": st["height"]}


for sdir, product in JOBS:
    dd = json.load(open(f"{sdir}/dedup.json"))
    clips = []
    for c in dd["kept"] + dd["removed"]:
        clips.append({k: c[k] for k in ("clip_id", "path", "clip_start",
                                       "clip_end", "duration")})
    clips.sort(key=lambda c: c["clip_start"])
    out = dedup_clips(clips)
    kept = sorted(out["kept"], key=lambda c: c["clip_start"])
    order_ok = all(kept[i]["clip_start"] <= kept[i + 1]["clip_start"]
                   for i in range(len(kept) - 1))
    mg = merge_clips([c["path"] for c in kept], f"{sdir}/final.mp4")
    assert mg["ok"], mg
    shutil.copy(f"{sdir}/final.mp4", product)
    json.dump(out, open(f"{sdir}/dedup.json", "w"), indent=2)
    man = json.load(open(f"{sdir}/manifest.json"))
    from collections import Counter
    ev = json.load(open(f"{sdir}/events.json"))
    rj = json.load(open(f"{sdir}/rejected_events.json"))
    c = Counter(x["reject_reason"] for x in rj)
    man.update({
        "final_clip_count": len(kept), "raw_clip_count": len(clips),
        "duplicate_rejected": len(out["removed"]),
        "final_duration_sec": mg["duration"], "final_codec": mg["codec_info"],
        "final_fps": mg["fps"],
        "quality_summary": {
            "center_field_candidates": man.get("center_field_candidates"),
            "complete_events": len(ev),
            "rejected_start_incomplete": c.get("start_incomplete", 0),
            "rejected_end_incomplete": c.get("end_incomplete", 0),
            "rejected_no_complete_pitch": c.get("no_complete_pitch", 0),
            "rejected_discontinuity": c.get("shot_discontinuity", 0),
            "duplicate_rejected": len(out["removed"]), "replay_rejected": 0,
            "final_clip_count": len(kept),
            "quality_warning": len(kept) == 0},
    })
    json.dump(man, open(f"{sdir}/manifest.json", "w"), indent=2)
    v = verify(product)
    print(sdir.split("/")[-1], "kept:", len(kept), "removed:",
          [(r["clip_id"], r["duplicate_of"]) for r in out["removed"]],
          "flagged:", len(out["flagged"]), "order:", order_ok)
    print("verify:", v)
    assert v["codec"] in ("h264", "avc1") and v["pix_fmt"] == "yuv420p"
    assert v["decode_clean"] and order_ok
print("SYNC OK")
