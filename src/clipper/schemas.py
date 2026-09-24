"""Shot data model for Milestone 1 (no PitchEvent yet)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

VIEW_LABELS = (
    "center_field_good",
    "side_fullbody_acceptable",
    "closeup_bad",
    "batter_bad",
    "field_bad",
    "graphic_bad",
    "other_bad",
)

# Production default: ONLY center_field_good goes to pitch detection.
PRODUCTION_ACCEPTED = {"center_field_good"}


@dataclass
class Shot:
    shot_id: str
    start: float
    end: float
    duration: float
    view_class: str
    confidence: float
    accepted_for_pitch_detection: bool
    reject_reason: str | None
    classifier: str = ""
    scores: dict | None = None
    transition_contaminated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def build_shot(
    shot_id: str,
    start: float,
    end: float,
    view_class: str,
    confidence: float,
    classifier: str = "",
    scores: dict | None = None,
    min_confidence: float = 0.0,
    transition_contaminated: bool = False,
) -> Shot:
    """Production acceptance (M6.3): CF + conf >= min_confidence +
    not transition_contaminated. Defaults preserve the legacy
    view-only rule for backward compatibility (tests, offline replay)."""
    if view_class not in VIEW_LABELS:
        raise ValueError(f"unknown view_class: {view_class}")
    accepted = view_class in PRODUCTION_ACCEPTED
    reason: str | None = None
    if not accepted:
        reason = {
            "side_fullbody_acceptable": "non_center_field_side_view_reserved",
            "closeup_bad": "closeup",
            "batter_bad": "wrong_view_batter",
            "field_bad": "wrong_view_field",
            "graphic_bad": "graphic_transition",
            "other_bad": "other_rejected",
        }[view_class]
    elif confidence < min_confidence:
        accepted, reason = False, "low_view_confidence"
    elif transition_contaminated:
        accepted, reason = False, "transition_contaminated"
    return Shot(
        shot_id=shot_id,
        start=round(float(start), 3),
        end=round(float(end), 3),
        duration=round(float(end - start), 3),
        view_class=view_class,
        confidence=round(float(confidence), 4),
        accepted_for_pitch_detection=accepted,
        reject_reason=reason,
        classifier=classifier,
        scores=scores,
        transition_contaminated=transition_contaminated,
    )
