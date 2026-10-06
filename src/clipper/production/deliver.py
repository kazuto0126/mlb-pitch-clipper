"""Hand-off of finished videos to a downstream project (contract v1).

The two projects share ONLY this folder (no code, no imports). Layout:

  <deliver_root>/
    index.jsonl                         one line per delivery, appended LAST
    <pitcher-slug>/<delivery_id>/
      <Pitcher_Name>_<Game_Year>.mp4
      delivery.json                     contract fields + per-clip offsets

Atomicity: video and delivery.json are written to *.tmp then os.replace'd;
the index line is appended only after both exist, so a reader that follows
index.jsonl never sees a partial delivery. Deliveries are immutable: a new
run produces a new delivery_id, nothing is overwritten.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
from pathlib import Path

CONTRACT_VERSION = 1
INDEX = "index.jsonl"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clip_offsets(source_dir: Path) -> list[dict]:
    """Where each kept clip sits inside the merged video (concat order =
    chronological), plus its time in the original source video."""
    dd = source_dir / "dedup.json"
    if not dd.exists():
        return []
    kept = sorted(json.loads(dd.read_text(encoding="utf-8"))["kept"],
                  key=lambda c: c["clip_start"])
    out, t = [], 0.0
    for i, c in enumerate(kept, 1):
        dur = float(c.get("duration") or (c["clip_end"] - c["clip_start"]))
        out.append({"index": i, "start_sec": round(t, 3), "end_sec": round(t + dur, 3),
                    "source_start_sec": round(c["clip_start"], 3),
                    "source_end_sec": round(c["clip_end"], 3)})
        t += dur
    return out


def deliver_source(run_root: Path, source_manifest: dict, deliver_root: str,
                   pitcher_slug: str, run_id: str) -> dict:
    """Copy one produced video + delivery.json into deliver_root."""
    m = source_manifest
    src_video = run_root / m["final_path"]
    delivery_id = f"{run_id}_{m['video_id']}"
    ddir = Path(deliver_root) / pitcher_slug / delivery_id
    ddir.mkdir(parents=True, exist_ok=True)
    dst_video = ddir / m["final_path"]
    tmp = dst_video.with_name(dst_video.name + ".tmp")
    shutil.copyfile(src_video, tmp)
    os.replace(tmp, dst_video)
    record = {
        "contract_version": CONTRACT_VERSION,
        "delivery_id": delivery_id,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "pitcher_name": m.get("pitcher_name"),
        "video_file": dst_video.name,
        "sha256": _sha256(dst_video),
        "final_clip_count": m.get("final_clip_count"),
        "final_duration_sec": m.get("final_duration_sec"),
        "game_year": m.get("game_year"),
        "game_year_confidence": m.get("game_year_confidence"),
        "source": {"video_id": m.get("video_id"), "title": m.get("source_title"),
                   "url": m.get("source_url"), "channel": m.get("channel"),
                   "source_type": m.get("source_type")},
        "quality_warning": m.get("quality_warning"),
        "warnings": m.get("warnings", []),
        "clips": _clip_offsets(run_root / "sources" / m["video_id"]),
    }
    side = ddir / "delivery.json"
    tmp = side.with_name(side.name + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, side)
    line = {"delivery_id": delivery_id, "pitcher_name": record["pitcher_name"],
            "contract_version": CONTRACT_VERSION,
            "video": f"{pitcher_slug}/{delivery_id}/{dst_video.name}",
            "delivery_json": f"{pitcher_slug}/{delivery_id}/delivery.json",
            "created_utc": record["created_utc"]}
    with (Path(deliver_root) / INDEX).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line
