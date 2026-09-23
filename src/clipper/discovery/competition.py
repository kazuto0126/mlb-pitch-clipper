"""competition_context: is this MLB game footage?

Production default: only `mlb` is a primary production source.
`non_mlb` (WBC/NPB/amateur/bullpen/interview/documentary) stays in the
discovery pool but is rejected at the preview gate. `unknown` is allowed
through as borderline at best — never claim MLB without evidence.
No pitcher-specific branches.
"""
from __future__ import annotations

import re

_NON_MLB = [
    r"world baseball classic", r"\bwbc\b",
    r"\bnpb\b", r"nippon", r"japan series",
    r"\bkbo\b", r"korean series",
    r"\bcollege\b", r"\bncaa\b", r"high school", r"summer league",
    r"little league", r"\bamateur\b", r"\bdraft\b",
    r"bullpen( session)?", r"live bp\b", r"throwing session",
    r"\btraining\b", r"workout", r"practice",
    r"documentary", r"mic'd up", r"day in the life",
]
_MLB = [
    r"\bmlb\b", r"world series", r"postseason", r"opening day",
    r"regular season", r"all-star", r"all star",
    r"\bvs\.?\b", r"\btop \d+(st|nd|rd|th)\b",  # game situation wording
    r"inning", r"shutout", r"complete game", r"full outing",
    r"every pitch", r"full start", r"full game",
]


def classify_competition(title: str, description: str = "",
                         channel: str = "") -> str:
    text = f"{title}\n{description}".lower()
    if any(re.search(p, text) for p in _NON_MLB):
        return "non_mlb"
    game_text = f"{title}\n{channel}".lower()
    if any(re.search(p, game_text) for p in _MLB):
        return "mlb"
    return "unknown"
