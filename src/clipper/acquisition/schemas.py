"""M4 data contracts (formulas documented here, single source of truth).

complete_event_yield = complete_events / max(center_field_candidates, 1)
  Fraction of M1-accepted candidates that became complete M2 events.
complete_events_per_minute = complete_events / (preview_duration_sec / 60)
incomplete_rate = (start_incomplete + end_incomplete + no_complete_pitch
  + ambiguous + shot_discontinuity + shot_too_short) / max(cf_candidates, 1)
  i.e. rejected_windows / max(cf_candidates, 1). May exceed 1 only if a
  shot yields >1 rejection (never in current M2: 1 window -> <=1 rejection,
  except multi-event shots append event rejections too).
discontinuity_rate = shot_discontinuity_count / max(shot_count, 1)
  Measures M1 impurity (missed cuts) inside candidates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class PreviewSegmentPlan:
    index: int
    start: float
    duration: float
    method: str = "pending"          # yt-dlp-section | full-then-trim | failed
    file: str = ""
    error: str = ""


@dataclass
class SourcePreview:
    video_id: str = ""
    title: str = ""
    channel: str = ""
    url: str = ""
    source_type: str = "unknown"
    metadata_score: float = 0.0
    competition_context: str = "unknown"   # mlb | non_mlb | unknown
    preview_status: str = "pending"        # ok | partial | failed
    preview_error: str = ""
    preview_duration_sec: float = 0.0
    preview_segment_count: int = 0
    segments_skipped_empty: int = 0  # downloaded but zero CF candidates
    initial_preview_segments: int = 0
    expanded_preview_segments: int = 0
    total_preview_seconds: float = 0.0
    preview_fraction: float | None = None
    evidence_state: str = "insufficient"  # sufficient_good|sufficient_bad|insufficient
    adaptive_preview_triggered: bool = False
    adaptive_reason: str = ""
    final_preview_decision: str = "reject"  # mirrors preview_decision
    shot_count: int = 0            # interior shots only (edges carry no signal)
    edge_skipped_shots: int = 0    # truncated by section download edges
    center_field_shots: int = 0    # interior CF candidates (yield denominator)
    center_field_ratio: float = 0.0
    m2_complete_events: int = 0
    m2_rejected_events: int = 0
    complete_events_per_minute: float = 0.0
    complete_event_yield: float = 0.0
    incomplete_rate: float = 0.0
    discontinuity_rate: float = 0.0
    reject_by_reason: dict = field(default_factory=dict)
    preview_decision: str = "reject"       # recommended | borderline | reject
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(cf_candidates: int, shots: int, complete: int,
                    rejected: int, by_reason: dict,
                    preview_sec: float) -> dict:
    cf = max(cf_candidates, 1)
    minutes = preview_sec / 60.0 if preview_sec > 0 else 0.0
    disc = by_reason.get("shot_discontinuity", 0)
    return {
        "complete_events_per_minute": round(complete / minutes, 3) if minutes else 0.0,
        "complete_event_yield": round(complete / cf, 4),
        "incomplete_rate": round(rejected / cf, 4),
        "discontinuity_rate": round(disc / max(shots, 1), 4),
    }
