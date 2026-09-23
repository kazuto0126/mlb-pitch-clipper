"""source_type classification from title/description/duration.

Order: hard penalties first (short/interview/reaction), then positive
long-form types, then highlights tiers, else unknown. No pitcher-specific
branches — ever.
"""
from __future__ import annotations

import re

_PATTERNS = [
    ("short", [r"#shorts", r"\bshorts\b", r"^[^ ]{0,40}short$"]),
    ("interview", [r"\binterview\b", r"press conference", r"media session",
                   r"sits down with", r"\bpodcast\b", r"mic'd up", r"micd up"]),
    ("reaction", [r"\breaction\b", r"\breacts?\b", r"watching ", r"live stream",
                  r"watch party", r"breakdown(?!\s+pitch)"]),
    ("full_outing", [r"full outing"]),
    ("every_pitch", [r"every pitch"]),
    ("full_start", [r"full start"]),
    ("full_game", [r"full game", r"complete game", r"full match"]),
]

_PITCH_HINTS = [r"pitching", r"on the mound", r"strikeout", r"\bks\b",
                r"whiffs?", r"\bouting\b", r"\bstart\b", r"shutout",
                r"no-?hitter", r"perfect game"]
_HIGHLIGHT_HINTS = [r"highlights?", r"top plays", r"moments?", r"must c\b",
                    r"must see", r"sickest", r"nasty", r"filthy", r"insane",
                    r"compilation", r"\bmix\b", r"edit\b"]


def classify_source_type(title: str, description: str = "",
                         duration: float | None = None,
                         url: str = "") -> str:
    text = f"{title}\n{description}".lower()
    for stype, pats in _PATTERNS:
        if any(re.search(p, text) for p in pats):
            return stype
    if duration is not None and duration <= 65:
        return "short"
    if "/shorts/" in url:
        return "short"
    pitching = any(re.search(p, text) for p in _PITCH_HINTS)
    highlighty = any(re.search(p, text) for p in _HIGHLIGHT_HINTS)
    if pitching and highlighty:
        return "pitching_highlights"
    if highlighty:
        return "general_highlights"
    if pitching:
        return "pitching_highlights"
    return "unknown"
