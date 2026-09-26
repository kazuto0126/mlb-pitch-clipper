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


def evaluate_segments(seg_files: list[str], work_dir: str,
                      start_idx: int = 0) -> dict:
    """Run frozen M1 then M2 on each downloaded segment file.

    First/last shot of every preview section are truncated by the download
    edge (not real broadcast cuts) and carry no source-quality signal, so
    metrics use interior shots only; edge shots are counted separately.
    """
    shots = cands = complete = rejected = edge = 0
    skipped = 0
    by_reason: Counter = Counter()
    for k, f in enumerate(seg_files):
        i = start_idx + k
        d = str(Path(work_dir) / f"seg{i:02d}")
        run_m1(f, d, prefer_clip=True)
        s = json.loads((Path(d) / "shots.json").read_text(encoding="utf-8"))
        c = json.loads((Path(d) / "candidates.json").read_text(encoding="utf-8"))
        if not c:
            # No CF candidates: contributes shots only. M2 asserts non-empty
            # input, so skip it here — one empty segment must never kill
            # the whole source (failure isolation, not a threshold change).
            shots += len(s)
            skipped += 1
            continue
        m2 = run_m2(d, video=f)
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
            "edge_skipped": edge, "segments_skipped_empty": skipped}


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
    duration = candidate.get("duration")
    segs = acquire_preview_segments(
        rep.url, duration, str(sdir / "segments"),
        downloader=downloader or download_section)
    rep.initial_preview_segments = sum(
        1 for p in segs if p.method in ("yt-dlp-section", "full-then-trim"))
    _accumulate(rep, [p.file for p in segs
                      if p.method in ("yt-dlp-section", "full-then-trim")],
                segs, sdir, start_idx=0)
    if rep.preview_status == "failed":
        rep.preview_error = "; ".join(p.error for p in segs)[:300]
        decide(rep)
        rep.final_preview_decision = rep.preview_decision
        (sdir / "preview_stats.json").write_text(
            json.dumps(rep.to_dict(), indent=2), encoding="utf-8")
        return rep
    # adaptive second/third pass on INSUFFICIENT evidence only
    from .evidence import (budget_ok, classify_evidence, expansion_rounds)
    state, why = classify_evidence(
        rep.center_field_shots, rep.m2_complete_events,
        rep.m2_rejected_events, rep.reject_by_reason)
    rep.evidence_state = state
    if rep.preview_status == "ok" and state == "insufficient":
        for rnd, fracs in expansion_rounds(duration):
            have = [(p.start, p.start + p.duration) for p in segs if p.file]
            secs = sum(p.duration for p in segs if p.file)
            if not budget_ok(len([p for p in segs if p.file]), secs, duration):
                rep.adaptive_reason = (f"budget exhausted after round {rnd - 1}; "
                                       f"staying with initial evidence")
                break
            extra = [p for p in
                     _download_plans(rep.url, duration, fracs, have,
                                     str(sdir / "segments"),
                                     downloader or download_section, rnd)
                     if p.method in ("yt-dlp-section", "full-then-trim")]
            if not extra:
                rep.adaptive_reason = (f"round {rnd}: no downloadable segments; "
                                       f"staying with initial evidence")
                break
            rep.adaptive_preview_triggered = True
            rep.adaptive_reason = (f"round 1 {why}; expanded round {rnd} "
                                   f"with {len(extra)} segments")
            segs.extend(extra)
            _accumulate(rep, [p.file for p in extra], extra, sdir,
                        start_idx=rep.preview_segment_count - len(extra))
            state, why = classify_evidence(
                rep.center_field_shots, rep.m2_complete_events,
                rep.m2_rejected_events, rep.reject_by_reason)
            rep.evidence_state = state
            if state != "insufficient":
                break
    decide(rep)
    rep.final_preview_decision = rep.preview_decision
    rep.total_preview_seconds = rep.preview_duration_sec
    rep.preview_fraction = round(rep.preview_duration_sec / duration, 4) \
        if duration else None
    rep.reasons = [f"acquire: {rep.adaptive_reason or 'round 1 only'}"] + rep.reasons
    (sdir / "preview_stats.json").write_text(
        json.dumps(rep.to_dict(), indent=2), encoding="utf-8")
    return rep


def _download_plans(url, duration, fracs, have, seg_dir, downloader, rnd):
    from .preview_acquire import plan_expansion
    from pathlib import Path as _P
    out = []
    for p in plan_expansion(duration, have, fracs):
        dest = str(_P(seg_dir) / f"segR{rnd}_{p.index:02d}_{int(p.start)}s.mp4")
        try:
            got = downloader(url, p.start, p.duration, dest)
        except Exception as e:
            from .schemas import PreviewSegmentPlan
            got = PreviewSegmentPlan(p.index, p.start, p.duration,
                                     method="failed", error=str(e)[:200])
        got.index = p.index
        p.method, p.file, p.error = got.method, got.file, got.error
        out.append(p)
    return out


def _accumulate(rep, new_files, new_plans, sdir, start_idx=0):
    """Run frozen M1/M2 over newly downloaded files; ADD into rep totals."""
    from collections import Counter as _C
    for p in new_plans:
        if p.method not in ("yt-dlp-section", "full-then-trim"):
            rep._n_failed = getattr(rep, "_n_failed", 0) + 1
    if not new_files:
        if rep.preview_segment_count == 0:
            rep.preview_status = "failed"
            rep.preview_error = "no downloadable segments"
            decide(rep)
        return
    agg = evaluate_segments(new_files, str(sdir / "m1m2"), start_idx=start_idx)
    rep.preview_segment_count += len(new_files)
    rep.segments_skipped_empty += agg.get("segments_skipped_empty", 0)
    rep.preview_duration_sec = round(
        rep.preview_duration_sec + sum(
            p.duration for p in new_plans if p.file), 1)
    rep.edge_skipped_shots += agg["edge_skipped"]
    rep.shot_count += agg["shots"]
    rep.center_field_shots += agg["candidates"]
    rep.m2_complete_events += agg["complete"]
    rep.m2_rejected_events += agg["rejected"]
    merged = dict(rep.reject_by_reason)
    for k, v in agg["by_reason"].items():
        merged[k] = merged.get(k, 0) + v
    rep.reject_by_reason = merged
    rep.center_field_ratio = round(
        rep.center_field_shots / max(rep.shot_count, 1), 3)
    rep.__dict__.update(compute_metrics(
        rep.center_field_shots, rep.shot_count, rep.m2_complete_events,
        rep.m2_rejected_events, rep.reject_by_reason, rep.preview_duration_sec))
    rep.expanded_preview_segments = max(
        0, rep.preview_segment_count - rep.initial_preview_segments)
    n_fail = getattr(rep, "_n_failed", 0)
    rep.preview_status = "ok" if n_fail == 0 else "partial"
