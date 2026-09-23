"""Preview gate: frozen M1+M2 per segment -> metrics -> decision.

No new classifiers, no threshold tuning of M1/M2. Bad source => reject
source. Conservative global decision rules (same for every pitcher);
all components are emitted so thresholds can be calibrated later on
distributions, not on a single video.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..pipeline import run_pipeline as run_m1
from ..run_m2 import run_m2
from .preview_acquire import acquire_preview_segments
from .schemas import SourcePreview, compute_metrics


def evaluate_segments(seg_files: list[str], work_dir: str) -> dict:
    """Run frozen M1 then M2 on each downloaded segment file.

    First/last shot of every preview section are truncated by the download
    edge (not real broadcast cuts) and carry no source-quality signal, so
    metrics use interior shots only; edge shots are counted separately.
    """
    shots = cands = complete = rejected = edge = 0
    by_reason: Counter = Counter()
    for i, f in enumerate(seg_files):
        d = str(Path(work_dir) / f"seg{i:02d}")
        run_m1(f, d, prefer_clip=True)
        m2 = run_m2(d, video=f)
        s = json.loads((Path(d) / "shots.json").read_text(encoding="utf-8"))
        c = json.loads((Path(d) / "candidates.json").read_text(encoding="utf-8"))
        e = json.loads((Path(d) / "events.json").read_text(encoding="utf-8"))
        r = json.loads((Path(d) / "rejected_events.json").read_text(encoding="utf-8"))
        _ = m2
        ids = [x["shot_id"] for x in s]
        edge_ids = {ids[0], ids[-1]} if len(ids) > 1 else set(ids)
        edge += len(edge_ids)
        interior_cand = {x["shot_id"] for x in c if x["shot_id"] not in edge_ids}
        shots += len(s) - len(edge_ids)
        cands += len(interior_cand)
        complete += sum(1 for x in e if x["source_shot_id"] in interior_cand)
        r_in = [x for x in r if x["source_shot_id"] not in edge_ids]
        rejected += len(r_in)
        by_reason.update(x["reject_reason"] for x in r_in)
    return {"shots": shots, "candidates": cands, "complete": complete,
            "rejected": rejected, "by_reason": dict(by_reason),
            "edge_skipped": edge}


def decide(rep: SourcePreview) -> SourcePreview:
    reasons = []
    if rep.preview_status == "failed":
        rep.preview_decision = "reject"
        rep.reasons = [f"acquisition failed: {rep.preview_error[:120]}"]
        return rep
    if rep.competition_context == "non_mlb":
        rep.preview_decision = "reject"
        rep.reasons = ["non-MLB competition context excluded from production"]
        return rep
    if rep.center_field_shots == 0:
        rep.preview_decision = "reject"
        rep.reasons = ["zero center-field candidates in preview"]
        return rep
    if rep.m2_complete_events >= 2 and rep.complete_event_yield >= 0.20 \
            and rep.discontinuity_rate <= 0.20:
        rep.preview_decision = "recommended"
        reasons.append(f"yield {rep.complete_event_yield} over "
                       f"{rep.center_field_shots} CF candidates")
    elif rep.m2_complete_events >= 1:
        rep.preview_decision = "borderline"
        reasons.append(f"single complete event "
                       f"(yield {rep.complete_event_yield})")
    elif rep.center_field_ratio >= 0.40 and rep.discontinuity_rate <= 0.30:
        rep.preview_decision = "borderline"
        reasons.append(f"no complete events, but CF available "
                       f"({rep.center_field_ratio}) with clean continuity")
    else:
        rep.preview_decision = "reject"
        reasons.append(f"yield {rep.complete_event_yield}, "
                       f"incomplete_rate {rep.incomplete_rate}")
    if rep.competition_context == "unknown":
        reasons.append("competition context unknown (not confirmed MLB)")
        if rep.preview_decision == "recommended":
            rep.preview_decision = "borderline"
    rep.reasons = reasons
    return rep


def preview_source(candidate: dict, source_dir: str,
                   downloader=None) -> SourcePreview:
    """Full per-source preview: acquire -> frozen M1/M2 -> metrics -> decide."""
    from .preview_acquire import download_section
    from ..discovery.competition import classify_competition
    rep = SourcePreview(
        video_id=candidate.get("video_id", ""),
        title=candidate.get("title", ""),
        channel=candidate.get("channel", ""),
        url=candidate.get("url", ""),
        source_type=candidate.get("source_type", "unknown"),
        metadata_score=(candidate.get("suitability") or {}).get("final_score", 0.0),
        competition_context=classify_competition(
            candidate.get("title", ""),
            candidate.get("description_excerpt", ""),
            candidate.get("channel", "")),
    )
    sdir = Path(source_dir)
    segs = acquire_preview_segments(
        rep.url, candidate.get("duration"), str(sdir / "segments"),
        downloader=downloader or download_section)
    ok_files = [p.file for p in segs if p.method in ("yt-dlp-section", "full-then-trim")]
    methods = Counter(p.method for p in segs)
    rep.preview_segment_count = len(ok_files)
    rep.preview_duration_sec = round(sum(
        p.duration for p in segs if p.file), 1)
    if not ok_files:
        rep.preview_status = "failed"
        rep.preview_error = "; ".join(p.error for p in segs)[:300]
        return decide(rep)
    rep.preview_status = "ok" if len(ok_files) == len(segs) else "partial"
    agg = evaluate_segments(ok_files, str(sdir / "m1m2"))
    rep.edge_skipped_shots = agg["edge_skipped"]
    rep.shot_count = agg["shots"]
    rep.center_field_shots = agg["candidates"]
    rep.center_field_ratio = round(agg["candidates"] / max(agg["shots"], 1), 3)
    rep.m2_complete_events = agg["complete"]
    rep.m2_rejected_events = agg["rejected"]
    rep.reject_by_reason = agg["by_reason"]
    rep.__dict__.update(compute_metrics(
        agg["candidates"], agg["shots"], agg["complete"],
        agg["rejected"], agg["by_reason"], rep.preview_duration_sec))
    decide(rep)
    rep.reasons = [f"acquire: {dict(methods)}"] + rep.reasons
    (sdir / "preview_stats.json").write_text(
        json.dumps(rep.to_dict(), indent=2), encoding="utf-8")
    return rep
