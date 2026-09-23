"""Game-year extraction. Never guess: unknown -> (None, "null").

high:   explicit game date/year in title/description
medium: season wording ("2026 season", "2026 campaign")
low:    published_date fallback
null:   nothing reliable
"""
from __future__ import annotations

import re

_MONTHS = ("january|february|march|april|may|june|july|august|september|"
           "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|"
           "oct|nov|dec")


def extract_year(title: str, description: str = "",
                 published_date: str | None = None) -> tuple[int | None, str]:
    text = f"{title}\n{description}"
    # explicit date: June 15 2026 / 2026-06-15 / 06/15/2026 / 15 June 2026
    # NOTE: month alternation must be grouped, else trailing constraints
    # apply to the last alternative only (bare month name => false hit).
    if re.search(rf"\b(?:{_MONTHS})\b\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+(19|20)\d{{2}}",
                 text, re.I):
        m = re.search(r"((?:19|20)\d{2})", text)
        return int(m.group(1)), "high"
    if re.search(r"\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text):
        m = re.search(r"\b((?:19|20)\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", text)
        return int(m.group(1)), "high"
    if re.search(r"\b\d{1,2}[-/]\d{1,2}[-/](19|20)\d{2}\b", text):
        m = re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]((?:19|20)\d{2})\b", text)
        return int(m.group(1)), "high"
    # explicit year mention near game words (season wording stays medium)
    m = re.search(r"\b((?:19|20)\d{2})\s+(highlights|outing|start|game)\b",
                  text, re.I)
    if m:
        # bare "2026 highlights" is weaker than a date but still explicit
        return int(m.group(1)), "high"
    # bare year in the TITLE (e.g. "2023 World Baseball Classic",
    # "Top 100 Plays 2024"): medium — usually the season, not a full date.
    m = re.search(r"\b((?:19|20)\d{2})\b", title)
    if m:
        return int(m.group(1)), "medium"
    m = re.search(r"\bseason\s+((?:19|20)\d{2})\b", text, re.I)
    if m:
        return int(m.group(1)), "medium"
    if published_date and re.match(r"\d{4}-\d{2}-\d{2}", published_date):
        return int(published_date[:4]), "low"
    return None, "null"
