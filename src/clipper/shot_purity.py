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
# Homogeneous close-up veto (M6.4): a CF-labeled shot is vetoed only when
# BOTH signals agree it is not a confident broadcast framing:
#   class margin  = CF - max(non-CF) < MARGIN_MIN   (indecisive classifier)
#   edge density of the mid frame < EDGE_MIN_DENSITY (smooth foreground,
#     no broadcast scene texture: field + crowd + players)
# Evidence: 4 verified close-up FPs margins 0.003-0.277 / edges 0.050-0.081;
# 10 verified true CF margins 0.590-0.825 / edges 0.119-0.168 (day + night,
# 5 pitchers/sources). Vetoed event-shots sampled 6/6 non-pitch/tail.
# No body/face/pose features: edge density cannot tell WHAT is smooth.
MARGIN_MIN = 0.40
EDGE_MIN_DENSITY = 0.10
NON_CF_CLASSES = ("closeup_bad", "batter_bad", "field_bad", "graphic_bad",
                  "other_bad", "side_fullbody_acceptable")


def class_margin(scores: dict | None) -> float:
    sc = scores or {}
    return round(sc.get("center_field_good", 0.0)
                 - max(sc.get(k, 0.0) for k in NON_CF_CLASSES), 4)


def frame_edge_density(frame) -> float:
    import cv2
    a = cv2.resize(frame, (256, 144))
    if len(a.shape) == 3:
        a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    return round(float(cv2.Canny(gray, 80, 160).mean() / 255.0), 4)


def assess_closeup(video: str, start: float, end: float,
                   scores: dict | None) -> dict:
    """Conservative veto: margin AND texture must both fail."""
    from .motion import grab_frame
    margin = class_margin(scores)
    if margin >= MARGIN_MIN:
        return {"vetoed": False, "margin": margin, "edge": None,
                "reason": "decisive CF margin"}
    mid = grab_frame(video, (start + end) / 2)
    if mid is None:
        return {"vetoed": False, "margin": margin, "edge": None,
                "reason": "unreadable frame: keep (conservative)"}
    edge = frame_edge_density(mid)
    vetoed = edge < EDGE_MIN_DENSITY
    return {"vetoed": vetoed, "margin": margin, "edge": edge,
            "reason": "homogeneous close-up (low margin + low texture)"
            if vetoed else "low margin but broadcast texture: keep"}


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
