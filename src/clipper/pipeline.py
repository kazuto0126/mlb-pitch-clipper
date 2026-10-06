"""M1 pipeline: local broadcast MP4 -> candidate center-field shots.

Outputs under output/<run_id>/:
  shots.json       all shots with Shot data model
  candidates.json  production subset (view_class == center_field_good)
  diagnostics/     per-shot thumbnails + scores.csv
  manifest.json    run metadata + counts
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
from pathlib import Path

from .probe import probe_video
from .sample import sample_frames, shot_sample_times
from .schemas import PRODUCTION_ACCEPTED, build_shot
from .segment import segment_shots
from .shot_purity import (MIN_CENTER_FIELD_CONFIDENCE, assess_closeup,
                          assess_homogeneity)
from .view_classifier import load_classifier


def run_pipeline(video: str, outdir: str, prefer_clip: bool = True) -> dict:
    out = Path(outdir)
    (out / "diagnostics" / "thumbs").mkdir(parents=True, exist_ok=True)

    info = probe_video(video)
    shots = segment_shots(video)
    clf = load_classifier(prefer_clip=prefer_clip)
    backend = getattr(clf, "backend", type(clf).__name__)

    records: list[dict] = []
    emb_ids: list[str] = []
    embs: list = []
    for i, s in enumerate(shots):
        times = shot_sample_times(s.start, s.end)
        frames = sample_frames(video, times)
        res = clf.classify(frames)
        if res.embedding is not None:  # kept for the M7.6 framing check
            emb_ids.append(f"s{i:03d}")
            embs.append(res.embedding)
        # M6.3/M6.4 purity: confidence gate (cheap) -> close-up veto
        # (margin free + 1 frame) -> dissolve guard (CF survivors only).
        contaminated = False
        homog_veto = False
        if res.view_class in PRODUCTION_ACCEPTED \
                and res.confidence >= MIN_CENTER_FIELD_CONFIDENCE:
            close = assess_closeup(video, s.start, s.end,
                                   {k: round(v, 4) for k, v in res.scores.items()})
            homog_veto = close["vetoed"]
            if not homog_veto:
                contaminated = assess_homogeneity(
                    video, s.start, s.end)["contaminated"]
        shot = build_shot(
            shot_id=f"s{i:03d}",
            start=s.start,
            end=s.end,
            view_class=res.view_class,
            confidence=res.confidence,
            classifier=res.backend,
            scores={k: round(v, 4) for k, v in res.scores.items()},
            min_confidence=MIN_CENTER_FIELD_CONFIDENCE,
            transition_contaminated=contaminated,
            homogeneous_closeup=homog_veto,
        )
        records.append(shot.to_dict())
        # thumbnail = middle sampled frame
        if frames:
            mid = frames[len(frames) // 2]
            mid.save(out / "diagnostics" / "thumbs" / f"{shot.shot_id}_{shot.view_class}.jpg")

    cands = [r for r in records if r["accepted_for_pitch_detection"]]

    (out / "shots.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (out / "candidates.json").write_text(json.dumps(cands, indent=2), encoding="utf-8")
    if embs:
        import numpy as np
        np.savez_compressed(out / "embeddings.npz", ids=np.array(emb_ids),
                            embs=np.stack(embs).astype(np.float16))

    with open(out / "diagnostics" / "scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["shot_id", "start", "end", "view_class", "confidence", "accepted", "reject_reason"])
        for r in records:
            w.writerow([r["shot_id"], r["start"], r["end"], r["view_class"],
                        r["confidence"], r["accepted_for_pitch_detection"], r["reject_reason"]])

    by_view: dict[str, int] = {}
    for r in records:
        by_view[r["view_class"]] = by_view.get(r["view_class"], 0) + 1
    manifest = {
        "run_id": Path(outdir).name,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "milestone": 1,
        "input": {"path": video, "width": info.width, "height": info.height,
                  "fps": round(info.fps, 3), "duration": round(info.duration, 3), "codec": info.codec},
        "classifier_backend": backend,
        "production_rule": "accepted = CF + conf>=0.5 + not contaminated + not homog-closeup",
        "counts": {"total_shots": len(records), "candidates": len(cands), "by_view": by_view},
        "notes": "M1 has no PitchEvent; candidates are shots worth sending to pitch detector (M2).",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-clip", action="store_true", help="force heuristic fallback")
    args = ap.parse_args()
    m = run_pipeline(args.video, args.out, prefer_clip=not args.no_clip)
    print(json.dumps(m["counts"], indent=2))


if __name__ == "__main__":
    main()
