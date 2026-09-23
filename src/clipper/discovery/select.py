"""Selection: rank by final_score, take top-N (contract supports multi-source).

Future per-game outputs (Shohei_Ohtani_2025_01.mp4 …) consume this list.
This milestone only builds the ranking/selection contract — no download.
"""
from __future__ import annotations

from .classify import classify_source_type
from .scoring import score_candidate, selection_reason
from .year import extract_year


def select_sources(candidates: list[dict], top_n: int = 3) -> list[dict]:
    ranked = sorted(candidates, key=lambda c: c["suitability"]["final_score"],
                    reverse=True)
    return ranked[:top_n]


def enrich(raw: dict) -> dict:
    """normalize → classify → score → year → selection contract record."""
    from .fetch import normalize
    c = normalize(raw)
    stype = classify_source_type(c["title"], c["description_excerpt"],
                                 c["duration"], c["url"])
    comp = score_candidate(stype, c["title"], c["channel"],
                           c["description_excerpt"], c["duration"])
    year, conf = extract_year(c["title"], c["description_excerpt"],
                              c["published_date"])
    return {
        **c,
        "source_type": stype,
        "game_year": year,
        "game_year_confidence": conf,
        "suitability": comp,
        "selection_reason": selection_reason(stype, comp, c["channel"]),
    }
