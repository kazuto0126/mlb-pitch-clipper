"""Product filename: <Pitcher_English_Name>_<Year>.mp4 (spaces -> _).

- Only high/medium game_year_confidence years reach the filename; low
  (published_date fallback) and null -> <Name>_UnknownYear.mp4 (never fake
  with published year). The manifest keeps the raw game_year/confidence.
- Same-year collisions in one run -> _01, _02 suffixes.
- Only [A-Za-z0-9_] survive sanitizing (drops accents/symbols deterministically).
"""
from __future__ import annotations

import re

RELIABLE_YEAR_CONFIDENCE = ("high", "medium")


def sanitize_name(pitcher_name: str) -> str:
    base = "_".join(pitcher_name.split())
    base = re.sub(r"[^A-Za-z0-9_]", "", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "UnknownPitcher"


def reliable_game_year(game_year: int | None,
                       game_year_confidence: str | None) -> int | None:
    """game_year if it is a real game year (high/medium), else None."""
    if game_year and game_year_confidence in RELIABLE_YEAR_CONFIDENCE:
        return game_year
    return None


def product_filename(pitcher_name: str, game_year: int | None,
                     taken: set | None = None, *,
                     game_year_confidence: str | None) -> str:
    year = reliable_game_year(game_year, game_year_confidence)
    stem = f"{sanitize_name(pitcher_name)}_{year or 'UnknownYear'}"
    if not taken or f"{stem}.mp4" not in taken:
        return f"{stem}.mp4"
    i = 1
    while f"{stem}_{i:02d}.mp4" in taken:
        i += 1
    return f"{stem}_{i:02d}.mp4"
