"""Suitability scoring with observable components.

final = w_sem*semantic + w_dur*duration + w_src*source + w_hold*hold
        - w_risk*editing_risk, clipped to [0, 1].

Weights live in WEIGHTS (configurable, documented) — not hard-locked, but
no per-pitcher tuning: the same weights apply to every pitcher.
"""
from __future__ import annotations

WEIGHTS = {"semantic": 0.35, "duration": 0.20, "source": 0.20,
           "hold": 0.15, "risk": 0.35}

SEMANTIC = {"full_outing": 1.0, "every_pitch": 1.0, "full_start": 0.9,
            "full_game": 0.85, "pitching_highlights": 0.5,
            "general_highlights": 0.3, "unknown": 0.4,
            "short": 0.05, "interview": 0.05, "reaction": 0.1}

OFFICIAL_CHANNELS = ["mlb", "espn", "fox sports", "tbs", "apple tv",
                     "peacock", "dazn", "sny", "yes network", "nesn",
                     "marquee", "bally", "sportsnet la", "snla",
                     "dodgers", "yankees", "red sox", "mets", "cubs",
                     "giants", "padres", "astros", "braves", "phillies",
                     "pirates", "tigers", "guardians", "athletics"]
SPORTS_MEDIA = ["bleacher report", "barstool", "jomboymedia", "foul territory",
                "the athletic", "cbssports", "nbcsports", "sporting news",
                "mlb network"]

RISK_KEYWORDS = ["montage", "mix", "#shorts", "shorts", "interview",
                 "reaction", "compilation", "recap", "news", "podcast",
                 "breakdown", "analysis", "explained", "film room",
                 "mic'd up", "top 10", "funniest", "crying", "laughing",
                 "emotional", "tribute", "insane", "filthy", "nastiest",
                 "cinematic", "rewind"]


def semantic_score(source_type: str) -> float:
    return SEMANTIC.get(source_type, 0.4)


def duration_score(duration: float | None) -> float:
    """Ideal 8–45 min; Shorts-length and marathon streams decay."""
    if duration is None:
        return 0.4
    if duration <= 65:
        return 0.0
    if duration < 8 * 60:
        return 0.3 + 0.7 * (duration - 65) / (8 * 60 - 65)
    if duration <= 45 * 60:
        return 1.0
    if duration <= 3 * 3600:
        return max(0.3, 1.0 - (duration - 45 * 60) / (3 * 3600 - 45 * 60) * 0.7)
    return 0.3


def source_score(channel: str) -> float:
    c = (channel or "").lower()
    if any(k in c for k in OFFICIAL_CHANNELS):
        return 1.0
    if any(k in c for k in SPORTS_MEDIA):
        return 0.6
    if any(k in c for k in ["tv", "network", "sports", "baseball", "official"]):
        return 0.7
    return 0.4


def hold_score(source_type: str, duration: float | None) -> float:
    """Metadata proxy for shot-hold quality (real measurement = M3 preview).

    Long-form outing/game types are expected to hold broadcast shots;
    Shorts-tier cannot. Calibrated against M2 evidence (highlights hostile).
    """
    base = {"full_outing": 0.9, "every_pitch": 0.9, "full_start": 0.85,
            "full_game": 0.8, "pitching_highlights": 0.45,
            "general_highlights": 0.3, "unknown": 0.4,
            "short": 0.05, "interview": 0.05, "reaction": 0.1}[source_type]
    if duration and duration > 20 * 60:
        base = min(1.0, base + 0.1)
    return base


def editing_risk(title: str, description: str = "",
                 duration: float | None = None) -> float:
    text = f"{title}\n{description}".lower()
    hits = sum(1 for k in RISK_KEYWORDS if k in text)
    risk = min(1.0, hits / 3.0)
    if duration is not None and duration <= 65:
        risk = max(risk, 0.9)
    if duration is not None and 65 < duration < 180:
        risk = max(risk, 0.4)
    return round(risk, 3)


def score_candidate(source_type: str, title: str, channel: str,
                    description: str = "",
                    duration: float | None = None,
                    weights: dict | None = None) -> dict:
    w = weights or WEIGHTS
    comp = {
        "semantic_score": round(semantic_score(source_type), 3),
        "duration_score": round(duration_score(duration), 3),
        "source_score": round(source_score(channel), 3),
        "hold_score": round(hold_score(source_type, duration), 3),
        "editing_risk": editing_risk(title, description, duration),
    }
    final = (w["semantic"] * comp["semantic_score"]
             + w["duration"] * comp["duration_score"]
             + w["source"] * comp["source_score"]
             + w["hold"] * comp["hold_score"]
             - w["risk"] * comp["editing_risk"])
    comp["final_score"] = round(max(0.0, min(1.0, final)), 4)
    return comp


def selection_reason(source_type: str, comp: dict, channel: str) -> str:
    bits = []
    if source_type in ("full_outing", "every_pitch", "full_start", "full_game"):
        bits.append(f"long-form {source_type.replace('_', ' ')}")
    elif source_type in ("pitching_highlights",):
        bits.append("pitching-focused highlights (fallback tier)")
    elif source_type in ("general_highlights",):
        bits.append("general highlights (fallback tier)")
    elif source_type in ("short", "interview", "reaction"):
        bits.append(f"penalized: {source_type}")
    else:
        bits.append("untyped source")
    if comp["source_score"] >= 1.0:
        bits.append(f"official/broadcast channel ({channel})")
    if comp["editing_risk"] >= 0.6:
        bits.append(f"high editing risk ({comp['editing_risk']})")
    if comp["duration_score"] <= 0.0:
        bits.append("too short for full-pitch editing")
    return "; ".join(bits)
