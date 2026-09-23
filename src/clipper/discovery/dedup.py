"""Dedup by video_id (keep first query_source, record all)."""
from __future__ import annotations


def dedup(hits: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for h in hits:
        vid = h.get("id") or h.get("video_id") or ""
        if not vid:
            continue
        if vid not in seen:
            seen[vid] = h
        else:
            prev = seen[vid].get("_query_source", "")
            cur = h.get("_query_source", "")
            if cur and cur not in prev:
                seen[vid]["_query_source"] = f"{prev} + {cur}".strip(" +")
    return list(seen.values())
