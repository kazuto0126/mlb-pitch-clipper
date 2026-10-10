"""Hand-off of finished pitches to a downstream project (contract v2).

The two projects share ONLY the hand-off folder (no code, no imports).
One batch per produced source; ONE MP4 PER PITCH plus a paired JSON:

  <handoff>/
    CONTRACT.md                      copied from docs/HANDOFF_CONTRACT.md
    index.jsonl                      one line per batch, appended LAST
    <pitcher-slug>/<batch_id>/
      batch.json
      <pitch_id>.mp4                 one complete pitch, frame 0 = file start
      <pitch_id>.json
      viewing/<Pitcher_Name>_<Game_Year>.mp4   merged, for viewing only

Per-pitch bounds: M2's clip widened to PRE_ROLL before motion onset and
POST_ROLL after settle (set position and full follow-through), never past
the detected shot (one continuous camera shot) nor into a neighbouring
pitch of the same shot, never shorter than M2's own clip, <= MAX_CLIP_SEC.
Each extracted file is scanned for hard cuts before it is accepted.

Every file is written as *.tmp then os.replace'd and the index line is
appended last, so a reader following index.jsonl never sees a partial
batch; a batch that fails midway is removed. Batches are immutable; a
re-run is a new batch_id.

CLI (deliver an already produced run):
  python -m src.clipper.production.deliver --run output/<slug>/<run_id> \
      --to D:/project/pitch-video-handoff --throws R
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .clips import extract_clip

CONTRACT_VERSION = 2
INDEX = "index.jsonl"
VIEW = "rear_centerfield_broadcast"
PRE_ROLL = 2.0     # s before motion onset (set position / preparation)
POST_ROLL = 1.5    # s after settle (follow-through to balance)
SHOT_EDGE = 0.1    # s kept after a shot's detected start (always on/after the cut)
# segment.py samples at 5 fps and stamps a cut on the first sample after
# it, so a detected shot end can be up to 0.2 s past the real cut
SHOT_END_EDGE = 0.25
NEIGHBOUR_GAP = 0.3  # s kept away from another pitch in the same shot
HARD_CUT_DIFF = 20.0  # mean abs frame diff (320x180); in-shot frames stay < 5
# Same-camera jump cuts (edits that drop the time between pitches) change
# little but all at once: one isolated frame diff many times the local
# level (Glasnow fan edit: 6.9-7.3 vs ~0.6). Pans rise and fall gradually.
JUMP_CUT_MIN, JUMP_CUT_RATIO = 3.0, 4.0
MAX_CLIP_SEC = 30.0
MIN_BATCH_PITCHES = 3
CONTRACT_SRC = Path(__file__).resolve().parents[3] / "docs" / "HANDOFF_CONTRACT.md"

# Honest per-pitch checks: what the pipeline guarantees vs what needs a human.
CHECKS = {
    "single_motion_event": ("verified_by_pipeline", "one complete M2 motion "
                            "event; bounds stop short of other events in the "
                            "same shot"),
    "pitch_delivery_visible": ("not_verified", "the motion detector can fire on "
                               "catcher/batter movement while the pitcher stands "
                               "(seen in the M7.7 audit)"),
    "continuous_shot": ("verified_by_pipeline", "inside one detected shot "
                        "(end kept 0.25 s clear of the 5 fps cut grid); "
                        "transition guard on the shot; delivered file scanned "
                        "frame by frame for hard cuts and same-camera jump cuts"),
    "view_rear_centerfield": ("verified_by_pipeline", "CLIP view class + "
                              "close-up vetoes + per-source framing consistency"),
    "normal_speed_export": ("verified_by_pipeline", "no speed change, original "
                            "frame rate, no frame interpolation"),
    "not_replay_or_slow_motion": ("not_verified", "replay detection is "
                                  "conservative; a slow-motion replay may remain"),
    "not_mirrored": ("not_verified", "no automatic check"),
    "full_body_in_frame": ("not_verified", "no automatic check"),
    "pitcher_identity": ("not_verified", "source is a pitcher-centred edit "
                         "found for this name; no visual identity check "
                         "(out of scope by design)"),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _ratio(s: str) -> float:
    try:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    except Exception:
        return 0.0


def probe_pitch(path: Path) -> dict:
    """Frame-exact facts of a delivered file (read from the file itself)."""
    v = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=codec_name,pix_fmt,width,height,r_frame_rate,"
         "avg_frame_rate,nb_read_frames,sample_aspect_ratio,start_time,duration",
         "-of", "json", str(path)], text=True, timeout=300))["streams"][0]
    audio = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)], text=True, timeout=120).strip()
    r, avg = _ratio(v.get("r_frame_rate", "0/1")), _ratio(v.get("avg_frame_rate", "0/1"))
    sar = v.get("sample_aspect_ratio", "1:1")
    return {"codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "width": v.get("width"), "height": v.get("height"),
            "fps": v.get("r_frame_rate"), "fps_float": round(r, 3),
            "constant_frame_rate": bool(r and avg and abs(r - avg) / r < 0.005),
            "frame_count": int(v.get("nb_read_frames") or 0),
            "duration_sec": round(float(v.get("duration") or 0.0), 3),
            # container start_time (libx264 adds ~1 frame); decoders return
            # frame 0 at 0.0 — time frames as frame_index / fps_float
            "container_start_time_sec": round(float(v.get("start_time") or 0.0), 3),
            "frame_time_rule": "t = frame_index / fps_float (frame 0 = 0.0 s)",
            "square_pixels": sar in ("1:1", "0:1", "N/A", None),
            "has_audio": bool(audio)}


def hard_cuts(path: Path) -> list[int]:
    """Frame indices that start a new picture in a delivered file: a hard
    cut, or a same-camera jump cut (isolated spike over the local level)."""
    cap = cv2.VideoCapture(str(path))
    d, prev = [], None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.resize(f, (320, 180))
        if prev is not None:
            d.append(float(np.mean(cv2.absdiff(g, prev))))
        prev = g
    cap.release()
    cuts = []
    for i, x in enumerate(d):  # d[i] is the change into frame i + 1
        local = d[max(0, i - 15):max(0, i - 1)] + d[i + 2:i + 16]
        isolated = (i == 0 or d[i - 1] < x / 2) and (i + 1 >= len(d) or d[i + 1] < x / 2)
        if x > HARD_CUT_DIFF or (
                local and isolated and x > JUMP_CUT_MIN
                and x > JUMP_CUT_RATIO * max(float(np.median(local)), 0.3)):
            cuts.append(i + 1)
    return cuts


def pitch_bounds(event: dict, shot: dict, same_shot_events: list[dict]) -> tuple[float, float]:
    start = max(shot["start"] + SHOT_EDGE, event["motion_onset"] - PRE_ROLL)
    end = min(shot["end"] - SHOT_END_EDGE, event["settle_time"] + POST_ROLL)
    for o in same_shot_events:
        if o["event_id"] == event["event_id"]:
            continue
        if o["settle_time"] <= event["motion_onset"]:   # earlier pitch
            start = max(start, o["settle_time"] + NEIGHBOUR_GAP)
        if o["motion_onset"] >= event["settle_time"]:   # later pitch
            end = min(end, o["motion_onset"] - NEIGHBOUR_GAP)
    # never shorter than M2's clip, except where it runs into the uncertain
    # zone before the detected shot end
    start = min(start, event["clip_start"])
    end = min(max(end, event["clip_end"]), shot["end"] - SHOT_END_EDGE)
    if end - start > MAX_CLIP_SEC:
        end = start + MAX_CLIP_SEC
    return round(start, 3), round(end, 3)


def _season(m: dict):
    if m.get("game_year") and m.get("game_year_confidence") in ("high", "medium"):
        return m["game_year"]
    return "unknown"


def deliver_source(run_root: Path, source_manifest: dict, deliver_root: str,
                   pitcher_slug: str, run_id: str, throws: str = "unknown",
                   exclude: dict | None = None) -> dict:
    """Write one batch (all kept pitches of one produced source).

    exclude: {kept_index (1-based, chronological): reason} removed by an
    operator after review; recorded in batch.json, never silent."""
    m = source_manifest
    exclude = exclude or {}
    sdir = run_root / "sources" / m["video_id"]
    video = sdir / "intermediate" / "normalized.mp4"
    shots = {s["shot_id"]: s for s in json.loads((sdir / "shots.json").read_text(encoding="utf-8"))}
    events = json.loads((sdir / "events.json").read_text(encoding="utf-8"))
    by_id = {e["event_id"]: e for e in events}
    kept = sorted(json.loads((sdir / "dedup.json").read_text(encoding="utf-8"))["kept"],
                  key=lambda c: c["clip_start"])
    if len(kept) - len([k for k in exclude if 1 <= k <= len(kept)]) < MIN_BATCH_PITCHES:
        raise ValueError(f"fewer than {MIN_BATCH_PITCHES} pitches left to deliver")
    batch_id = f"{run_id}_{m['video_id']}"
    root = Path(deliver_root)
    bdir = root / pitcher_slug / batch_id
    if bdir.exists():  # batches are immutable: never write into one again
        raise FileExistsError(f"batch already delivered: {bdir}")
    bdir.mkdir(parents=True)
    created = _dt.datetime.now(_dt.timezone.utc).isoformat()
    source = {"video_id": m.get("video_id"), "title": m.get("source_title"),
              "url": m.get("source_url"), "channel": m.get("channel"),
              "source_type": m.get("source_type")}
    game = {"season": _season(m), "season_confidence": m.get("game_year_confidence"),
            "team": "unknown", "opponent": "unknown", "game_id": "unknown",
            "pitch_type": "unknown"}
    try:
        pitches, excluded = [], []
        for k, c in enumerate(kept, 1):
            e = by_id[c["clip_id"]]
            shot = shots[e["source_shot_id"]]
            same = [x for x in events if x["source_shot_id"] == e["source_shot_id"]]
            s, t = pitch_bounds(e, shot, same)
            if k in exclude:
                excluded.append({"kept_index": k, "source_start_sec": s,
                                 "source_end_sec": t, "reason": exclude[k]})
                continue
            i = len(pitches) + 1
            pitch_id = f"{batch_id}_p{i:02d}"
            mp4 = bdir / f"{pitch_id}.mp4"
            tmp = bdir / f"{pitch_id}.tmp.mp4"
            r = extract_clip(str(video), s, t, str(tmp))
            if not r.get("ok"):
                raise RuntimeError(f"extract {pitch_id}: {r.get('error')}")
            cuts = hard_cuts(tmp)
            if cuts:
                raise RuntimeError(f"{pitch_id} (kept #{k}, {s}-{t}s) has a hard cut at "
                                   f"frame {cuts}; exclude it or check the shot bounds")
            os.replace(tmp, mp4)
            rec = {
                "contract_version": CONTRACT_VERSION, "pitch_id": pitch_id,
                "batch_id": batch_id, "index": i, "created_utc": created,
                "pitcher_name": m.get("pitcher_name"), "throws": throws,
                "view": VIEW, "video_file": mp4.name, "sha256": _sha256(mp4),
                "video": probe_pitch(mp4),
                "source": {**source, "start_sec": s, "end_sec": t},
                "game": game,
                "pipeline_anchors_sec": {
                    "motion_onset": round(e["motion_onset"] - s, 3),
                    "motion_peak": round(e["motion_peak"] - s, 3),
                    "settle": round(e["settle_time"] - s, 3),
                    "note": "motion-energy anchors relative to frame 0; NOT "
                            "biomechanical events (no release/foot-strike claim)"},
                "checks": {k: {"status": st, "how": how} for k, (st, how) in CHECKS.items()},
                "requires_human_review": [k for k, (st, _) in CHECKS.items() if st != "verified_by_pipeline"],
            }
            _atomic_json(bdir / f"{pitch_id}.json", rec)
            pitches.append(rec)
        viewing = None
        if m.get("final_path") and (run_root / m["final_path"]).exists():
            (bdir / "viewing").mkdir(exist_ok=True)
            dst = bdir / "viewing" / m["final_path"]
            shutil.copyfile(run_root / m["final_path"], dst.with_name(dst.name + ".tmp"))
            os.replace(dst.with_name(dst.name + ".tmp"), dst)
            viewing = f"viewing/{m['final_path']}"
        batch = {"contract_version": CONTRACT_VERSION, "batch_id": batch_id,
                 "created_utc": created, "pitcher_name": m.get("pitcher_name"),
                 "throws": throws, "view": VIEW, "pitch_count": len(pitches),
                 "pitches": [{"pitch_id": p["pitch_id"], "video_file": p["video_file"],
                              "json": f"{p['pitch_id']}.json"} for p in pitches],
                 "source": source, "game": game, "viewing_video": viewing,
                 "excluded_by_operator": excluded,
                 "quality_warning": m.get("quality_warning"), "warnings": m.get("warnings", [])}
        _atomic_json(bdir / "batch.json", batch)
    except BaseException:
        shutil.rmtree(bdir, ignore_errors=True)  # never indexed, so never seen
        raise
    if CONTRACT_SRC.exists():
        tmp = root / "CONTRACT.md.tmp"
        shutil.copyfile(CONTRACT_SRC, tmp)
        os.replace(tmp, root / "CONTRACT.md")
    line = {"batch_id": batch_id, "pitcher_name": m.get("pitcher_name"),
            "contract_version": CONTRACT_VERSION, "pitch_count": len(pitches),
            "batch_json": f"{pitcher_slug}/{batch_id}/batch.json", "created_utc": created}
    with (root / INDEX).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def deliver_run(run_dir: str, deliver_root: str, throws: str = "unknown",
                exclude: dict | None = None) -> list[dict]:
    run_root = Path(run_dir)
    rm = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    ok = [r for r in rm.get("results", []) if r.get("status") == "ok"]
    return [deliver_source(run_root, r, deliver_root, run_root.parent.name,
                           rm["run_id"], throws, exclude) for r in ok]


def _parse_exclude(items: list[str]) -> dict:
    out = {}
    for it in items:
        k, _, reason = it.partition("=")
        out[int(k)] = reason.strip() or "excluded by operator after review"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="deliver a produced run (contract v2)")
    ap.add_argument("--run", required=True, help="output/<pitcher-slug>/<run_id>")
    ap.add_argument("--to", required=True, help="hand-off folder")
    ap.add_argument("--throws", choices=("R", "L", "unknown"), default="unknown")
    ap.add_argument("--exclude", action="append", default=[],
                    help='kept clip index to leave out after review, e.g. '
                         '--exclude "2=catcher motion, no delivery" (repeatable)')
    a = ap.parse_args()
    print(json.dumps(deliver_run(a.run, a.to, a.throws, _parse_exclude(a.exclude)),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
