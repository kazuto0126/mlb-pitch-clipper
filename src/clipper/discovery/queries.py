"""Discovery query generation (pitcher-agnostic templates).

`pitching highlights` is included for recall but ranks below full
outing / every pitch / full start by scoring design (M2 evidence:
fast highlights are hostile to complete clips).
"""
from __future__ import annotations

QUERY_TEMPLATES = [
    "{pitcher} full outing",
    "{pitcher} every pitch",
    "{pitcher} full start",
    "{pitcher} pitching full game",
    "{pitcher} complete game pitching",
    "{pitcher} vs full outing",
    "{pitcher} pitching highlights",
]


def build_queries(pitcher_name: str, per_query_limit: int = 5) -> list[dict]:
    name = " ".join(pitcher_name.split())
    if not name:
        raise ValueError("empty pitcher name")
    return [{"query": t.format(pitcher=name), "limit": per_query_limit}
            for t in QUERY_TEMPLATES]
