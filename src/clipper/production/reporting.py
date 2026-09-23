"""M6 generalization audit helpers (audit-only, never production gates).

Ratios are product-level statistics; the failure taxonomy classifies a
completed/failed production summary into one high-level bucket for the
cross-pitcher report. Cutoffs below are audit conventions, not pipeline
thresholds — production code must not import them for decisions.
"""
from __future__ import annotations


def product_ratios(s: dict) -> dict:
    shots = s.get("shot_count") or 0
    cf = s.get("center_field_candidates") or 0
    comp = s.get("complete_events") or 0
    final = s.get("final_clip_count") or 0
    dur_min = (s.get("full_video_duration_sec") or 0) / 60.0
    return {
        "center_field_rate": round(cf / shots, 4) if shots else 0.0,
        "complete_yield": round(comp / cf, 4) if cf else 0.0,
        "final_yield": round(final / cf, 4) if cf else 0.0,
        "clips_per_source_minute": round(final / dur_min, 4) if dur_min else 0.0,
    }


def classify_failure(s: dict) -> str:
    """One high-level bucket per §7 taxonomy (audit only)."""
    status = s.get("status", "")
    if status == "failed-download":
        return "DOWNLOAD_FAILURE"
    if s.get("competition_context") == "non_mlb":
        return "SOURCE_NOT_MLB"
    if not s.get("shot_count"):
        return "UNKNOWN"
    cf_rate = product_ratios(s)["center_field_rate"]
    if cf_rate < 0.30:
        return "LOW_CENTER_FIELD_COVERAGE"
    rej_s = s.get("rejected_start_incomplete", 0)
    rej_e = s.get("rejected_end_incomplete", 0)
    rej_n = s.get("rejected_no_complete_pitch", 0)
    tot = rej_s + rej_e + rej_n
    if tot > 0:
        if rej_s / tot >= 0.5:
            return "HIGH_START_INCOMPLETE"
        if rej_e / tot >= 0.5:
            return "HIGH_END_INCOMPLETE"
    if not s.get("complete_events") and not s.get("final_clip_count"):
        return "ZERO_USABLE_EVENTS"
    if product_ratios(s)["complete_yield"] < 0.05:
        return "LOW_COMPLETE_EVENT_YIELD"
    dur = s.get("full_video_duration_sec") or 0
    if 0 < dur < 180:
        return "SOURCE_TOO_SHORT"
    disc = (s.get("rejected_discontinuity", 0) or 0) / max(s.get("shot_count", 1), 1)
    if disc >= 0.05:
        return "SOURCE_BAD_EDITING"
    return "UNKNOWN"


def dedup_warning(removed: int, kept: int, thresh: float = 0.30) -> bool:
    tot = (removed or 0) + (kept or 0)
    return bool(tot > 0 and removed / tot > thresh)


def build_rows(summaries: list[dict]) -> list[dict]:
    rows = []
    for s in summaries:
        rows.append({**s, **product_ratios(s),
                     "failure_taxonomy": classify_failure(s),
                     "dedup_warning": dedup_warning(
                         s.get("duplicate_rejected", 0),
                         s.get("final_clip_count", 0))})
    return rows
