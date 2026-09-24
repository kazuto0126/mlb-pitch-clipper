"""M1 shot-purity hardening (M6.3): confidence gate + dissolve guard.

Two conservative hardenings only (no M1 redesign, no resegmentation):

A. MIN_CENTER_FIELD_CONFIDENCE = 0.5 (global, all pitchers/sources).
   Evidence: 13 frame-verified bad CF accepts (logo animation, SUBSCRIBE
   card, close-ups, base-runner, batter x5, dirt-play) ALL score <= 0.458
   across 5 production runs; all frame-verified good CF shots score >= 0.61.
   Below threshold -> reject_reason = low_view_confidence.

B. Soft dissolve/transition veto (visual homogeneity, hist only).
   A candidate CF shot sampled at 5 points must satisfy
   min_adjacent_corr >= 0.8 AND edge_corr >= 0.8, else
   reject_reason = transition_contaminated. Evidence: impure mega-shots
   s005 (0.134/0.188) and s030 (0.776/0.708) vetoed; homogeneous CF
   (incl. s087 at 0.884/0.849 and verified goods >= 0.936) kept.
   Known residual: HOMOGENEOUS close-up FPs (e.g. s024, 16s pure
   close-up at 0.557) pass both checks — needs classifier work, recorded
   in validation/regression_cases/m1_shot_purity/.
"""
from __future__ import annotations

MIN_CENTER_FIELD_CONFIDENCE = 0.5
HOMOG_N = 5
HOMOG_MIN_ADJ = 0.8
HOMOG_MIN_EDGE = 0.8


def assess_homogeneity(video: str, start: float, end: float,
                       n: int = HOMOG_N) -> dict:
    """Sample n frames across [start, end]; HSV-hist adjacent + edge corr."""
    from .motion import grab_frame, hist_corr
    if end - start <= 0:
        return {"contaminated": True, "min_adj": 0.0, "edge": 0.0,
                "reason": "empty shot"}
    fracs = [0.1 + 0.8 * k / max(1, n - 1) for k in range(n)]
    frames = [grab_frame(video, start + (end - start) * f) for f in fracs]
    if any(f is None for f in frames):
        return {"contaminated": True, "min_adj": 0.0, "edge": 0.0,
                "reason": "unreadable frames"}
    adj = [hist_corr(frames[i], frames[i + 1]) for i in range(n - 1)]
    edge = hist_corr(frames[0], frames[-1])
    contaminated = min(adj) < HOMOG_MIN_ADJ or edge < HOMOG_MIN_EDGE
    return {"contaminated": contaminated,
            "min_adj": round(min(adj), 3), "edge": round(edge, 3),
            "reason": "transition inside shot" if contaminated else "homogeneous"}
