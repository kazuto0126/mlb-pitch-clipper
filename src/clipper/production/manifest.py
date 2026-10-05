"""Frozen manifest schema + quality warnings (M7 contract).

No body/pose/biomechanics fields. quality_warning never blocks output:
only zero usable clips becomes no_usable_clips.
"""
from __future__ import annotations

from .naming import reliable_game_year

LOW_YIELD = 0.03
FEW_CLIPS = 3

RUN_MANIFEST_KEYS = {"run_id", "pitcher", "status", "source_selection_mode",
                     "sources_attempted", "finals", "results", "created_utc",
                     "milestone"}
SOURCE_MANIFEST_KEYS = {
    "pitcher_name", "video_id", "source_url", "source_title", "channel",
    "source_type", "competition_context", "game_year",
    "game_year_confidence", "discovery_score", "preview_decision",
    "source_selection_mode", "download_status", "acquisition_method",
    "local_path", "normalization_status", "shot_count",
    "center_field_candidates", "rejected_low_confidence",
    "rejected_transition", "rejected_homogeneous_closeup",
    "complete_events", "rejected_events", "rejected_start_incomplete",
    "rejected_end_incomplete", "rejected_no_complete_pitch",
    "rejected_discontinuity", "raw_clip_count", "duplicate_rejected",
    "replay_rejected", "replay_status", "final_clip_count",
    "final_duration_sec", "final_codec", "final_path", "status",
    "quality_summary", "quality_warning", "warnings",
}


def build_warnings(m: dict) -> tuple[bool, list[str]]:
    """Pure: (quality_warning, warnings[]) from a source manifest dict."""
    warnings: list[str] = []
    if m.get("source_selection_mode") == "borderline_fallback":
        warnings.append("borderline source fallback (no recommended source)")
    elif m.get("source_selection_mode") == "insufficient_evidence_fallback":
        warnings.append("insufficient preview evidence fallback "
                        "(accepted only on full-run yield)")
    elif m.get("source_selection_mode") == "bad_evidence_fallback":
        warnings.append("preview judged source bad; last-resort fallback "
                        "(accepted only on full-run yield)")
    cf = m.get("center_field_candidates") or 0
    comp = m.get("complete_events") or 0
    if cf and comp / cf < LOW_YIELD:
        warnings.append(f"unusually low event yield ({comp}/{cf})")
    final = m.get("final_clip_count") or 0
    if 0 < final < FEW_CLIPS:
        warnings.append(f"very few final clips ({final})")
    year, conf = m.get("game_year"), m.get("game_year_confidence")
    if reliable_game_year(year, conf) is None:
        if year is not None:  # raw year kept in manifest, not in filename
            warnings.append(f"game year unreliable ({year} is {conf} "
                            "confidence; filename uses UnknownYear)")
        else:
            warnings.append("game year unreliable")
    if m.get("replay_status") == "uncertain":
        warnings.append("replay detection conservative (uncertain)")
    if m.get("status") == "no-usable-clips":
        warnings.append("no usable clips from this source")
    if m.get("status") == "low-yield":
        warnings.append(f"{final} final clips < {m.get('min_final_clips')} "
                        "required; source not used")
    return bool(warnings), warnings


def validate_manifest(m: dict, kind: str = "source") -> list[str]:
    """Returns list of missing required keys (empty = valid)."""
    keys = SOURCE_MANIFEST_KEYS if kind == "source" else RUN_MANIFEST_KEYS
    return sorted(k for k in keys if k not in m)
