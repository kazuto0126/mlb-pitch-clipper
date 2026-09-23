"""Product filename: <Pitcher_English_Name>_<Year>.mp4 (spaces -> _).

- game_year None -> <Name>_UnknownYear.mp4 (never fake with published year).
- Same-year collisions in one run -> _01, _02 suffixes.
- Only [A-Za-z0-9_] survive sanitizing (drops accents/symbols deterministically).
"""
from __future__ import annotations

import re


def sanitize_name(pitcher_name: str) -> str:
    base = "_".join(pitcher_name.split())
    base = re.sub(r"[^A-Za-z0-9_]", "", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "UnknownPitcher"


def product_filename(pitcher_name: str, game_year: int | None,
                     taken: set | None = None) -> str:
    stem = f"{sanitize_name(pitcher_name)}_{game_year if game_year else 'UnknownYear'}"
    if not taken or f"{stem}.mp4" not in taken:
        return f"{stem}.mp4"
    i = 1
    while f"{stem}_{i:02d}.mp4" in taken:
        i += 1
    return f"{stem}_{i:02d}.mp4"
