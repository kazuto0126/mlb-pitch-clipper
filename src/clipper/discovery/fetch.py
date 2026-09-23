"""YouTube metadata fetch via yt-dlp (search only, NEVER download).

Each query runs `ytsearchN:text --dump-json --skip-download`.
Failures are per-query and non-fatal (logged, skipped).
"""
from __future__ import annotations

import json
import subprocess
import time

FETCH_JS_WARNING = "ejs"


def _run_ytsearch(query: str, limit: int, retries: int = 2) -> list[dict]:
    cmd = ["yt-dlp", f"ytsearch{limit}:{query}", "--dump-json",
           "--skip-download", "--no-playlist", "--ignore-errors",
           "--quiet", "--no-warnings"]
    last_err = ""
    for _ in range(retries + 1):
        try:
            out = subprocess.check_output(cmd, text=True, timeout=180)
            rows = []
            for line in out.splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
            return rows
        except Exception as e:  # network flakes, rate limits, extraction drift
            last_err = str(e)[:200]
            time.sleep(3)
    print(f"[discovery] query failed: {query!r} ({last_err})")
    return []


def fetch_candidates(queries: list[dict]) -> list[dict]:
    """Raw per-(query, video) hits. Dedup happens in dedup.py."""
    hits: list[dict] = []
    for q in queries:
        for meta in _run_ytsearch(q["query"], q["limit"]):
            meta["_query_source"] = q["query"]
            hits.append(meta)
        time.sleep(1)
    return hits


def normalize(meta: dict) -> dict:
    ud = meta.get("upload_date") or ""
    pub = f"{ud[:4]}-{ud[4:6]}-{ud[6:8]}" if len(ud) == 8 else None
    return {
        "video_id": meta.get("id", ""),
        "title": meta.get("title", "") or "",
        "channel": meta.get("channel", "") or meta.get("uploader", "") or "",
        "url": meta.get("webpage_url", "")
        or f"https://www.youtube.com/watch?v={meta.get('id', '')}",
        "duration": meta.get("duration"),
        "published_date": pub,
        "description_excerpt": (meta.get("description", "") or "")[:500],
        "query_source": meta.get("_query_source", ""),
    }
