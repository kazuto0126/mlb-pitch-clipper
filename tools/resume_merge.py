"""Resume M5 merge for an already-produced source dir (clips exist)."""
import json
import shutil
import sys

sys.path.insert(0, ".")

from src.clipper.production.merge import merge_clips
from src.clipper.production.naming import product_filename

sdir, pitcher, year, taken_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
import pathlib
sdir = pathlib.Path(sdir)
man = json.load(open(sdir / "manifest.json"))
dd = json.load(open(sdir / "dedup.json"))
kept = sorted(dd["kept"], key=lambda c: c["clip_start"])
taken = set(json.load(open(taken_path)) if pathlib.Path(taken_path).exists() else [])
mg = merge_clips([c["path"] for c in kept], str(sdir / "final.mp4"))
print("merge:", json.dumps(mg))
if mg.get("ok"):
    fname = product_filename(pitcher, int(year) if year != "None" else None, taken,
                             game_year_confidence=man.get("game_year_confidence"))
    taken.add(fname)
    shutil.copy(sdir / "final.mp4", sdir.parent.parent / fname)
    man.update({"status": "ok", "final_path": fname,
                "final_duration_sec": mg["duration"], "final_codec": mg["codec_info"],
                "final_fps": mg["fps"],
                "quality_summary": {**man.get("quality_summary", {}),
                                    "quality_warning": False}})
    json.dump(man, open(sdir / "manifest.json", "w"), indent=2)
    json.dump(sorted(taken), open(taken_path, "w"))
    print("final:", fname)
