"""source_type classification from title/description/duration.

Precedence (M6.2): high-editing-risk families FIRST, so
"FULL GAME HIGHLIGHTS" / "FULL HIGHLIGHTS" / "FULL GAME RECAP" can never
inherit long-form trust from the words full/game/start. Only
every_pitch survives as an accepted condensed format (it is structured
pitch-by-pitch, not a montage).

No pitcher-specific branches — ever.
"""
from __future__ import annotations

import re

# Long-form markers that survive a highlights suffix ONLY when the duration
# is consistent (the word "highlights" is also channel branding, e.g.
# "| MLB Highlights"). Short duration => the highlights reading wins.
_LONGFORM_MIN_SEC = {"every_pitch": 0, "full_outing": 480,
                     "full_start": 480, "full_game": 1800}
_LONGFORM_PATS = {"every_pitch": [r"every pitch"],
                  "full_outing": [r"full outing"],
                  "full_start": [r"full start"],
                  "full_game": [r"complete game", r"full game", r"full match"]}
_HIGHLIGHT_PATS = [r"highlights?", r"\btop plays\b", r"\bmoments?\b",
                   r"\bmust c\b", r"must see", r"\bsickest\b", r"\bnasty\b",
                   r"\bfilthy\b", r"\binsane\b"]

# (type, patterns, reason). First match wins.
_PRIORITY = [
    ("short", [r"#shorts", r"\bshorts\b"], "short-form marker"),
    ("interview", [r"\binterview\b", r"press conference", r"media session",
                   r"sits down with", r"\bpodcast\b", r"mic'd up", r"micd up"],
     "interview/talk format"),
    ("reaction", [r"\breaction\b", r"\breacts?\b", r"watching ", r"live stream",
                  r"watch party"], "reaction format"),
    ("recap", [r"\brecap\b", r"\brewind\b"], "recap/rewind edit"),
    ("montage", [r"\bmontage\b", r"\bcinematic\b", r"\bcompilation\b",
                 r"\bmix\b", r"\bmashup\b", r"\banalysis\b", r"\bbreakdown\b",
                 r"film room", r"\bexplained\b"], "heavily edited feature"),
    ("pitching_highlights", [r"pitching highlights?", r"pitching debut"],
     "pitching-focused highlights"),
    ("general_highlights", [r"highlights?", r"\btop plays\b", r"\bmoments?\b",
                            r"\bmust c\b", r"must see", r"\bsickest\b",
                            r"\bnasty\b", r"\bfilthy\b", r"\binsane\b"],
     "general highlights/montage wording"),
    ("every_pitch", [r"every pitch"], "every-pitch structure"),
    ("full_outing", [r"full outing"], "full outing"),
    ("full_start", [r"full start"], "full start"),
    ("full_game", [r"complete game", r"full game", r"full match"],
     "full/complete game"),
]

_PITCH_HINTS = [r"on the mound", r"strikeout", r"\bks\b", r"whiffs?",
                r"\bouting\b", r"\bstart\b", r"shutout", r"no-?hitter",
                r"perfect game"]


def classify_source_type(title: str, description: str = "",
                         duration: float | None = None,
                         url: str = "") -> tuple[str, str]:
    """Returns (source_type, classification_reason)."""
    text = f"{title}\n{description}".lower()
    # Arbitration first: a long-form marker + highlights wording is decided
    # by duration (branding suffix vs condensed edit).
    long_hit = next((k for k, pats in _LONGFORM_PATS.items()
                     if any(re.search(p, text) for p in pats)), None)
    hi_hit = any(re.search(p, text) for p in _HIGHLIGHT_PATS)
    if long_hit and hi_hit:
        need = _LONGFORM_MIN_SEC[long_hit]
        if duration is not None and duration >= need:
            return long_hit, \
                f"{long_hit.replace('_', ' ')} + highlights suffix but " \
                f"duration consistent ({duration // 60:.0f}min)"
        return ("pitching_highlights"
                if any(re.search(p, text) for p in _PITCH_HINTS)
                else "general_highlights"), \
            f"{long_hit.replace('_', ' ')} claim contradicted by " \
            f"highlights wording at short/unknown duration"
    for stype, pats, why in _PRIORITY:
        if any(re.search(p, text) for p in pats):
            # pitching-flavored general highlights upgrade one tier
            if stype == "general_highlights" and any(
                    re.search(p, text) for p in _PITCH_HINTS):
                return "pitching_highlights", \
                    f"{why} + pitching context -> pitching_highlights"
            return stype, why
    if duration is not None and duration <= 65:
        return "short", "duration <= 65s"
    if "/shorts/" in url:
        return "short", "shorts URL"
    if any(re.search(p, text) for p in _PITCH_HINTS):
        return "pitching_highlights", "pitching context only"
    return "unknown", "no type signal"
