"""Per-source production: normalize -> frozen M1 -> calibrated M2 ->
clips -> conservative dedup -> chronological merge -> manifest.

M1/M2 reused frozen (M2 at calibrated DEFAULT_PARAMS). No tuning here.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..acquisition.full_acquire import acquire_full
from ..pipeline import run_pipeline as run_m1
from ..run_m2 import run_m2
from .clips import extract_clip
from .dedup import dedup_clips
from .merge import merge_clips
from .naming import product_filename
from .normalize import normalize_media


def _qsum(by_reason: dict, get):
    return {
        "rejected_start_incomplete": by_reason.get("start_incomplete", 0),
        "rejected_end_incomplete": by_reason.get("end_incomplete", 0),
        "rejected_no_complete_pitch": by_reason.get("no_complete_pitch", 0),
        "rejected_discontinuity": by_reason.get("shot_discontinuity", 0),
    }


def produce_source(pitcher_name: str, candidate: dict, source_dir: str,
                   filename_taken: set, downloader=acquire_full) -> dict:
    sdir = Path(source_dir)
    (sdir / "source").mkdir(parents=True, exist_ok=True)
    (sdir / "intermediate").mkdir(parents=True, exist_ok=True)
    man: dict = {
        "pitcher_name": pitcher_name,
        "video_id": candidate.get("video_id", ""),
        "source_url": candidate.get("url", ""),
        "source_title": candidate.get("title", ""),
        "channel": candidate.get("channel", ""),
        "source_type": candidate.get("source_type", "unknown"),
        "game_year": candidate.get("game_year"),
        "game_year_confidence": candidate.get("game_year_confidence", "null"),
        "competition_context": candidate.get("competition_context", "unknown"),
        "discovery_score": ((candidate.get("suitability") or {})
                            .get("final_score")),
        "preview_decision": candidate.get("preview_decision", "unknown"),
        "source_selection_mode": candidate.get("source_selection_mode", "unknown"),
    }
    # 1. full acquisition (fallback handled by caller across sources)
    dl = downloader(candidate["url"], str(sdir / "source" / "original.mp4"),
                    str(sdir / "source" / "metadata.json"))
    man["download_status"] = "ok" if dl.get("ok") else f"failed: {dl.get('error')}"
    man["acquisition_method"] = dl.get("method", "none")
    man["local_path"] = str(sdir / "source" / "original.mp4") if dl.get("ok") else ""
    if not dl.get("ok"):
        man["status"] = "failed-download"
        return man
    # 2. normalize
    nm = normalize_media(str(sdir / "source" / "original.mp4"),
                         str(sdir / "intermediate" / "normalized.mp4"))
    man["normalization_status"] = nm.get("method", f"failed: {nm.get('error')}")
    if not nm.get("ok"):
        man["status"] = "failed-normalize"
        return man
    src = str(sdir / "intermediate" / "normalized.mp4")
    # 3. frozen M1 on the full video
    m1out = str(sdir / "m1")
    run_m1(src, m1out, prefer_clip=True)
    shots = json.loads((Path(m1out) / "shots.json").read_text(encoding="utf-8"))
    cands = json.loads((Path(m1out) / "candidates.json").read_text(encoding="utf-8"))
    shutil.copy(Path(m1out) / "shots.json", sdir / "shots.json")
    shutil.copy(Path(m1out) / "candidates.json", sdir / "candidates.json")
    man["shot_count"] = len(shots)
    man["center_field_candidates"] = len(cands)
    m1_rej: dict = {}
    for s in shots:
        if not s.get("accepted_for_pitch_detection"):
            r = s.get("reject_reason") or "unknown"
            m1_rej[r] = m1_rej.get(r, 0) + 1
    man["rejected_low_confidence"] = m1_rej.get("low_view_confidence", 0)
    man["rejected_transition"] = m1_rej.get("transition_contaminated", 0)
    man["rejected_homogeneous_closeup"] = m1_rej.get("homogeneous_closeup", 0)
    # 4. calibrated M2 (DEFAULT_PARAMS)
    m2 = run_m2(m1out, video=src)
    events = json.loads((Path(m1out) / "events.json").read_text(encoding="utf-8"))
    rejected = json.loads((Path(m1out) / "rejected_events.json").read_text(encoding="utf-8"))
    shutil.copy(Path(m1out) / "events.json", sdir / "events.json")
    shutil.copy(Path(m1out) / "rejected_events.json", sdir / "rejected_events.json")
    _ = m2
    by_reason: dict = {}
    for r in rejected:
        by_reason[r["reject_reason"]] = by_reason.get(r["reject_reason"], 0) + 1
    man["complete_events"] = len(events)
    man["rejected_events"] = len(rejected)
    man["rejected_start_incomplete"] = by_reason.get("start_incomplete", 0)
    man["rejected_end_incomplete"] = by_reason.get("end_incomplete", 0)
    man["rejected_no_complete_pitch"] = by_reason.get("no_complete_pitch", 0)
    man["rejected_discontinuity"] = by_reason.get("shot_discontinuity", 0)
    # 5. clip extraction (chronological)
    events.sort(key=lambda e: e["clip_start"])
    clips = []
    for e in events:
        dest = str(sdir / "clips" / "raw" / f"{e['event_id']}.mp4")
        r = extract_clip(src, e["clip_start"], e["clip_end"], dest)
        if r.get("ok"):
            clips.append({"clip_id": e["event_id"], "path": dest,
                          "clip_start": e["clip_start"], "clip_end": e["clip_end"],
                          "duration": r["duration"]})
    man["raw_clip_count"] = len(clips)
    # 6. conservative dedup (uncertain pairs kept)
    dd = dedup_clips(clips)
    (sdir / "dedup.json").write_text(json.dumps(dd, indent=2), encoding="utf-8")
    man["duplicate_rejected"] = len(dd["removed"])
    man["replay_rejected"] = 0
    man["replay_status"] = "uncertain" if not dd["removed"] else "duplicates-removed"
    kept = sorted(dd["kept"], key=lambda c: c["clip_start"])
    man["final_clip_count"] = len(kept)

    def _finish(status, extra=None):
        from .manifest import build_warnings
        man["status"] = status
        if extra:
            man.update(extra)
        man["quality_warning"], man["warnings"] = build_warnings(man)
        man["quality_summary"] = {
            **_qsum(by_reason, None),
            "center_field_candidates": len(cands),
            "complete_events": len(events),
            "duplicate_rejected": len(dd["removed"]),
            "replay_rejected": 0,
            "final_clip_count": len(kept),
            "quality_warning": man["quality_warning"],
        }
        (sdir / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
        return man

    if not kept:
        man["status"] = "no-usable-clips"
        return _finish("no-usable-clips")
    # 7. merge + product filename
    final_tmp = str(sdir / "final.mp4")
    mg = merge_clips([c["path"] for c in kept], final_tmp)
    if not mg.get("ok"):
        return _finish(f"failed-merge: {mg.get('error')}")
    fname = product_filename(pitcher_name, candidate.get("game_year"), filename_taken)
    filename_taken.add(fname)
    shutil.copy(final_tmp, Path(source_dir).parent.parent / fname)
    return _finish("ok", {
        "final_path": fname,
        "final_duration_sec": mg["duration"], "final_codec": mg["codec_info"],
        "final_fps": mg["fps"],
    })
